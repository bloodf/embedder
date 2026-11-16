import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder")]
import settings  # noqa: E402


class StoreTests(unittest.TestCase):
    def test_defaults_without_storage(self):
        s = settings.Store().effective()
        self.assertEqual(s, settings.DEFAULTS)
        self.assertEqual((s["xy_clearance"], s["z_clearance"], s["cover_magnet"], s["cover_nfc"]), (0.2, 0.2, 1.0, 0.6))
        self.assertEqual(s["ui_language"], "auto")
        self.assertEqual(s["user_presets"], [])

    def test_update_validates_and_ignores_unknown(self):
        st = settings.Store()
        out = st.update({"xy_clearance": 0.3, "z_clearance": "0.1", "cover_magnet": 2, "cover_nfc": float("nan"),
                         "nope": 1, "ui_language": "klingon"})
        self.assertEqual(out["xy_clearance"], 0.3)
        self.assertEqual(out["z_clearance"], 0.2)      # wrong type ignored
        self.assertEqual(out["cover_magnet"], 2.0)     # whole numbers are fine
        self.assertIsInstance(out["cover_magnet"], float)
        self.assertEqual(out["cover_nfc"], 0.6)        # not finite
        self.assertNotIn("nope", out)
        self.assertEqual(out["ui_language"], "auto")
        self.assertEqual(st.update({"ui_language": "pt-BR"})["ui_language"], "pt-BR")
        for lang in ("es", "de", "zh-CN", "en", "auto"):
            self.assertEqual(st.update({"ui_language": lang})["ui_language"], lang)

    def test_ranges_and_booleans(self):
        st = settings.Store()
        out = st.update({"xy_clearance": -0.1, "z_clearance": 5, "cover_magnet": True, "cover_nfc": 11})
        self.assertEqual((out["xy_clearance"], out["z_clearance"], out["cover_magnet"], out["cover_nfc"]), (0.2, 0.2, 1.0, 0.6))
        self.assertEqual(st.update({"xy_clearance": 0})["xy_clearance"], 0.0)

    def test_file_roundtrip_atomic_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            settings.Store(path).update({"xy_clearance": 0.15})
            self.assertEqual(settings.Store(path).effective()["xy_clearance"], 0.15)
            self.assertEqual(os.listdir(d), ["settings.json"])
            with open(path, "w") as f:
                f.write("{broken")
            self.assertEqual(settings.Store(path).effective(), settings.DEFAULTS)

    def test_callables(self):
        box = []
        st = settings.Store(load=lambda: box[-1] if box else "", save=box.append)
        st.update({"cover_nfc": 0.8})
        self.assertEqual(json.loads(box[-1])["cover_nfc"], 0.8)
        self.assertEqual(settings.Store(load=lambda: box[-1], save=box.append).effective()["cover_nfc"], 0.8)

    def test_effective_is_a_copy_and_unchanged_update_does_not_write(self):
        box = []
        st = settings.Store(load=lambda: "", save=box.append)
        st.effective()["xy_clearance"] = 9
        self.assertEqual(st.effective()["xy_clearance"], 0.2)
        st.update({"xy_clearance": 0.3})
        st.update({"xy_clearance": 0.3, "bogus": 1})
        self.assertEqual(len(box), 1)

    def test_user_presets_are_validated(self):
        st = settings.Store()
        good = {"id": "user-1", "name": "Mine", "kind": "magnet", "shape": "disc", "d": 7, "t": 2}
        out = st.update({"user_presets": [good, {"name": ""}]})
        self.assertEqual([p["id"] for p in out["user_presets"]], ["user-1"])
        self.assertEqual(st.update({"user_presets": "x"})["user_presets"], out["user_presets"])


if __name__ == "__main__":
    unittest.main()
