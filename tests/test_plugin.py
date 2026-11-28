"""plugin.py under a fake `orca`: the page bridge, load -> plan -> apply -> open, the storage rule and the
plugin audit policy (tests/audit_guard.py) on the worker threads."""

import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder"), os.path.join(ROOT, "tests")]

import audit_guard  # noqa: E402
import fake_orca  # noqa: E402
import fixtures  # noqa: E402

orca = fake_orca.install_orca()
import plugin  # noqa: E402
import threemf  # noqa: E402

LIVE = {"layer_height": "0.2", "initial_layer_print_height": "0.2", "machine_pause_gcode": "M601",
        "print_sequence": "by layer", "raft_layers": "0", "printable_area": ["0x0", "256x0", "256x256", "0x256"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.storage, True)
        self.src = fixtures.cube(os.path.join(tempfile.mkdtemp(), "cube.3mf"))
        global orca
        orca = fake_orca.install_orca(preset=LIVE, storage=self.storage, source=self.src, project_path="/work/Cube.3mf")
        plugin.orca = orca
        plugin._storage_dir, plugin._store, plugin._session = None, None, None
        orca.registered.clear()
        plugin.Embedder().register_capabilities()
        self.page = plugin.EmbedderPage()
        self.page.posted = []
        self.seq = 0

    def send(self, cmd, **args):
        self.seq += 1
        self.page.on_message({"type": "cmd", "id": self.seq, "cmd": cmd, "args": args})
        return self.seq

    def reply(self, msg_id, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            for m in self.page.posted:
                if m.get("type") == "reply" and m.get("id") == msg_id:
                    return m
            time.sleep(0.01)
        self.fail("no reply to %s: %r" % (msg_id, self.page.posted[-3:]))

    def call(self, cmd, **args):
        m = self.reply(self.send(cmd, **args))
        self.assertNotIn("error", m, m)
        return m["result"]

    def error(self, cmd, **args):
        m = self.reply(self.send(cmd, **args))
        self.assertIn("error", m, m)
        return m["error"]["code"]


class Bridge(Base):
    def test_registration_asks_for_threads_only(self):
        self.assertEqual([c.__name__ for c in orca.registered], ["EmbedderPage"])
        self.assertEqual(orca.permissions, [{"threading": True}])
        self.assertEqual(self.page.get_name(), "Embedder")
        icon = self.page.get_icon()
        self.assertTrue(icon.endswith("embedder-icon.png"), icon)   # not embedder.png: the host would load an old embedder.svg first
        with open(icon, "rb") as f:
            self.assertEqual(f.read(), plugin._asset("icon.png"))

    def test_hello_settings_and_unknown(self):
        r = self.call("hello")
        self.assertEqual(r["settings"]["cover_nfc"], 0.6)
        self.assertEqual(self.call("settings.save", settings={"xy_clearance": 0.3})["xy_clearance"], 0.3)
        self.assertEqual(self.call("settings.get")["xy_clearance"], 0.3)
        self.assertEqual(self.error("nope"), "unknown_command")
        self.page.on_message("garbage")
        self.page.on_message({"type": "cmd", "id": 99, "cmd": "hello", "args": "x"})
        self.assertNotIn("error", self.reply(99))

    def test_a_language_that_cannot_be_saved_does_not_raise_into_the_host(self):
        os.makedirs(os.path.join(self.storage, "settings.json.tmp"))   # the settings file can't be written
        self.page.on_message({"type": "ui_language", "value": "en"})
        self.assertEqual(self.error("settings.save", settings={"xy_clearance": 0.3}), "internal")

    def test_presets(self):
        r = self.call("presets.list")
        self.assertEqual(len(r["builtin"]), 15 + 4 + 7 + 2 + 1 + 4 + 3)
        self.assertEqual(r["user"], [])
        saved = self.call("presets.save", preset={"name": "Big", "kind": "magnet", "shape": "disc", "d": 25, "t": 5})
        self.assertEqual([u["name"] for u in saved["user"]], ["Big"])
        self.assertEqual(self.call("presets.list")["user"][0]["id"], saved["id"])
        self.assertEqual(self.error("presets.save", preset={"name": ""}), "bad_name")
        self.call("settings.save", settings={"pocket_shapes": {saved["id"]: "circle", "magnet-disc-6x3": "square"}})
        self.assertEqual(self.call("presets.delete", id=saved["id"])["user"], [])
        self.assertEqual(self.call("settings.get")["pocket_shapes"], {"magnet-disc-6x3": "square"}, "its shape went with it")
        self.assertEqual(self.error("presets.delete", id="user-x"), "unknown_preset")

    def test_page_html_has_boot_and_language(self):
        orca.host.app_language = "pt_BR"
        html = self.page.get_ui()
        self.assertNotIn("__BOOT__", html)
        self.assertIn('"lang": "pt_BR"', html)


class RoundTrip(Base):
    def load(self):
        r = self.call("project.load")
        self.assertTrue(any(m.get("type") == "progress" and m.get("job") == r["job"] for m in self.page.posted))
        return r

    def test_load_plan_apply_open(self):
        audit_guard.enable(orca.permissions[-1], self.storage)
        self.addCleanup(audit_guard.disable)
        r = self.load()
        self.assertEqual(orca.plater.exports, [os.path.join(self.storage, "jobs", r["job"], "source.3mf")])
        self.assertEqual(r["name"], "Cube")
        chunk = self.call("mesh.chunk", job=r["job"], object=0, part=0, kind="pos", i=0)
        self.assertEqual(chunk["bytes"], 96)
        pocket = {"object": 0, "part": 0, "tri": 2, "point": [110, 110, 20], "preset": "magnet-disc-6x3", "mode": "embedded"}
        plan = self.call("pocket.plan", job=r["job"], **pocket)
        self.assertAlmostEqual(plan["pause_z"], 19.2)
        applied = self.call("project.apply", job=r["job"], pockets=[pocket], remove=[])
        self.assertEqual(applied["pauses"], [{"top_z": 19.2, "extra": "Embedder: insert 1 x 6x3 magnet",
            "items": [{"label": "6x3 magnet", "polarity": None, "n": 1}]}])
        self.assertTrue(applied["path"].startswith(self.storage))
        self.assertEqual(audit_guard.denials(), [])
        pkg = threemf.read(applied["path"])
        self.assertEqual(len(pkg.embedder_parts()), 1)
        with open(self.src, "rb") as f, open(os.path.join(self.storage, "jobs", r["job"], "source.3mf"), "rb") as g:
            self.assertEqual(f.read(), g.read(), "the exported copy is used as is; the original is never written")
        opened = []
        plugin._open_in_orca = lambda path: opened.append(path) or True
        self.addCleanup(setattr, plugin, "_open_in_orca", plugin.open_in_orca)
        self.assertEqual(self.call("project.open", path=applied["path"]), {"open": "asked"})
        self.assertEqual(opened, [os.path.realpath(applied["path"])])
        self.assertEqual(self.error("project.open", path=self.src), "bad_request")

    def test_old_copies_status_and_clear(self):
        old = os.path.join(self.storage, "Cube-embedder-20250101-000000-abcdef.3mf")
        new = os.path.join(self.storage, "Cube-embedder-20260101-000000-abcdef.3mf")
        for path, t in ((old, 1), (new, 2)):
            with open(path, "wb") as f:
                f.write(b"x" * 300)
            os.utime(path, (t, t))
        self.assertEqual(self.call("copies.status"), {"count": 1, "bytes": 300, "kept": 1})
        self.assertEqual(self.call("copies.clear"), {"removed": 1, "freed": 300, "failed": 0, "count": 0, "bytes": 0, "kept": 1})
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new))

    def test_storage_is_only_asked_inside_callbacks(self):
        plugin._storage_dir = None
        orca.storage_calls["inside"] = True
        self.call("hello")                    # a callback: the folder is kept
        orca.storage_calls["inside"] = False   # worker threads cannot ask any more
        r = self.load()
        applied = self.call("project.apply", job=r["job"], pockets=[], remove=[])
        self.assertTrue(applied["path"].startswith(self.storage))

    def test_live_preset_values_fill_an_empty_project(self):
        fixtures.empty_settings(self.src)
        orca.host.preset_bundle().full_config_value = lambda k: dict(LIVE, layer_height="0.12").get(k)
        r = self.load()
        self.assertEqual((r["config_source"], r["settings"]["layer_height"]), ("preset", 0.12))

    def test_failed_export(self):
        orca.plater.source = None
        self.assertEqual(self.error("project.load"), "export_failed")

    def test_stale_job(self):
        first = self.load()
        self.load()
        self.assertEqual(self.error("mesh.chunk", job=first["job"], object=0, part=0, kind="pos", i=0), "stale_job")

    def test_auto_fridge_bridge_command(self):
        r = self.load()
        auto = self.call("pocket.auto_fridge", job=r["job"], object=0, count="auto", preset="magnet-disc-6x2", mode="embedded")
        self.assertEqual(auto["count"], 1)
        self.assertEqual(auto["items"][0]["plan"]["face"], "bottom")
        applied = self.call("project.apply", job=r["job"], pockets=[it["args"] for it in auto["items"]], remove=[])
        self.assertEqual(len(applied["pauses"]), 1)

    def test_plugin_fallbacks_lifecycle_and_open_in_orca(self):
        from unittest import mock
        # Lifecycle & default config
        self.assertEqual(self.page.get_default_config(), {})
        self.page.on_load()
        self.page.on_unload()

        # UnicodeEncodeError fallback in log()
        bad_out = mock.MagicMock()
        bad_out.encoding = "ascii"
        bad_out.write.side_effect = [UnicodeEncodeError("ascii", "\u2603", 0, 1, "bad"), None, None, None]
        with mock.patch("sys.stdout", bad_out):
            plugin.log("snow \u2603")

        # Fallback to cap.get_config / cap.save_config when storage() is unavailable
        plugin._storage_dir, plugin._store = None, None
        cap = mock.MagicMock()
        saved_cfg = ['{"embedder_settings": {"xy_clearance": 0.25}}']
        cap.get_config.side_effect = lambda: saved_cfg[0]
        cap.save_config.side_effect = lambda txt: saved_cfg.__setitem__(0, txt)
        with mock.patch.object(plugin.orca.host.plugin, "storage", side_effect=RuntimeError("no dir")):
            store = plugin.get_store(cap)
            self.assertEqual(store.effective()["xy_clearance"], 0.25)
            store.update({"xy_clearance": 0.35})
            self.assertIn("0.35", saved_cfg[0])
            self.assertEqual(plugin._cap_config(mock.MagicMock(get_config=lambda: "not-json")), {})
            plugin._store = None
            self.assertEqual(plugin.get_store(None).effective()["xy_clearance"], 0.2)

        # Worker unexpected exception -> internal error reply; SessionError -> error code; open_failed
        with mock.patch.object(plugin, "get_session", side_effect=RuntimeError("boom")):
            self.assertEqual(self.error("pocket.plan", job="j1"), "internal")
        with mock.patch.object(plugin, "get_session", side_effect=plugin.session.SessionError("stale_job", "old")):
            self.assertEqual(self.error("pocket.plan", job="j1"), "stale_job")
        self.page.on_message({"type": "other"})
        with mock.patch.object(plugin.orca.host, "model", side_effect=RuntimeError("no model")):
            self.assertEqual(plugin._current_plate(), 1)
        with mock.patch.object(plugin.orca.host, "preset_bundle", side_effect=RuntimeError("no bundle")):
            self.assertEqual(plugin._live_values(), {})
        r_ok = self.load()
        applied = self.call("project.apply", job=r_ok["job"], pockets=[], remove=[])
        with mock.patch.object(plugin, "_open_in_orca", side_effect=OSError("cannot launch")):
            self.assertEqual(self.error("project.open", path=applied["path"]), "open_failed")
        # get_icon() second call hits existing identical file, then directory blocks write -> ""
        self.assertTrue(self.page.get_icon().endswith("embedder-icon.png"))
        self.assertTrue(self.page.get_icon().endswith("embedder-icon.png"))
        os.remove(os.path.join(self.storage, "embedder-icon.png"))
        os.makedirs(os.path.join(self.storage, "embedder-icon.png"), exist_ok=True)
        self.assertEqual(self.page.get_icon(), "")

        # _asset in packaged (__package__) mode, _host_language error, _live_values skip, worker SessionError & reply fail
        import types
        with mock.patch.object(plugin, "__package__", "embedder"), \
             mock.patch.object(plugin, "_assets", types.SimpleNamespace(ICON_PNG=b"png"), create=True), \
             mock.patch("pkgutil.get_data", side_effect=[b"<html>", None]):
            self.assertEqual(plugin._asset("icon.png"), b"png")
            self.assertEqual(plugin._asset("app.html"), "<html>")
            with self.assertRaises(FileNotFoundError):
                plugin._asset("missing.html")
        with mock.patch.object(plugin.orca.host, "app_language", side_effect=RuntimeError("no lang")):
            self.assertIsNone(plugin._host_language())
        with mock.patch.object(plugin.orca.host, "preset_bundle", return_value=types.SimpleNamespace(
            full_config_value=mock.MagicMock(side_effect=RuntimeError("bad key"))
        )):
            self.assertEqual(plugin._live_values(), {})
        with mock.patch.object(self.page, "reply", side_effect=RuntimeError("gone")), \
             mock.patch.object(plugin, "get_session", side_effect=RuntimeError("boom")):
            self.send("pocket.plan", job="j1")
            time.sleep(0.05)
        with mock.patch.object(plugin, "get_session", side_effect=plugin.session.SessionError("bad_request", "bad")):
            self.assertEqual(self.error("pocket.plan", job="j1"), "bad_request")
        # Direct _worker SessionError path
        done_err = []
        fake_page = mock.MagicMock(reply=lambda mid, result=None, error=None: done_err.append(error))
        def raise_sess():
            raise plugin.session.SessionError("stale_job", "old")
        plugin._worker(fake_page, 1, raise_sess)
        time.sleep(0.05)
        self.assertEqual(done_err[0]["code"], "stale_job")

        # open_in_orca platform branches
        with mock.patch("subprocess.Popen") as popen:
            with mock.patch("sys.platform", "darwin"):
                self.assertTrue(plugin.open_in_orca("/tmp/a.3mf"))
            with mock.patch("sys.platform", "linux"):
                self.assertTrue(plugin.open_in_orca("/tmp/a.3mf"))
            with mock.patch("sys.platform", "win32"):
                self.assertFalse(plugin.open_in_orca("/tmp/a.3mf"))
                orca_exe = os.path.join(self.storage, "orca-slicer.exe")
                with open(orca_exe, "wb") as f:
                    f.write(b"")
                with mock.patch("sys.executable", orca_exe):
                    self.assertTrue(plugin.open_in_orca("/tmp/a.3mf"))
            self.assertEqual(popen.call_count, 3)

        with mock.patch.object(plugin.orca.host.plater(), "export_3mf_copy", side_effect=RuntimeError("export err")):
            self.assertEqual(self.error("project.load"), "export_failed")


if __name__ == "__main__":
    unittest.main()
