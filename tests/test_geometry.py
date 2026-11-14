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

    def test_box(self):
        v, t = g.box_mesh(4, 2, 3)
        self.assertEqual(len(v), 8)
        self.assertEqual(len(t), 12)
        self.assertTrue(_closed(t))
        self.assertAlmostEqual(_volume(v, t), 24.0)
        self.assertEqual(min(p[0] for p in v), -2)
        self.assertEqual((min(p[2] for p in v), max(p[2] for p in v)), (0, 3))

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
