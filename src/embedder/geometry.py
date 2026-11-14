"""Small stdlib geometry: 4x4 matrices as 16-tuples (row-major, column vectors: p' = M p), 3MF and Orca config
transform strings, pocket meshes and face classes. Free of `orca`."""

import math

SEGMENTS = 64               # sides of a pocket cylinder
TILT_LIMIT_DEG = 5.0        # a face within this of horizontal/vertical counts as flat/side
IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def fmt(v):
    text = "%.9g" % v
    return "0" if text in ("-0", "0") else text


def mul(a, b):
    return tuple(sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4))


def apply(m, p):
    x, y, z = p
    return tuple(m[r * 4] * x + m[r * 4 + 1] * y + m[r * 4 + 2] * z + m[r * 4 + 3] for r in range(3))


def apply_dir(m, v):
    x, y, z = v
    return tuple(m[r * 4] * x + m[r * 4 + 1] * y + m[r * 4 + 2] * z for r in range(3))


def translation(x, y, z):
    return (1.0, 0.0, 0.0, float(x), 0.0, 1.0, 0.0, float(y), 0.0, 0.0, 1.0, float(z), 0.0, 0.0, 0.0, 1.0)


def scale(sx, sy, sz):
    return (float(sx), 0.0, 0.0, 0.0, 0.0, float(sy), 0.0, 0.0, 0.0, 0.0, float(sz), 0.0, 0.0, 0.0, 0.0, 1.0)


def rotation_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (c, -s, 0.0, 0.0, s, c, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def _cofactors(m):
    """The 4x4 cofactor matrix (row-major), from the 2x2 minors of the top and bottom row pairs."""
    a = [m[0:4], m[4:8], m[8:12], m[12:16]]
    s = [a[0][i] * a[1][j] - a[0][j] * a[1][i] for i, j in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))]
    c = [a[2][i] * a[3][j] - a[2][j] * a[3][i] for i, j in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))]
    (s0, s1, s2, s3, s4, s5), (c0, c1, c2, c3, c4, c5) = s, c
    return (
        a[1][1] * c5 - a[1][2] * c4 + a[1][3] * c3, -(a[1][0] * c5 - a[1][2] * c2 + a[1][3] * c1),
        a[1][0] * c4 - a[1][1] * c2 + a[1][3] * c0, -(a[1][0] * c3 - a[1][1] * c1 + a[1][2] * c0),
        -(a[0][1] * c5 - a[0][2] * c4 + a[0][3] * c3), a[0][0] * c5 - a[0][2] * c2 + a[0][3] * c1,
        -(a[0][0] * c4 - a[0][1] * c2 + a[0][3] * c0), a[0][0] * c3 - a[0][1] * c1 + a[0][2] * c0,
        a[3][1] * s5 - a[3][2] * s4 + a[3][3] * s3, -(a[3][0] * s5 - a[3][2] * s2 + a[3][3] * s1),
        a[3][0] * s4 - a[3][1] * s2 + a[3][3] * s0, -(a[3][0] * s3 - a[3][1] * s1 + a[3][2] * s0),
        -(a[2][1] * s5 - a[2][2] * s4 + a[2][3] * s3), a[2][0] * s5 - a[2][2] * s2 + a[2][3] * s1,
        -(a[2][0] * s4 - a[2][1] * s2 + a[2][3] * s0), a[2][0] * s3 - a[2][1] * s1 + a[2][2] * s0,
    )


def det(m):
    cof = _cofactors(m)
    return sum(m[i] * cof[i] for i in range(4))


def inverse(m):
    """General inverse (scale and shear included) as adjugate / determinant."""
    cof = _cofactors(m)
    d = sum(m[i] * cof[i] for i in range(4))
    if abs(d) < 1e-12:
        raise ValueError("singular matrix")
    return tuple(cof[c * 4 + r] / d for r in range(4) for c in range(4))


def from_3mf(text):
    """3MF transform "m00 m10 m20 m01 m11 m21 m02 m12 m22 tx ty tz" (column by column) -> mat4."""
    if not text or not text.strip():
        return IDENTITY
    a = [float(v) for v in text.split()]
    if len(a) != 12:
        raise ValueError("a 3MF transform has 12 numbers")
    return (a[0], a[3], a[6], a[9], a[1], a[4], a[7], a[10], a[2], a[5], a[8], a[11], 0.0, 0.0, 0.0, 1.0)


def to_3mf(m):
    return " ".join(fmt(v) for v in (m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10], m[3], m[7], m[11]))


def from_config(text):
    """Orca model_settings `matrix`: 16 numbers, row-major."""
    a = tuple(float(v) for v in text.split())
    if len(a) != 16:
        raise ValueError("a config matrix has 16 numbers")
    return a


def to_config(m):
    return " ".join(fmt(v) for v in m)


def normalize(v):
    length = math.sqrt(sum(c * c for c in v))
    if length < 1e-12:
        raise ValueError("zero-length vector")
    return tuple(c / length for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def frame(origin, axis, spin_deg):
    """A rotation + translation whose local +Z is `axis` and local origin is `origin`, spun about the axis.
    For a vertical axis the local X starts along world X, so a spin reads as a plain rotation about Z."""
    z = normalize(axis)
    helper = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = normalize(tuple(h - _dot(helper, z) * c for h, c in zip(helper, z)))
    y = _cross(z, x)
    c, s = math.cos(math.radians(spin_deg)), math.sin(math.radians(spin_deg))
    xs = tuple(c * a + s * b for a, b in zip(x, y))
    ys = tuple(-s * a + c * b for a, b in zip(x, y))
    ox, oy, oz = origin
    return (xs[0], ys[0], z[0], float(ox), xs[1], ys[1], z[1], float(oy), xs[2], ys[2], z[2], float(oz),
            0.0, 0.0, 0.0, 1.0)


def rigid_z(m, eps=1e-6):
    """True when the 3x3 part is a pure rotation about Z (no scale, mirror or tilt)."""
    c, s = m[0], m[4]
    expect = (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)
    got = (m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10])
    return abs(c * c + s * s - 1) < eps and all(abs(a - b) < eps for a, b in zip(got, expect))


def cylinder_mesh(diameter, height, n=SEGMENTS):
    """Closed n-gon prism, z from 0 to height, circumscribed: flat-to-flat equals `diameter` (never undersized)."""
    r = diameter / 2 / math.cos(math.pi / n)
    ring = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    verts = [(x, y, 0.0) for x, y in ring] + [(x, y, float(height)) for x, y in ring]
    verts += [(0.0, 0.0, 0.0), (0.0, 0.0, float(height))]
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [(i, j, n + j), (i, n + j, n + i), (2 * n, j, i), (2 * n + 1, n + i, n + j)]
    return tuple(verts), tuple(tris)


def box_mesh(sx, sy, sz):
    """Closed box centred on X and Y, z from 0 to sz."""
    hx, hy = sx / 2, sy / 2
    verts = tuple((float(x), float(y), float(z)) for z in (0, sz) for y in (-hy, hy) for x in (-hx, hx))
    tris = ((0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
            (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5))
    return verts, tris


def triangle_normal(a, b, c):
    """Unit normal by the right-hand rule (counter-clockwise = outward in 3MF)."""
    e1 = tuple(q - p for p, q in zip(a, b))
    e2 = tuple(q - p for p, q in zip(a, c))
    return normalize(_cross(e1, e2))


def tilt(normal):
    """'flat' (within 5 deg of +-Z), 'side' (within 5 deg of horizontal) or 'tilted'."""
    nz = abs(normalize(normal)[2])
    if nz >= math.cos(math.radians(TILT_LIMIT_DEG)):
        return "flat"
    if nz <= math.sin(math.radians(TILT_LIMIT_DEG)):
        return "side"
    return "tilted"
