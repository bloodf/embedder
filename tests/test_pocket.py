import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder"), os.path.join(ROOT, "tests")]
import fixtures  # noqa: E402
import geometry as g  # noqa: E402
import pocket  # noqa: E402
import presets  # noqa: E402

MAG = presets.find("magnet-disc-6x3")
BLOCK = presets.find("magnet-block-10x5x2")
NFC = presets.find("nfc-sticker-25")
GRID = pocket.Grid(0.2, 0.2)
CTX = pocket.Context(grid=GRID, xy_clearance=0.2, z_clearance=0.2)
MODES = pocket.MODES


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
        self.assertEqual((p.face, p.shape, p.mode), ("top", "hexagon", "embedded"))
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
        self.assertEqual((p.face, p.shape), ("side", "slot"))
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
            "by_object": (req(), CTX._replace(block="by_object")),
            "instances_other_plate": (req(), CTX._replace(block="instances_other_plate")),
            "instances_differ": (req(), CTX._replace(instances_rigid=False)),
            "no_floor": (req(point=(0, 0, 4.4)), CTX._replace(grid=pocket.Grid(0.3, 0.2))),
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

    def test_no_material_under_the_cavity_is_blocked(self):
        for r in (req(insert=NFC, point=(0, 0, 0), normal=(0, 0, -1), cover=0.0),
                  req(point=(20, 10, 3.2), normal=(1, 0, 0))):
            with self.assertRaises(pocket.Blocked) as cm:
                pocket.plan(r, CTX)
            self.assertEqual(cm.exception.code, "no_floor")

    def test_actual_cover_is_never_thinner_than_asked(self):
        grid = pocket.Grid(0.3, 0.12)
        ctx = pocket.Context(grid=grid)
        for z, face in ((9.87, (0, 0, 1)), (0.0, (0, 0, -1))):
            p = pocket.plan(req(point=(0, 0, z), normal=face, cover=1.0), ctx)
            self.assertGreaterEqual(p.cover, 1.0 - 1e-9, face)
            self.assertGreaterEqual(p.top - p.floor, 3.2 - 1e-9, face)

    def test_side_thin_cover_is_a_fixed_wall(self):
        thin = pocket.plan(req(point=(20, 10, 10), normal=(1, 0, 0), cover=0.7), CTX)
        thick = pocket.plan(req(point=(20, 10, 10), normal=(1, 0, 0), cover=0.9), CTX)
        self.assertEqual((thin.warnings, thick.warnings), (("thin_cover",), ()))

    def test_bad_mode(self):
        with self.assertRaises(pocket.Blocked) as cm:
            pocket.plan(req(mode="sideways"), CTX)
        self.assertEqual(cm.exception.code, "bad_mode")


class Open(unittest.TestCase):
    def test_instances_differ_blocks_open_too(self):
        with self.assertRaises(pocket.Blocked) as cm:
            pocket.plan(req(mode="open"), CTX._replace(instances_rigid=False))
        self.assertEqual(cm.exception.code, "instances_differ")

    def test_open_on_tilted_face_follows_the_normal_and_overshoots(self):
        n = (0.6, 0, 0.8)
        p = pocket.plan(req(mode="open", point=(1, 2, 3), normal=n, spin=10), CTX._replace(block="by_object"))
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
        self.assertEqual((v, t), g.hexagon_mesh(6.4, p.top - p.floor))
        world = p.world_mesh()[0]
        self.assertAlmostEqual(min(q[2] for q in world), p.floor)
        self.assertAlmostEqual(max(q[2] for q in world), p.top)

    def test_a_disc_gets_a_hexagon_as_wide_across_the_flats_as_the_round_pocket_was(self):
        for mode, insert in (("embedded", MAG), ("open", MAG), ("embedded", NFC), ("open", NFC)):
            p = pocket.plan(req(insert=insert, mode=mode, cover=0.6), CTX)
            self.assertEqual(p.shape, "hexagon", (mode, insert.label))
            self.assertAlmostEqual(p.size[0], insert.d + 0.4)
            xs, ys = [q[0] for q in p.mesh()[0]], [q[1] for q in p.mesh()[0]]
            self.assertAlmostEqual(max(ys) - min(ys), insert.d + 0.4)                      # the flats hold the disc
            self.assertAlmostEqual(max(xs) - min(xs), (insert.d + 0.4) / math.cos(math.radians(30)))   # the corners vent
            self.assertTrue(_close(p.outer(), ((insert.d + 0.4) / math.cos(math.radians(30)), insert.d + 0.4)))

    def test_the_hexagon_turns_with_the_spin(self):
        p = pocket.plan(req(spin=30), CTX)
        world = p.world_mesh()[0]
        self.assertAlmostEqual(max(q[1] for q in world) - 10, 3.2 / math.cos(math.radians(30)))   # a corner now points along Y

    def test_a_block_gets_a_box_of_the_same_size_with_a_vent_on_each_corner(self):
        for mode in MODES:
            p = pocket.plan(req(insert=BLOCK, mode=mode), CTX)
            self.assertEqual((p.shape, p.size[:2]), ("box", (10.4, 5.4)), mode)
            self.assertEqual(p.mesh(), g.vented_box_mesh(10.4, 5.4, p.size[2], pocket.VENT_DIAMETER / 2))
            self.assertTrue(_close(p.outer(), (10.4 + pocket.VENT_DIAMETER, 5.4 + pocket.VENT_DIAMETER)), mode)
        self.assertEqual(pocket.VENT_DIAMETER, 1.0)

    def test_vents_shrink_on_a_box_too_narrow_for_them(self):
        thin = presets.resolve({"custom": {"kind": "nfc", "shape": "block", "l": 30, "w": 0.4, "t": 1}}, [])
        p = pocket.plan(req(insert=thin, mode="open"), CTX)
        r = pocket.vent_radius(*p.size[:2])
        self.assertLess(2 * r, 0.8)                     # the vents of the two near corners stay apart
        self.assertEqual(p.mesh(), g.vented_box_mesh(30.4, 0.8, p.size[2], r))

    def test_a_side_slot_vents_at_its_corners_and_keeps_the_wall_whole(self):
        for insert in (MAG, BLOCK):
            p = pocket.plan(req(insert=insert, point=(20, 10, 10), normal=(1, 0, 0), cover=1.0), CTX)
            self.assertEqual(p.shape, "slot")
            world = p.world_mesh()[0]
            self.assertAlmostEqual(max(q[0] for q in world), 19.0)                       # 1 mm of wall, as before the vents
            self.assertAlmostEqual(max(q[1] for q in world) - min(q[1] for q in world), p.size[0] + pocket.VENT_DIAMETER)
            self.assertAlmostEqual(min(q[0] for q in world), 19.0 - p.size[1] - pocket.VENT_DIAMETER / 2)
            self.assertAlmostEqual(p.cover, 1.0)
            self.assertEqual(p.warnings, ())


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

    def test_copies_count_every_instance(self):
        a = pocket.plan(req(point=(5, 5, 20)), CTX)
        out, _ = pocket.pauses([a], existing=(), copies=[3])
        self.assertEqual(out, ((round(a.pause_z, 6), "Embedder: insert 3 x 6x3 magnet"),))

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


class Containment(unittest.TestCase):
    """The cavity must stay inside the part: cube 20 mm at (100, 100, 0)."""
    MESH = None

    @classmethod
    def setUpClass(cls):
        verts, tris = fixtures.box(20, 20, 20, 100, 100, 0)
        cls.pos = [c for v in verts for c in v]
        cls.idx = [i for t in tris for i in t]

    def breaks(self, r):
        return pocket.breaks_surface(pocket.plan(r, CTX), self.pos, self.idx)

    def test_inside(self):
        self.assertFalse(self.breaks(req(point=(110, 110, 20))))
        self.assertFalse(self.breaks(req(point=(120, 110, 10), normal=(1, 0, 0))))
        self.assertFalse(self.breaks(req(point=(110, 110, 0), normal=(0, 0, -1))))

    def test_a_hexagon_corner_through_a_thin_wall_is_reported(self):
        """The flats are 3.2 mm from the centre and the corners 3.7: at 3.5 mm from the wall only a corner leaves."""
        self.assertTrue(self.breaks(req(point=(103.5, 110, 20))))               # a corner points at the wall
        self.assertFalse(self.breaks(req(point=(103.5, 110, 20), spin=30)))     # turned: a flat faces it
        self.assertFalse(self.breaks(req(point=(104, 110, 20))))
        self.assertTrue(self.breaks(req(point=(110, 116.6, 20), spin=90)))      # and so does any other corner
        self.assertFalse(self.breaks(req(point=(110, 116.6, 20))))

    def test_a_vent_through_a_thin_wall_is_reported(self):
        """A 10.4 x 5.4 box 0.3 mm from the wall: the box stays inside, its corner vents (0.5 mm) do not."""
        self.assertTrue(self.breaks(req(insert=BLOCK, point=(105.5, 110, 20))))
        self.assertFalse(self.breaks(req(insert=BLOCK, point=(105.8, 110, 20))))
        self.assertTrue(self.breaks(req(insert=BLOCK, point=(110, 103, 20))))
        self.assertFalse(self.breaks(req(insert=BLOCK, point=(110, 103.3, 20))))

    def test_a_slot_vent_past_the_end_of_the_wall_is_reported(self):
        """The slot is 6.4 mm along the wall and its vents reach 0.5 mm further; behind it they reach 0.5 mm deeper."""
        self.assertTrue(self.breaks(req(point=(120, 103.5, 10), normal=(1, 0, 0))))
        self.assertFalse(self.breaks(req(point=(120, 103.8, 10), normal=(1, 0, 0))))
        thin = fixtures.box(4.7, 20, 20, 100, 100, 0)                           # 1 mm wall, 3.4 mm slot, 0.3 mm left behind it
        pos, idx = [c for v in thin[0] for c in v], [i for t in thin[1] for i in t]
        slot = pocket.plan(req(point=(104.7, 110, 10), normal=(1, 0, 0)), CTX)
        self.assertTrue(pocket.breaks_surface(slot, pos, idx))

    def test_breaks_through(self):
        self.assertTrue(self.breaks(req(point=(101, 110, 20))))              # rim leaves the side wall
        self.assertTrue(self.breaks(req(point=(120, 110, 19), normal=(1, 0, 0))))    # slot above the part
        self.assertTrue(self.breaks(req(point=(120, 101, 10), normal=(1, 0, 0))))     # slot past the corner

    def test_open_pockets_are_not_checked(self):
        self.assertFalse(self.breaks(req(mode="open", point=(101, 110, 20))))


def _close(a, b, eps=1e-6):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


if __name__ == "__main__":
    unittest.main()
