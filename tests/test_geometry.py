import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder")]
import geometry as g  # noqa: E402


def close(a, b, eps=1e-6):
    return all(abs(x - y) <= eps for x, y in zip(a, b)) and len(a) == len(b)


class Matrices(unittest.TestCase):
    def test_identity_mul_and_apply(self):
        t = g.translation(1, 2, 3)
        self.assertEqual(g.mul(g.IDENTITY, t), t)
        self.assertTrue(close(g.apply(t, (1, 1, 1)), (2, 3, 4)))
        r = g.rotation_z(90)
        self.assertTrue(close(g.apply(r, (1, 0, 0)), (0, 1, 0)))
        self.assertTrue(close(g.apply(g.mul(t, r), (1, 0, 0)), (1, 3, 3)))   # rotate first, then move
        self.assertTrue(close(g.apply_dir(g.mul(t, r), (1, 0, 0)), (0, 1, 0)))

    def test_det_and_inverse_general(self):
        m = g.mul(g.mul(g.translation(5, -3, 2), g.rotation_z(30)), g.scale(2, -1, 0.5))
        m = m[:1] + (m[1] + 0.3,) + m[2:]   # a shear too
        self.assertLess(g.det(m), 0)
        inv = g.inverse(m)
        self.assertTrue(close(g.mul(m, inv), g.IDENTITY))
        self.assertTrue(close(g.mul(inv, m), g.IDENTITY))
        with self.assertRaises(ValueError):
            g.inverse(g.scale(1, 0, 1))

    def test_3mf_transform_layout(self):
        # 3MF lists the matrix column by column: m00 m10 m20 m01 ... then the translation
        m = g.from_3mf("0 1 0 -1 0 0 0 0 1 10 20 30")
        self.assertTrue(close(g.apply(m, (1, 0, 0)), (10, 21, 30)))
        self.assertTrue(close(g.from_3mf(g.to_3mf(m)), m))
        self.assertEqual(g.from_3mf(None), g.IDENTITY)
        self.assertEqual(g.from_3mf(""), g.IDENTITY)
        self.assertEqual(g.to_3mf(g.translation(1, 2.5, 0)), "1 0 0 0 1 0 0 0 1 1 2.5 0")

    def test_config_matrix_is_row_major(self):
        m = g.mul(g.translation(1, 2, 3), g.rotation_z(90))
        text = g.to_config(m)
        self.assertEqual(text.split()[3], "1")
        self.assertTrue(close(g.from_config(text), m))
        self.assertTrue(close(g.from_config(g.to_config(m)), g.from_3mf(g.to_3mf(m))))

    def test_frame_maps_local_z_to_axis(self):
        for axis in ((0, 0, 1), (0, 0, -1), (1, 0, 0), (0, -1, 0), (0.6, 0, 0.8)):
            f = g.frame((1, 2, 3), axis, 0)
            self.assertAlmostEqual(g.det(f), 1.0)
            self.assertTrue(close(g.apply_dir(f, (0, 0, 1)), axis))
            self.assertTrue(close(g.apply(f, (0, 0, 0)), (1, 2, 3)))
        spun = g.frame((0, 0, 0), (0, 0, 1), 90)
        self.assertTrue(close(g.apply_dir(spun, (1, 0, 0)), (0, 1, 0)))

    def test_rigid_z(self):
        self.assertTrue(g.rigid_z(g.mul(g.translation(5, 6, 0), g.rotation_z(33))))
        self.assertFalse(g.rigid_z(g.scale(1, 1, 2)))
        self.assertFalse(g.rigid_z(g.frame((0, 0, 0), (1, 0, 0), 0)))
        self.assertFalse(g.rigid_z(g.scale(-1, 1, 1)))


class FaceCentre(unittest.TestCase):
    @staticmethod
    def flat(squares, z=0.0):
        """Unit squares (x, y) at height z, two triangles each, vertices not shared (as an STL would have them)."""
        pos, idx = [], []
        for x, y in squares:
            for a, b, c in (((x, y), (x + 1, y), (x + 1, y + 1)), ((x, y), (x + 1, y + 1), (x, y + 1))):
                idx += [len(pos) // 3 + k for k in range(3)]
                for px, py in (a, b, c):
                    pos += [px, py, z]
        return pos, idx

    def test_centre_of_the_joined_flat_face(self):
        pos, idx = self.flat([(0, 0), (1, 0), (2, 0), (5, 5)])
        self.assertTrue(close(g.face_centre(pos, idx, 0, (0, 0, 1)), (1.5, 0.5, 0)))
        self.assertTrue(close(g.face_centre(pos, idx, 7, (0, 0, 1)), (5.5, 5.5, 0)))   # a separate face

    def test_a_centre_off_the_face_is_none(self):
        ring = [(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)]
        pos, idx = self.flat(ring)
        self.assertIsNone(g.face_centre(pos, idx, 0, (0, 0, 1)))

    def test_other_planes_are_left_out(self):
        pos, idx = self.flat([(0, 0)])
        up, upi = self.flat([(1, 0)], z=1.0)
        pos, idx = pos + up, idx + [i + 6 for i in upi]
        self.assertTrue(close(g.face_centre(pos, idx, 0, (0, 0, 1)), (0.5, 0.5, 0)))


class Meshes(unittest.TestCase):
    def test_cylinder_is_circumscribed_and_closed(self):
        v, t = g.cylinder_mesh(6.0, 3.0)
        n = g.SEGMENTS
        self.assertEqual(len(v), 2 * n + 2)
        self.assertEqual(len(t), 4 * n)
        # flat-to-flat (twice the apothem) equals the nominal diameter
        r_vertex = math.hypot(v[0][0], v[0][1])
        self.assertAlmostEqual(2 * r_vertex * math.cos(math.pi / n), 6.0)
        self.assertEqual({p[2] for p in v}, {0.0, 3.0})
        self.assertTrue(_closed(t))
        self.assertGreater(_volume(v, t), 0)   # outward winding
        self.assertAlmostEqual(_volume(v, t), n * r_vertex ** 2 * math.sin(2 * math.pi / n) / 2 * 3.0, places=6)

    def test_hexagon_holds_a_disc_on_its_flats_and_vents_at_its_corners(self):
        v, t = g.hexagon_mesh(6.4, 3.2)
        self.assertEqual((len(v), len(t)), (14, 24))
        self.assertTrue(_closed(t))
        ring = v[:6]
        for x, y, _ in ring:
            self.assertAlmostEqual(math.hypot(x, y), 6.4 / 2 / math.cos(math.radians(30)))   # circumradius
        self.assertAlmostEqual(max(y for _, y, _ in ring), 3.2)        # flat to flat is the round pocket's diameter
        self.assertAlmostEqual(min(y for _, y, _ in ring), -3.2)
        # fixed orientation: two corners on local X, so two flats run parallel to it
        self.assertTrue(close(ring[0], (g.hexagon_corners(6.4) / 2, 0.0, 0.0)))
        self.assertAlmostEqual(g.hexagon_corners(6.4), 6.4 / math.cos(math.radians(30)))
        self.assertEqual(sorted(round(y, 9) for _, y, _ in ring), [-3.2, -3.2, 0.0, 0.0, 3.2, 3.2])
        self.assertAlmostEqual(_volume(v, t), 2 * math.sqrt(3) * 3.2 ** 2 * 3.2)   # 2 sqrt(3) apothem^2 * height
        self.assertEqual(g.hexagon_mesh(6.4, 3.2), (v, t))             # deterministic

    def test_vented_box_is_one_closed_solid_with_a_round_vent_on_each_corner(self):
        n = g.VENT_SEGMENTS
        v, t = g.vented_box_mesh(10.4, 5.4, 2.2, 0.5)
        self.assertTrue(_closed(t))
        self.assertEqual({p[2] for p in v}, {0.0, 2.2})
        sector = 0.5 ** 2 * math.sin(2 * math.pi / n) / 2              # one arc step of a vent
        self.assertAlmostEqual(_volume(v, t), (10.4 * 5.4 + 4 * (3 * n // 4) * sector) * 2.2)
        for cx in (-5.2, 5.2):
            for cy in (-2.7, 2.7):
                arc = [p for p in v if abs(math.hypot(p[0] - cx, p[1] - cy) - 0.5) < 1e-9]
                self.assertEqual(len(arc), 2 * (3 * n // 4 + 1), (cx, cy))           # 270 degrees outside the box
                self.assertTrue(any(close(p[:2], (cx + math.copysign(0.5, cx), cy)) for p in arc))
                self.assertTrue(any(close(p[:2], (cx, cy + math.copysign(0.5, cy))) for p in arc))
        self.assertAlmostEqual(max(p[0] for p in v), 5.7)
        self.assertAlmostEqual(min(p[1] for p in v), -3.2)
        self.assertFalse(_degenerate(v, t))

    def test_flush_vented_box_keeps_its_front_face_flat(self):
        n = g.VENT_SEGMENTS
        v, t = g.vented_box_mesh(6.4, 3.4, 6.2, 0.5, flush=True)
        self.assertTrue(_closed(t))
        self.assertAlmostEqual(min(p[1] for p in v), -1.7)              # nothing past the -Y face
        self.assertAlmostEqual(max(p[1] for p in v), 2.2)               # the back corners vent all round
        self.assertAlmostEqual(max(p[0] for p in v), 3.7)               # the front corners vent sideways
        sector = 0.5 ** 2 * math.sin(2 * math.pi / n) / 2
        self.assertAlmostEqual(_volume(v, t), (6.4 * 3.4 + (2 * 3 + 2) * (n // 4) * sector) * 6.2)
        self.assertFalse(_degenerate(v, t))

    def test_normal_and_tilt(self):
        self.assertTrue(close(g.triangle_normal((0, 0, 0), (1, 0, 0), (0, 1, 0)), (0, 0, 1)))
        with self.assertRaises(ValueError):
            g.triangle_normal((0, 0, 0), (1, 0, 0), (2, 0, 0))
        self.assertEqual(g.tilt((0, 0, 1)), "flat")
        self.assertEqual(g.tilt((0, 0, -1)), "flat")
        s4 = math.sin(math.radians(4))
        self.assertEqual(g.tilt((s4, 0, math.cos(math.radians(4)))), "flat")
        self.assertEqual(g.tilt((math.cos(math.radians(4)), 0, s4)), "side")
        self.assertEqual(g.tilt((1, 0, 0)), "side")
        self.assertEqual(g.tilt((0.7071, 0, 0.7071)), "tilted")
        s6 = math.sin(math.radians(6))
        self.assertEqual(g.tilt((s6, 0, math.cos(math.radians(6)))), "tilted")


def _degenerate(verts, tris):
    """Triangles without area (they would make a mesh OrcaSlicer repairs)."""
    def area(a, b, c):
        u, w = [q - p for p, q in zip(a, b)], [q - p for p, q in zip(a, c)]
        return math.sqrt((u[1] * w[2] - u[2] * w[1]) ** 2 + (u[2] * w[0] - u[0] * w[2]) ** 2 + (u[0] * w[1] - u[1] * w[0]) ** 2) / 2
    return [tri for tri in tris if area(*(verts[i] for i in tri)) < 1e-9]


def _closed(tris):
    edges = {}
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            edges[e] = edges.get(e, 0) + 1
    return all(edges.get((b, a)) == 1 for (a, b), n in edges.items() if n == 1) and all(n == 1 for n in edges.values())


def _volume(v, tris):
    total = 0.0
    for a, b, c in tris:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = v[a], v[b], v[c]
        total += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return total / 6


if __name__ == "__main__":
    unittest.main()
