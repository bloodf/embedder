import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder")]
import geometry as g  # noqa: E402
import pocket  # noqa: E402
import presets  # noqa: E402

MAG = presets.find("magnet-disc-6x3")
BLOCK = presets.find("magnet-block-10x5x2")
NFC = presets.find("nfc-sticker-25")
GRID = pocket.Grid(0.2, 0.2)
CTX = pocket.Context(grid=GRID, xy_clearance=0.2, z_clearance=0.2)


def req(insert=MAG, mode="embedded", point=(10, 10, 20), normal=(0, 0, 1), spin=0.0, cover=1.0):
    return pocket.Request(insert, mode, point, normal, spin, cover)


class Grid(unittest.TestCase):
    def test_snap(self):
        g2 = pocket.Grid(0.3, 0.2)
        self.assertEqual(g2.snap_down(0.1), 0.0)
        self.assertEqual(g2.snap_down(0.3), 0.3)
        self.assertEqual(g2.snap_down(0.69), 0.5)
        self.assertEqual(g2.snap_down(0.7), 0.7)
        self.assertEqual(g2.snap_up(0.0), 0.0)
        self.assertEqual(g2.snap_up(0.1), 0.3)
        self.assertEqual(g2.snap_up(0.51), 0.7)
        self.assertEqual(g2.snap_up(0.7000000001), 0.7)
        self.assertEqual(g2.top(0), 0.3)
        self.assertAlmostEqual(g2.top(3), 0.9)

    def test_invalid_grid(self):
        with self.assertRaises(ValueError):
            pocket.Grid(0, 0.2)
        with self.assertRaises(ValueError):
            pocket.Grid(0.2, -1)


class Embedded(unittest.TestCase):
    def test_disc_on_top_face_matches_the_spike(self):
        """Cube 20 mm, H=0.2: 6x3 magnet under a 1 mm cover. Depth 3.2 -> 16 layers; pause one layer above."""
        p = pocket.plan(req(point=(10, 10, 20)), CTX)
        self.assertEqual((p.face, p.shape, p.mode), ("top", "cylinder", "embedded"))
        self.assertAlmostEqual(p.size[0], 6.4)
        self.assertAlmostEqual(p.floor, 15.8)
        self.assertAlmostEqual(p.top, 19.0)
        self.assertAlmostEqual(p.size[2], p.top - p.floor)
        self.assertGreaterEqual(p.top - p.floor, 3.2 - 1e-9)
        self.assertAlmostEqual(p.pause_z, 19.2)
        self.assertAlmostEqual(p.cover, 1.0)
        self.assertTrue(_close(g.apply(p.transform, (0, 0, 0)), (10, 10, 15.8)))
        self.assertEqual(p.warnings, ())

    def test_floor_and_top_are_on_the_grid_and_never_shallow(self):
        grid = pocket.Grid(0.3, 0.12)
        p = pocket.plan(req(point=(0, 0, 9.87)), pocket.Context(grid=grid, xy_clearance=0.2, z_clearance=0.2))
        for z in (p.floor, p.top):
            k = (z - 0.3) / 0.12
            self.assertAlmostEqual(k, round(k), places=6)
        self.assertGreaterEqual(p.top - p.floor, 3.2 - 1e-9)
        self.assertAlmostEqual(p.pause_z, p.top + 0.12)

    def test_bottom_face_cover_below(self):
        p = pocket.plan(req(point=(5, 5, 0), normal=(0, 0, -1)), CTX)
        self.assertEqual(p.face, "bottom")
        self.assertAlmostEqual(p.floor, 1.0)
        self.assertAlmostEqual(p.top, 4.2)
        self.assertAlmostEqual(p.pause_z, 4.4)

    def test_block_on_flat_face_spins(self):
        p = pocket.plan(req(insert=BLOCK, spin=90), CTX)
        self.assertEqual(p.shape, "box")
        self.assertAlmostEqual(p.size[0], 10.4)
        self.assertAlmostEqual(p.size[1], 5.4)
        self.assertTrue(_close(g.apply_dir(p.transform, (1, 0, 0)), (0, 1, 0)))

    def test_disc_behind_side_face_is_a_vertical_slot(self):
        p = pocket.plan(req(point=(20, 10, 10), normal=(1, 0, 0), cover=1.0), CTX)
        self.assertEqual((p.face, p.shape), ("side", "box"))
        width, depth, height = p.size
        self.assertAlmostEqual(width, 6.4)            # d + 2 xy
        self.assertAlmostEqual(depth, 3.4)            # t + 2 xy
        self.assertGreaterEqual(height, 6.2 - 1e-9)   # d + z, snapped up
        self.assertTrue(_close(g.apply_dir(p.transform, (0, 0, 1)), (0, 0, 1)))
        centre = g.apply(p.transform, (0, 0, 0))
        self.assertAlmostEqual(centre[0], 20 - 1.0 - 3.4 / 2)   # behind a 1 mm wall
        self.assertAlmostEqual(centre[1], 10)
        self.assertAlmostEqual(abs(g.apply_dir(p.transform, (1, 0, 0))[1]), 1)   # width along the wall
        self.assertAlmostEqual(p.pause_z, p.top + 0.2)
        self.assertAlmostEqual(p.cover, 1.0)

    def test_thin_cover_warns(self):
        p = pocket.plan(req(insert=NFC, cover=0.1), CTX)
        self.assertIn("thin_cover", p.warnings)

    def test_blocks(self):
        cases = {
            "tilted_face": (req(normal=(0.7071, 0, 0.7071)), CTX),
            "by_object": (req(), CTX._replace(by_object=True)),
            "no_pause_gcode": (req(), CTX._replace(pause_gcode=False)),
            "raft": (req(), CTX._replace(raft=True)),
            "variable_layer_height": (req(), CTX._replace(variable_layers=True)),
            "instances_differ": (req(), CTX._replace(instances_rigid=False)),
            "below_bed": (req(point=(0, 0, 2)), CTX),
        }
        for code, (r, ctx) in cases.items():
            with self.assertRaises(pocket.Blocked, msg=code) as cm:
                pocket.plan(r, ctx)
            self.assertEqual(cm.exception.code, code)

    def test_pause_must_be_above_the_first_layer(self):
        with self.assertRaises(pocket.Blocked) as cm:
            pocket.check_pause(0.2, GRID)
        self.assertEqual(cm.exception.code, "pause_too_low")
        pocket.check_pause(0.4, GRID)
        p = pocket.plan(req(insert=NFC, point=(0, 0, 0), normal=(0, 0, -1), cover=0.0), CTX)
        self.assertEqual((p.floor, p.pause_z), (0.0, 0.8))

    def test_bad_mode(self):
        with self.assertRaises(pocket.Blocked) as cm:
            pocket.plan(req(mode="sideways"), CTX)
        self.assertEqual(cm.exception.code, "bad_mode")


class Open(unittest.TestCase):
    def test_open_on_tilted_face_follows_the_normal_and_overshoots(self):
        n = (0.6, 0, 0.8)
        p = pocket.plan(req(mode="open", point=(1, 2, 3), normal=n, spin=10), CTX._replace(by_object=True))
        self.assertEqual((p.face, p.mode, p.pause_z, p.floor, p.top), ("tilted", "open", None, None, None))
        self.assertTrue(_close(g.apply_dir(p.transform, (0, 0, 1)), n))
        depth = 3.2
        self.assertAlmostEqual(p.size[2], depth + pocket.OVERSHOOT)
        bottom = g.apply(p.transform, (0, 0, 0))
        self.assertTrue(_close(bottom, tuple(c - depth * k for c, k in zip((1, 2, 3), n))))
        self.assertAlmostEqual(g.det(p.transform), 1.0)

    def test_open_block_on_side(self):
        p = pocket.plan(req(insert=BLOCK, mode="open", point=(0, 5, 5), normal=(-1, 0, 0)), CTX)
        self.assertEqual(p.shape, "box")
        self.assertAlmostEqual(p.size[2], 2.2 + pocket.OVERSHOOT)


class Mesh(unittest.TestCase):
    def test_mesh_and_world_mesh(self):
        p = pocket.plan(req(), CTX)
        v, t = p.mesh()
        self.assertEqual(len(v), 2 * g.SEGMENTS + 2)
        world = p.world_mesh()[0]
        self.assertAlmostEqual(min(q[2] for q in world), p.floor)
        self.assertAlmostEqual(max(q[2] for q in world), p.top)


class Pauses(unittest.TestCase):
    def test_shared_heights_share_one_entry(self):
        a = pocket.plan(req(point=(5, 5, 20)), CTX)
        b = pocket.plan(req(point=(15, 5, 20)), CTX)
        c = pocket.plan(req(insert=NFC, point=(10, 15, 20), cover=0.6), CTX)
        o = pocket.plan(req(mode="open"), CTX)
        out, warnings = pocket.pauses([a, b, c, o], existing=())
        zs = [z for z, _ in out]
        self.assertEqual(zs, sorted(zs))
        by_z = dict(out)
        self.assertEqual(by_z[round(a.pause_z, 6)], "Embedder: insert 2 x 6x3 magnet")
        self.assertIn(round(c.pause_z, 6), by_z)
        self.assertEqual(warnings, ())

    def test_mixed_labels_in_one_entry(self):
        a = pocket.plan(req(point=(5, 5, 20)), CTX)
        b = pocket.plan(pocket.Request(presets.find("magnet-disc-5x3"), "embedded", (25, 5, 20), (0, 0, 1), 0, 1.0), CTX)
        out, _ = pocket.pauses([a, b], existing=())
        self.assertEqual(out, ((round(a.pause_z, 6), "Embedder: insert 1 x 6x3 magnet, 1 x 5x3 magnet"),))

    def test_existing_custom_gcode_at_the_same_layer_is_kept(self):
        a = pocket.plan(req(), CTX)
        out, warnings = pocket.pauses([a], existing=(a.pause_z + 0.00001,))
        self.assertEqual(out, ())
        self.assertEqual(warnings, (("existing_gcode_at_layer", round(a.pause_z, 6)),))

    def test_nfc_near_magnet(self):
        a = pocket.plan(req(point=(5, 5, 20)), CTX)
        near = pocket.plan(req(insert=NFC, point=(25, 5, 20), cover=0.6), CTX)
        far = pocket.plan(req(insert=NFC, point=(80, 5, 20), cover=0.6), CTX)
        self.assertEqual(pocket.proximity_warnings([a, near]), (("nfc_near_magnet", 0, 1),))
        self.assertEqual(pocket.proximity_warnings([a, far]), ())


def _close(a, b, eps=1e-6):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


if __name__ == "__main__":
    unittest.main()
