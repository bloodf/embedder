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
        self.assertTrue(self.page.get_icon().endswith("embedder.svg"))

    def test_hello_settings_and_unknown(self):
        r = self.call("hello")
        self.assertEqual(r["settings"]["cover_nfc"], 0.6)
        self.assertEqual(self.call("settings.save", settings={"xy_clearance": 0.3})["xy_clearance"], 0.3)
        self.assertEqual(self.call("settings.get")["xy_clearance"], 0.3)
        self.assertEqual(self.error("nope"), "unknown_command")
        self.page.on_message("garbage")
        self.page.on_message({"type": "cmd", "id": 99, "cmd": "hello", "args": "x"})
        self.assertNotIn("error", self.reply(99))

    def test_presets(self):
        r = self.call("presets.list")
        self.assertEqual(len(r["builtin"]), 15 + 4 + 7 + 2 + 1)
        self.assertEqual(r["user"], [])
        saved = self.call("presets.save", preset={"name": "Big", "kind": "magnet", "shape": "disc", "d": 25, "t": 5})
        self.assertEqual([u["name"] for u in saved["user"]], ["Big"])
        self.assertEqual(self.call("presets.list")["user"][0]["id"], saved["id"])
        self.assertEqual(self.error("presets.save", preset={"name": ""}), "bad_name")
        self.assertEqual(self.call("presets.delete", id=saved["id"])["user"], [])
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
        self.assertEqual(applied["pauses"], [{"top_z": 19.2, "extra": "Embedder: insert 1 x 6x3 magnet"}])
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


if __name__ == "__main__":
    unittest.main()
