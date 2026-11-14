import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder")]
import presets  # noqa: E402


class BuiltIn(unittest.TestCase):
    def test_table_contents(self):
        by_id = {p.id: p for p in presets.BUILTIN}
        self.assertEqual(len(by_id), len(presets.BUILTIN), "ids are unique")
        discs = sorted((p.d, p.t) for p in presets.BUILTIN if p.kind == "magnet" and p.shape == "disc")
        self.assertEqual(len(discs), 15)
        self.assertIn((6.0, 3.0), discs)
        blocks = [(p.l, p.w, p.t) for p in presets.BUILTIN if p.kind == "magnet" and p.shape == "block"]
        self.assertEqual(sorted(blocks), [(10, 5, 2), (10, 5, 3), (20, 10, 2), (20, 10, 5)])
        stickers = sorted(p.d for p in presets.BUILTIN if p.id.startswith("nfc-sticker-"))
        self.assertEqual(stickers, [10, 13, 20, 22, 25, 30, 38])
        self.assertTrue(all(p.t == 0.4 for p in presets.BUILTIN if p.id.startswith("nfc-sticker-")))
        card = by_id["nfc-card"]
        self.assertEqual((card.shape, card.l, card.w, card.t), ("block", 85.6, 54.0, 0.9))
        self.assertEqual((by_id["nfc-coin-30x2"].d, by_id["nfc-coin-30x2"].t), (30.0, 2.0))

    def test_stable_ids_and_labels(self):
        p = presets.find("magnet-disc-6x3")
        self.assertEqual((p.kind, p.shape, p.d, p.t, p.label), ("magnet", "disc", 6.0, 3.0, "6x3 magnet"))
        self.assertEqual(presets.find("magnet-block-10x5x2").label, "10x5x2 magnet")
        self.assertEqual(presets.find("nfc-sticker-25").label, "25 mm NFC sticker")
        self.assertIsNone(presets.find("nope"))

    def test_dims_footprint(self):
        disc, block = presets.find("magnet-disc-6x3"), presets.find("magnet-block-10x5x2")
        self.assertEqual((disc.l, disc.w), (6.0, 6.0))
        self.assertEqual((block.l, block.w, block.t), (10.0, 5.0, 2.0))

    def test_as_dict(self):
        d = presets.find("magnet-block-20x10x5").as_dict()
        self.assertEqual(d, {"id": "magnet-block-20x10x5", "name": "20x10x5 magnet", "kind": "magnet", "shape": "block",
                             "l": 20.0, "w": 10.0, "t": 5.0, "builtin": True})
        self.assertEqual(presets.find("magnet-disc-3x1").as_dict()["d"], 3.0)


class UserPresets(unittest.TestCase):
    def test_valid_disc_and_block(self):
        p = presets.parse_user({"id": "user-abc", "name": "  My  disc ", "kind": "magnet", "shape": "disc", "d": 7, "t": 2.5})
        self.assertEqual((p.id, p.label, p.d, p.t, p.builtin), ("user-abc", "My disc", 7.0, 2.5, False))
        b = presets.parse_user({"name": "tag", "kind": "nfc", "shape": "block", "l": 40, "w": 30, "t": 0.5})
        self.assertTrue(b.id.startswith("user-"))
        self.assertEqual((b.l, b.w, b.t), (40.0, 30.0, 0.5))

    def test_invalid(self):
        bad = [None, [], {"name": "", "kind": "magnet", "shape": "disc", "d": 5, "t": 1},
               {"name": "x" * 41, "kind": "magnet", "shape": "disc", "d": 5, "t": 1},
               {"name": "a", "kind": "rfid", "shape": "disc", "d": 5, "t": 1},
               {"name": "a", "kind": "magnet", "shape": "ring", "d": 5, "t": 1},
               {"name": "a", "kind": "magnet", "shape": "disc", "d": 0, "t": 1},
               {"name": "a", "kind": "magnet", "shape": "disc", "d": float("inf"), "t": 1},
               {"name": "a", "kind": "magnet", "shape": "disc", "d": True, "t": 1},
               {"name": "a", "kind": "magnet", "shape": "disc", "d": 5},
               {"name": "a", "kind": "magnet", "shape": "block", "l": 5, "w": 5, "t": 400},
               {"id": "magnet-disc-6x3", "name": "a", "kind": "magnet", "shape": "disc", "d": 5, "t": 1}]
        for raw in bad:
            with self.assertRaises(presets.PresetError, msg=repr(raw)):
                presets.parse_user(raw)

    def test_clean_list_drops_invalid_and_duplicates_and_caps(self):
        good = {"id": "user-1", "name": "a", "kind": "magnet", "shape": "disc", "d": 5, "t": 1}
        out = presets.clean_user_presets([good, {"bad": 1}, dict(good, name="dup")])
        self.assertEqual([p["name"] for p in out], ["a"])
        self.assertIsNone(presets.clean_user_presets("nope"))
        many = [dict(good, id="user-%d" % i) for i in range(presets.MAX_USER_PRESETS + 5)]
        self.assertEqual(len(presets.clean_user_presets(many)), presets.MAX_USER_PRESETS)

    def test_resolve(self):
        users = [{"id": "user-1", "name": "Mine", "kind": "nfc", "shape": "disc", "d": 20, "t": 0.5}]
        self.assertEqual(presets.resolve({"preset": "user-1"}, users).label, "Mine")
        self.assertEqual(presets.resolve({"preset": "magnet-disc-6x3"}, users).d, 6.0)
        custom = presets.resolve({"custom": {"kind": "magnet", "shape": "disc", "d": 6, "t": 3}}, [])
        self.assertEqual((custom.label, custom.id), ("6x3 magnet", "custom"))
        with self.assertRaises(presets.PresetError):
            presets.resolve({"preset": "missing"}, users)
        with self.assertRaises(presets.PresetError):
            presets.resolve({}, users)

    def test_upsert_and_delete(self):
        users = presets.upsert([], {"name": "a", "kind": "magnet", "shape": "disc", "d": 5, "t": 1})
        pid = users[0]["id"]
        users2 = presets.upsert(users, {"id": pid, "name": "b", "kind": "magnet", "shape": "disc", "d": 5, "t": 1})
        self.assertEqual([u["name"] for u in users2], ["b"])
        self.assertEqual(users[0]["name"], "a", "input list is not changed")
        self.assertEqual(presets.delete(users2, pid), [])
        with self.assertRaises(presets.PresetError):
            presets.delete(users2, "user-none")
        full = [dict(users[0], id="user-%d" % i) for i in range(presets.MAX_USER_PRESETS)]
        with self.assertRaises(presets.PresetError):
            presets.upsert(full, {"name": "x", "kind": "magnet", "shape": "disc", "d": 5, "t": 1})


if __name__ == "__main__":
    unittest.main()
