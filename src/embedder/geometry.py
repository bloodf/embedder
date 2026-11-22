"""Small stdlib geometry: 4x4 matrices as 16-tuples (row-major, column vectors: p' = M p), 3MF and Orca config
transform strings, pocket meshes (hexagon, box with corner vents) and face classes. Free of `orca`."""

import math

SEGMENTS = 64               # sides of a round prism
VENT_SEGMENTS = 16          # sides of a full corner vent
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


def hexagon_corners(flat):
    """Corner-to-corner width of a regular hexagon that is `flat` across its flats."""
    return flat / math.cos(math.pi / 6)


def hexagon_mesh(flat, height, turned=False):
    """Closed hexagonal prism, z from 0 to height, `flat` across the flats. Two corners lie on X, so two flats run
    parallel to X at y = +-flat / 2: a disc of that diameter touches the six flats and the corners stay open.
    turned: a 30 degree turn, so two corners lie on Y and two flats cross X at x = +-flat / 2."""
    verts, tris = cylinder_mesh(flat, height, 6)
    if turned:
        verts = tuple(apply(rotation_z(30), v) for v in verts)
    return verts, tris


def vented_box_mesh(sx, sy, sz, r, flush=False, n=VENT_SEGMENTS):
    """Closed box centred on X and Y, z from 0 to sz, with a round vent of radius r centred on each corner: one solid,
    the outline of the box and the four circles pushed up from 0 to sz. flush: the two corners on the -Y face vent
    along X only, so that face stays flat. r must be under half the shorter side, so neighbouring vents stay apart."""
    hx, hy, q = sx / 2, sy / 2, n // 4
    pts, ring, rect, caps = [(0.0, 0.0)], [], [], []    # a layer's points, centre first; outline, box edge, cap triangles
    for k, (cx, cy) in enumerate(((hx, -hy), (hx, hy), (-hx, hy), (-hx, -hy))):
        lo, hi = (k - 2) * q, (k + 1) * q               # 270 degrees outside the box, in steps of 2 pi / n
        first = not (flush and k == 0)                   # does the arc start, and end, on the box's own edge?
        last = not (flush and k == 3)
        lo, hi = (lo if first else lo + 2 * q), (hi if last else hi - 2 * q)
        corner = len(pts)
        arc = list(range(corner + 1, corner + 2 + hi - lo))
        pts.append((cx, cy))
        pts += [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(lo, hi + 1)]
        ring += ([] if first else [corner]) + arc + ([] if last else [corner])
        rect += ([arc[0]] if first else []) + [corner] + ([arc[-1]] if last else [])
        caps += [(corner, a, b) for a, b in zip(arc, arc[1:])]
    caps += [(0, a, b) for a, b in zip(rect, rect[1:] + rect[:1])]
    m = len(pts)
    verts = [(x, y, 0.0) for x, y in pts] + [(x, y, float(sz)) for x, y in pts]
    tris = [(a, c, b) for a, b, c in caps] + [(m + a, m + b, m + c) for a, b, c in caps]
    for a, b in zip(ring, ring[1:] + ring[:1]):
        tris += [(a, b, m + b), (a, m + b, m + a)]
    return tuple(verts), tuple(tris)


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


def _inside_triangle(p, a, b, c, n, eps=1e-6):
    """True when p (in the triangle's plane) lies inside or on triangle abc, whose unit normal is n."""
    return all(_dot(n, _cross(tuple(q - o for o, q in zip(u, v)), tuple(q - o for o, q in zip(u, p)))) >= -eps
               for u, v in ((a, b), (b, c), (c, a)))


def face_centre(pos, idx, tri, normal, dist=1e-3, cos_tol=1 - 1e-4):
    """Area-weighted centre of the flat face around triangle `tri` (flat position and index lists): the triangles
    joined to it through shared edges that lie in its plane. None when that centre falls off the face (a ring, a U).
    ponytail: a linear pass over the mesh per call; index the faces once if very large meshes make placing slow."""
    n = normalize(normal)

    def corners(k):
        return [tuple(pos[3 * idx[3 * k + c] + a] for a in range(3)) for c in range(3)]

    plane = _dot(n, corners(tri)[0])
    flat, by_edge = {}, {}
    for k in range(len(idx) // 3):
        cs = corners(k)
        if any(abs(_dot(n, c) - plane) > dist for c in cs):
            continue
        try:
            nk = triangle_normal(*cs)
        except ValueError:
            continue
        if _dot(nk, n) < cos_tol:
            continue
        flat[k] = cs
        keys = [tuple(round(v, 4) for v in c) for c in cs]
        for e in ((keys[0], keys[1]), (keys[1], keys[2]), (keys[2], keys[0])):
            by_edge.setdefault(frozenset(e), []).append(k)
    if tri not in flat:
        return None
    face, todo = {tri}, [tri]
    while todo:
        cs = flat[todo.pop()]
        keys = [tuple(round(v, 4) for v in c) for c in cs]
        for e in ((keys[0], keys[1]), (keys[1], keys[2]), (keys[2], keys[0])):
            for k in by_edge[frozenset(e)]:
                if k not in face:
                    face.add(k)
                    todo.append(k)
    total, acc = 0.0, [0.0, 0.0, 0.0]
    for k in face:
        a, b, c = flat[k]
        area = math.sqrt(sum(v * v for v in _cross(tuple(q - p for p, q in zip(a, b)), tuple(q - p for p, q in zip(a, c))))) / 2
        total += area
        acc = [s + area * (a[i] + b[i] + c[i]) / 3 for i, s in enumerate(acc)]
    centre = tuple(v / total for v in acc)
    return centre if any(_inside_triangle(centre, *flat[k], n) for k in face) else None


def _scan_bottom_tris(parts, min_z, z_tol, max_nz, all_corners):
    out = []
    for part_j, pos, idx in parts:
        for t in range(len(idx) // 3):
            cs = [tuple(pos[3 * idx[3 * t + c] + a] for a in range(3)) for c in range(3)]
            on_bottom = all(abs(c[2] - min_z) <= z_tol for c in cs) if all_corners else (min(c[2] for c in cs) <= min_z + z_tol)
            if not on_bottom:
                continue
            try:
                n = triangle_normal(*cs)
            except ValueError:
                continue
            if n[2] <= max_nz:
                area = 0.5 * abs((cs[1][0] - cs[0][0]) * (cs[2][1] - cs[0][1]) - (cs[1][1] - cs[0][1]) * (cs[2][0] - cs[0][0]))
                if area > 1e-4 or not all_corners:
                    out.append((part_j, t, cs, area if all_corners else 1.0))
    return out


def bottom_triangles(parts):
    """Downward-facing bottom triangles `[(part_j, tri_t, corners, area_2d), ...]` across `(part_j, pos, idx)` tuples.
    Prefers flat bed-contact facets within 0.25 mm of Z_min; falls back to beveled bottom facets within 1.5 mm."""
    if not parts:
        return []
    min_z = min(min(pos[2::3]) for _, pos, _ in parts)
    return (_scan_bottom_tris(parts, min_z, 0.25, -0.92, True)
            or _scan_bottom_tris(parts, min_z, 1.5, -0.75, False))


def _pt_in_tri_2d(px, py, cs):
    (ax, ay, _), (bx, by, _), (cx, cy, _) = cs
    d1 = (px - bx) * (ay - by) - (ax - bx) * (py - by)
    d2 = (px - cx) * (by - cy) - (bx - cx) * (py - cy)
    d3 = (px - ax) * (cy - ay) - (cx - ax) * (py - ay)
    return not (((d1 < -1e-4) or (d2 < -1e-4) or (d3 < -1e-4)) and ((d1 > 1e-4) or (d2 > 1e-4) or (d3 > 1e-4)))


def _closest_on_seg_2d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 <= 1e-12:
        return ax, ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return ax + t * dx, ay + t * dy


def snap_to_bottom(tx, ty, down_tris, margin=0.0):
    """Snap a 2D target (tx, ty) onto the containing or nearest bottom triangle: (part_j, tri_t, [x, y, z]).
    When outside all triangles, pulls edge projections inward toward the triangle centroid by at least `margin`."""
    for j, t, cs, _ in down_tris:
        if _pt_in_tri_2d(tx, ty, cs):
            z = sum(c[2] for c in cs) / 3.0
            return j, t, [round(tx, 6), round(ty, 6), round(z, 6)]
    best_j, best_t, best_pt, best_d = down_tris[0][0], down_tris[0][1], [round(tx, 6), round(ty, 6), 0.0], 1e18
    for j, t, cs, _ in down_tris:
        z = sum(c[2] for c in cs) / 3.0
        tcx, tcy = sum(c[0] for c in cs) / 3.0, sum(c[1] for c in cs) / 3.0
        cands = [(tcx, tcy)]
        for k in range(3):
            a, b = cs[k], cs[(k + 1) % 3]
            qx, qy = _closest_on_seg_2d(tx, ty, a[0], a[1], b[0], b[1])
            dist_c = math.hypot(tcx - qx, tcy - qy)
            if dist_c > 1e-6:
                pull = min(0.95, max(0.08, min(dist_c, margin) / dist_c))
                cands.append((qx + pull * (tcx - qx), qy + pull * (tcy - qy)))
            else:
                cands.append((0.92 * qx + 0.08 * tcx, 0.92 * qy + 0.08 * tcy))
        for qx, qy in cands:
            d = math.hypot(qx - tx, qy - ty)
            if d < best_d:
                best_d, best_j, best_t, best_pt = d, j, t, [round(qx, 6), round(qy, 6), round(z, 6)]
    return best_j, best_t, best_pt
