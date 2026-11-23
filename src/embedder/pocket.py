"""Pocket rules: where the cavity goes, its size, the layer grid and the pause that seals the insert in.
All coordinates are millimetres in the plate frame (world Z = print Z). Free of `orca`."""

import math
from collections import Counter
from dataclasses import dataclass
from typing import NamedTuple

import geometry

EPS = 1e-6
OVERSHOOT = 1.0          # mm an open pocket reaches outside the surface, so the cut is clean
NEAR_MM = 10.0           # an NFC tag closer than this to a magnet may not read
THIN_COVER_LAYERS = 2
THIN_SIDE_WALL = 0.8     # mm; a side wall thinner than about two perimeters may show the insert
INSET = 0.05             # mm the containment probes sit inside the cavity's faces
VENT_DIAMETER = 1.0      # mm; the round vent on each corner of a box pocket, for trapped air and spare glue
VENT_SHARE = 0.45        # ...and never more than this share of the box's shorter side, so two vents stay apart
MODES = ("open", "embedded")
SHAPES = ("circle", "hexagon", "square", "rectangle")   # the pocket shapes a user may pick; a side slot is its own
PAUSE_PREFIX = "Embedder:"


class Blocked(ValueError):
    """The pocket cannot be made as asked; `code` is stable for the page."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Grid:
    """Layer tops: first + k * height (k >= 0); 0 is the bed."""
    first: float
    height: float

    def __post_init__(self):
        if not (self.first > 0 and self.height > 0 and math.isfinite(self.first + self.height)):
            raise ValueError("layer heights must be positive")

    def top(self, k):
        return round(self.first + k * self.height, 6)

    def snap_down(self, z):
        if z < self.first - EPS:
            return 0.0
        return self.top(math.floor((z - self.first) / self.height + EPS))

    def snap_up(self, z):
        if z <= EPS:
            return 0.0
        if z <= self.first + EPS:
            return round(self.first, 6)
        return self.top(math.ceil((z - self.first) / self.height - EPS))


class Context(NamedTuple):
    """What a plan needs from the project and the settings."""
    grid: Grid
    xy_clearance: float = 0.2
    z_clearance: float = 0.2
    block: str = None               # why embedded pockets are off for this object (session.py decides), or None
    instances_rigid: bool = True    # every instance differs only by a Z rotation and a move (both modes need it)


class Request(NamedTuple):
    insert: object                  # presets.Preset
    mode: str
    point: tuple                    # on the face, plate frame
    normal: tuple                   # outward, plate frame
    spin: float = 0.0               # degrees about the pocket axis (flat faces and open pockets)
    cover: float = 1.0              # mm of material over an embedded insert
    shape: str = None               # one of SHAPES, or None for the insert's default (default_shape)
    polarity: str = None            # optional "N" | "S" orientation note for magnets


@dataclass(frozen=True)
class Pocket:
    insert: object
    mode: str
    face: str                       # top | bottom | side | tilted
    shape: str                      # one of SHAPES, or slot (any insert on edge behind a wall)
    size: tuple                     # the fit (x, y, height): a circle's diameter or a hexagon's across-flats twice
    transform: tuple                # local mesh -> plate frame
    floor: float = None             # embedded only: cavity bottom and top, on the layer grid
    top: float = None
    pause_z: float = None
    cover: float = None
    warnings: tuple = ()
    turned: bool = False            # a hexagon turned 30 degrees: flats across local X (hexagon_turned)
    polarity: str = None            # optional "N" | "S" orientation note for magnets

    def mesh(self):
        """A circle is a round prism, no larger than the fit anywhere; a hexagon holds a disc on its six flats and vents
        at its six corners; a square or rectangle vents through a round relief on each corner. A slot is a box whose
        face towards the wall (local -Y) stays flat, so the wall keeps its cover."""
        sx, sy, sz = self.size
        if self.shape == "circle":
            return geometry.cylinder_mesh(sx, sz)
        if self.shape == "hexagon":
            return geometry.hexagon_mesh(sx, sz, self.turned)
        return geometry.vented_box_mesh(sx, sy, sz, vent_radius(sx, sy), flush=self.shape == "slot")

    def outer(self):
        """(x, y) the footprint spans in its own frame, corners and vents included."""
        verts = self.mesh()[0]
        return tuple(max(v[a] for v in verts) - min(v[a] for v in verts) for a in (0, 1))

    def world_mesh(self):
        verts, tris = self.mesh()
        return tuple(geometry.apply(self.transform, v) for v in verts), tris


def _face(normal, kind):
    if kind == "flat":
        return "top" if normal[2] > 0 else "bottom"
    return kind


def default_shape(insert):
    """The pocket an insert gets unless the user picks another: a disc a hexagon (it vents), a block a rectangle."""
    return "hexagon" if insert.shape == "disc" else "rectangle"


def fit(insert, shape, cxy):
    """(x, y) of the smallest pocket of `shape` that holds the insert with cxy clearance all round. A disc's circle,
    hexagon (across flats) and square are its diameter plus clearance; a block's circle is its diagonal, its hexagon
    is the smaller of the two that hold it (_hexagon_flats), its square takes the longer side."""
    l, w = insert.l + 2 * cxy, insert.w + 2 * cxy        # a disc: both its diameter
    disc = insert.shape == "disc"
    if shape == "circle":
        d = l if disc else math.hypot(l, w)
        return d, d
    if shape == "hexagon":
        f = l if disc else min(_hexagon_flats(l, w))
        return f, f
    if shape == "square":
        return max(l, w), max(l, w)
    return l, w


def _hexagon_flats(l, w):
    """Across-flats a hexagon needs to hold an l x w rectangle centred, length along X: (corners on X, flats across X).
    Corners on X: flats at y = +-f/2 and at 60 degrees, so f >= max(w, (sqrt(3) l + w) / 2); turned 30 degrees, flats
    at x = +-f/2: f >= max(l, (l + sqrt(3) w) / 2). Between them they cover every turn (tests.test_pocket sweeps it)."""
    return max(w, (math.sqrt(3) * l + w) / 2), max(l, (l + math.sqrt(3) * w) / 2)


def hexagon_turned(insert, cxy):
    """True when a block's hexagon is smaller turned (flats across X): any block but a long, thin one."""
    if insert.shape == "disc":
        return False
    on_x, turned = _hexagon_flats(insert.l + 2 * cxy, insert.w + 2 * cxy)
    return turned < on_x


def _shape(req):
    if req.shape is None:
        return default_shape(req.insert)
    if req.shape not in SHAPES:
        raise Blocked("bad_shape", str(req.shape))
    return req.shape


def vent_radius(sx, sy):
    return min(VENT_DIAMETER / 2, VENT_SHARE * min(sx, sy))


def _open(req, ctx, face):
    n = geometry.normalize(req.normal)
    depth = req.insert.t + ctx.z_clearance
    shape = _shape(req)
    sx, sy = fit(req.insert, shape, ctx.xy_clearance)
    origin = tuple(p - depth * k for p, k in zip(req.point, n))
    return Pocket(req.insert, "open", face, shape, (sx, sy, depth + OVERSHOOT),
                  geometry.frame(origin, n, req.spin), turned=shape == "hexagon" and hexagon_turned(req.insert, ctx.xy_clearance))


def _check_embedded(ctx, kind):
    if kind == "tilted":
        raise Blocked("tilted_face")
    if ctx.block:
        raise Blocked(ctx.block)


def check_pause(z, grid):
    if z < grid.first + grid.height - EPS:
        raise Blocked("pause_too_low", "the pause would come before the second layer")


def _cavity(floor, top):
    """Checks a snapped cavity: inside the part's height and with printed layers under it."""
    if floor < -EPS:
        raise Blocked("below_bed", "the pocket would reach below the bed")
    if floor < EPS:
        raise Blocked("no_floor", "no printed layer would sit under the pocket")
    return floor, top


def _flat_cavity(face, z, cover, height, grid):
    """Top face: the cavity top snaps down under the cover; bottom face: the floor snaps up over it. Either way
    the cover is at least the asked thickness and the cavity at least the insert's height."""
    if face == "top":
        if z - cover - height < -EPS:
            raise Blocked("below_bed", "the pocket would reach below the bed")
        top = grid.snap_down(z - cover)
        return _cavity(grid.snap_down(top - height), top)
    floor = grid.snap_up(z + cover)
    return _cavity(floor, grid.snap_up(floor + height))


def _embedded_flat(req, ctx, face):
    ins, grid = req.insert, ctx.grid
    height = ins.t + ctx.z_clearance
    z = req.point[2]
    floor, top = _flat_cavity(face, z, req.cover, height, grid)
    cover = round(z - top if face == "top" else floor - z, 6)
    shape = _shape(req)
    sx, sy = fit(ins, shape, ctx.xy_clearance)
    transform = geometry.frame((req.point[0], req.point[1], floor), (0, 0, 1), req.spin)
    return Pocket(ins, "embedded", face, shape, (sx, sy, top - floor), transform, floor, top, cover=cover,
                  turned=shape == "hexagon" and hexagon_turned(ins, ctx.xy_clearance))


def _embedded_side(req, ctx):
    """The insert stands on edge behind the wall: a vertical slot, dropped in from above, whatever shape was picked
    (a cavity seen from above, it has no other outline to give). Local -Y faces the wall."""
    _shape(req)
    ins, grid, c = req.insert, ctx.grid, ctx.xy_clearance
    nh = geometry.normalize((req.normal[0], req.normal[1], 0.0))
    width, depth = ins.l + 2 * c, ins.t + 2 * c
    height = (ins.l if ins.shape == "disc" else ins.w) + ctx.z_clearance
    nominal = req.point[2] - height / 2
    if nominal < -EPS:
        raise Blocked("below_bed", "the pocket would reach below the bed")
    floor = grid.snap_down(nominal)
    floor, top = _cavity(floor, grid.snap_up(floor + height))
    back = req.cover + depth / 2
    centre = (req.point[0] - nh[0] * back, req.point[1] - nh[1] * back, floor)
    along = math.degrees(math.atan2(nh[0], -nh[1]))   # the wall's tangent (-ny, nx) as an angle from X
    transform = geometry.frame(centre, (0, 0, 1), along)
    return Pocket(ins, "embedded", "side", "slot", (width, depth, top - floor), transform, floor, top, cover=req.cover)


def plan(req, ctx):
    """The pocket for one request, or Blocked."""
    if req.mode not in MODES:
        raise Blocked("bad_mode", str(req.mode))
    if not ctx.instances_rigid:
        raise Blocked("instances_differ", "the copies of this object differ by more than a turn about Z")
    kind = geometry.tilt(req.normal)
    face = _face(req.normal, kind)
    if req.mode == "open":
        return Pocket(**{**_open(req, ctx, face).__dict__, "polarity": req.polarity})
    _check_embedded(ctx, kind)
    p = _embedded_flat(req, ctx, face) if kind == "flat" else _embedded_side(req, ctx)
    pause_z = round(p.top + ctx.grid.height, 6)
    check_pause(pause_z, ctx.grid)
    limit = THIN_SIDE_WALL if p.face == "side" else THIN_COVER_LAYERS * ctx.grid.height
    thin = p.cover < limit - EPS
    return Pocket(**{**p.__dict__, "pause_z": pause_z, "polarity": req.polarity,
                     "warnings": ("thin_cover",) if thin else ()})


def pause_text(labels):
    counts = Counter(labels)
    return PAUSE_PREFIX + " insert " + ", ".join("%d x %s" % (n, label) for label, n in counts.items())


def pauses(pockets, existing, copies=None):
    """((top_z, extra), ...) sorted by height, one per height shared by embedded pockets, plus warnings for
    heights that already carry someone else's custom G-code (left alone, no Embedder pause added there).
    copies[i]: how many instances of pocket i's object print (a negative part cuts every instance)."""
    groups = {}
    for i, p in enumerate(pockets):
        if p.pause_z is not None:
            n = copies[i] if copies else 1
            label = "%s (%s up)" % (p.insert.label, p.polarity) if p.polarity else p.insert.label
            groups.setdefault(round(p.pause_z, 6), []).extend([label] * n)
    taken = [round(z, 6) for z in existing]
    out, warnings = [], []
    for z in sorted(groups):
        if any(abs(z - e) < 1e-3 for e in taken):
            warnings.append(("existing_gcode_at_layer", z))
        else:
            out.append((z, pause_text(groups[z])))
    return tuple(out), tuple(warnings)


def _reach(p):
    """How far the pocket reaches from its centre: a circle's radius, else half the diagonal of its footprint (a
    hexagon's corners, a box's vents), so a warning about nearness never comes short."""
    centre = geometry.apply(p.transform, (0, 0, 0))
    return centre, p.size[0] / 2 if p.shape == "circle" else math.hypot(*p.outer()) / 2


def proximity_warnings(pockets):
    """(("nfc_near_magnet", i, j), ...) for every NFC pocket within NEAR_MM of a magnet pocket."""
    out = []
    for i, a in enumerate(pockets):
        for j in range(i + 1, len(pockets)):
            b = pockets[j]
            if {a.insert.kind, b.insert.kind} != {"magnet", "nfc"}:
                continue
            (ca, ra), (cb, rb) = _reach(a), _reach(b)
            if math.dist(ca, cb) - ra - rb < NEAR_MM:
                out.append(("nfc_near_magnet", i, j))
    return tuple(out)


# ---------------------------------------------------------------- containment

def _rim(p):
    """Local (x, y) points INSET inside the cavity's outline, at its extremes: twelve around a circle; a hexagon's
    corners and the middle of its flats; a box's edge middles and, on each corner, where the vent reaches furthest
    along X, along Y and between."""
    sx, sy, _ = p.size
    if p.shape == "circle":
        return [((sx / 2 - INSET) * math.cos(k * math.pi / 6), (sx / 2 - INSET) * math.sin(k * math.pi / 6)) for k in range(12)]
    if p.shape == "hexagon":
        radius = (geometry.hexagon_corners(sx) / 2 - INSET, sx / 2 - INSET)
        r = (lambda k: radius[(k + 1) % 2]) if p.turned else (lambda k: radius[k % 2])   # turned: corners on Y
        return [(r(k) * math.cos(k * math.pi / 6), r(k) * math.sin(k * math.pi / 6)) for k in range(12)]
    hx, hy, r = sx / 2, sy / 2, vent_radius(sx, sy) - INSET
    out = [(hx - INSET, 0.0), (INSET - hx, 0.0), (0.0, hy - INSET), (0.0, INSET - hy)]
    for gx, gy in ((1, -1), (1, 1), (-1, 1), (-1, -1)):
        if p.shape == "slot" and gy < 0:     # towards the wall the vent only reaches along X
            reach = ((gx * r, INSET),)
        else:
            reach = ((gx * r, 0.0), (0.0, gy * r), (gx * r * math.sqrt(0.5), gy * r * math.sqrt(0.5)))
        out += [(gx * hx + dx, gy * hy + dy) for dx, dy in reach]
    return out


def _probes(p):
    """Plate (x, y) columns through the cavity: its centre and its rim."""
    return [geometry.apply(p.transform, (x, y, 0.0))[:2] for x, y in [(0.0, 0.0)] + _rim(p)]


def _near_tris(p, pos, idx):
    """Precomputed XY-bounded triangles whose XY box overlaps the cavity's (one pass),
    so each probe only computes barycentric coordinates for triangles covering (x, y).
    ponytail: linear scan per plan; add a per-part grid index if very large meshes make placing slow."""
    corners = [geometry.apply(p.transform, (x, y, 0.0)) for x in (-p.size[0], p.size[0]) for y in (-p.size[1], p.size[1])]
    x0, x1 = min(c[0] for c in corners), max(c[0] for c in corners)
    y0, y1 = min(c[1] for c in corners), max(c[1] for c in corners)
    out = []
    for k in range(0, len(idx), 3):
        a, b, c = idx[k] * 3, idx[k + 1] * 3, idx[k + 2] * 3
        ax, bx, cx = pos[a], pos[b], pos[c]
        if max(ax, bx, cx) < x0 or min(ax, bx, cx) > x1:
            continue
        ay, by, cy = pos[a + 1], pos[b + 1], pos[c + 1]
        if max(ay, by, cy) < y0 or min(ay, by, cy) > y1:
            continue
        d = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(d) < 1e-12:
            continue
        out.append((ax, ay, pos[a + 2], bx, by, pos[b + 2], cx, cy, pos[c + 2], d,
                    min(ax, bx, cx), max(ax, bx, cx), min(ay, by, cy), max(ay, by, cy)))
    return out


def _crossings_near(x, y, tris):
    """Heights where the vertical line through (x, y) crosses the prefiltered triangles."""
    out = []
    for ax, ay, az, bx, by, bz, cx, cy, cz, d, minx, maxx, miny, maxy in tris:
        if x < minx or x > maxx or y < miny or y > maxy:
            continue
        u = ((bx - x) * (cy - y) - (cx - x) * (by - y)) / d
        v = ((cx - x) * (ay - y) - (ax - x) * (cy - y)) / d
        if u >= 0 and v >= 0 and (1 - u - v) >= 0:
            out.append(u * az + v * bz + (1 - u - v) * cz)
    return sorted(out)


def _inside(z, crossings):
    return sum(1 for c in crossings if c > z) % 2 == 1


def breaks_surface(p, pos, idx):
    """True when an embedded cavity leaves the part (pos/idx: the part's plate-frame mesh). Open pockets are open
    by design and are not checked. Probes sit slightly off-axis so a ray never runs along an edge."""
    if p.mode != "embedded":
        return False
    jitter = 1.7e-4
    tris = _near_tris(p, pos, idx)
    if p.face == "side":     # a slot only has to stay inside the part; a flat cavity also needs its floor and its cover
        heights = (p.floor + INSET, p.top - INSET)
    else:
        heights = ((p.floor + p.top) / 2, p.top + INSET, p.floor - INSET)
    for x, y in _probes(p):
        cross = _crossings_near(x + jitter, y + jitter, tris)
        if not all(_inside(z, cross) for z in heights):
            return True
    return False


MAGNET_GRADE_FACTORS = {"N35": 1.0, "N42": 1.18, "N52": 1.42, "ferrite": 0.16}
FRIDGE_SURFACE_FACTORS = {"steel": 1.0, "stainless": 0.45, "board": 0.30}
FILAMENT_DENSITIES = {
    "PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "PC": 1.20,
    "TPU": 1.21, "PA": 1.14, "NYLON": 1.14, "PET": 1.38, "HIPS": 1.04, "PVA": 1.23,
}


def filament_density(raw_density=None, filament_type=None):
    """Density in g/cm^3 from project_settings `filament_density`, else standard table by `filament_type`, else PLA (1.24)."""
    if isinstance(raw_density, list):
        raw_density = raw_density[0] if raw_density else None
    if isinstance(filament_type, list):
        filament_type = filament_type[0] if filament_type else None
    if raw_density is not None:
        try:
            d = float(str(raw_density).strip())
            if 0.2 <= d <= 10.0:
                return d
        except (ValueError, TypeError):
            pass
    ft = str(filament_type or "").strip().upper()
    for key, val in FILAMENT_DENSITIES.items():
        if ft == key or ft.startswith(key + "-") or ft.startswith(key + " "):
            return val
    return 1.24


def magnet_shear_hold_n(insert, cover_mm, grade="N35", surface="steel"):
    """Estimated vertical shear hold (Newtons) for one magnet against a vertical steel/stainless/board surface."""
    area = math.pi * (insert.l * 0.5) ** 2 if insert.shape == "disc" else insert.l * insert.w
    r = math.sqrt(area / math.pi)
    t = insert.t
    g = max(0.0, float(cover_mm)) + 0.15   # 0.15 mm typical paint/coating gap
    b_rel = (g + t) / math.hypot(g + t, r) - g / math.hypot(g, r)
    f_pull = 0.58 * area * (b_rel * b_rel) * MAGNET_GRADE_FACTORS.get(grade, 1.0) * FRIDGE_SURFACE_FACTORS.get(surface, 1.0)
    return 0.22 * f_pull


def required_fridge_magnets(volume_mm3, z_com_mm, span_mm, insert, cover_mm, infill_pct=15.0, grade="N35", surface="steel", density_g_cm3=1.24):
    """Minimum magnet count for a 2.5x safety factor against sliding and peeling on a vertical fridge door."""
    fill = min(1.0, max(0.15, infill_pct / 100.0 + 0.20))
    mass_kg = (max(0.0, volume_mm3) / 1000.0) * max(0.2, float(density_g_cm3)) * fill / 1000.0
    peel = 1.0 + 0.5 * max(0.0, z_com_mm) / max(10.0, span_mm)
    req_n = 2.5 * (mass_kg * 9.81) * peel
    hold_n = max(1e-6, magnet_shear_hold_n(insert, cover_mm, grade, surface))
    return max(1, math.ceil(req_n / hold_n)), hold_n, req_n


def _is_prime(n):
    if n < 2:
        return False
    return all(n % d != 0 for d in range(2, math.isqrt(n) + 1))


def _grid_dims(count, max_cols, max_rows, span_x, span_y):
    """Factor pair (cols, rows) for `count` that fits in (max_cols, max_rows) and best matches span_x / span_y."""
    best, best_score = None, 1e18
    aspect = span_x / max(1.0, span_y)
    for rows in range(1, min(count, max_rows) + 1):
        if count % rows != 0:
            continue
        cols = count // rows
        if cols > max_cols:
            continue
        score = abs(math.log((cols / rows) / aspect))
        if score < best_score:
            best, best_score = (cols, rows), score
    return best


def fridge_targets(down_tris, insert, xy_clearance, raw_count="auto", spread=0.28, needed_count=1):
    """Symmetric 2D target centres `[(tx, ty), ...]` across the bottom footprint `down_tris`."""
    xs = [c[0] for _, _, cs, _ in down_tris for c in cs]
    ys = [c[1] for _, _, cs, _ in down_tris for c in cs]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)
    cx_sym = 0.5 * (min_x + max_x)
    cy_sym = 0.5 * (min_y + max_y)
    base_area = sum(a for _, _, _, a in down_tris)

    pocket_r = 0.5 * max(insert.l, insert.w) + xy_clearance
    req_margin = pocket_r + 1.2
    min_sep = max(12.0, 4.4 * pocket_r)
    max_cols = 1 if span_x < min_sep + 2 * req_margin else 1 + int((span_x - 2 * req_margin) // min_sep)
    max_rows = 1 if span_y < min_sep + 2 * req_margin else 1 + int((span_y - 2 * req_margin) // min_sep)
    max_fit = max_cols * max_rows

    if raw_count == "auto" or raw_count is None:
        if base_area >= 2200.0 and max_cols >= 2 and max_rows >= 2:
            footprint_count = 4
        elif (base_area >= 480.0 or max(span_x, span_y) >= 1.35 * min_sep) and max(max_cols, max_rows) >= 2:
            footprint_count = 2
        else:
            footprint_count = 1
        n = max(footprint_count, int(needed_count))
        if n >= 3 and _is_prime(n):
            n += 1
        target_count = min(max_fit, n)
        dims = _grid_dims(target_count, max_cols, max_rows, span_x, span_y)
        while dims is None and target_count < max_fit:
            target_count += 1
            if target_count >= 3 and _is_prime(target_count):
                continue
            dims = _grid_dims(target_count, max_cols, max_rows, span_x, span_y)
        if dims is None:
            dims = (max_cols, max_rows)
            target_count = max_fit
    else:
        target_count = int(raw_count)
        dims = None if target_count == 3 else _grid_dims(target_count, max(target_count, max_cols), max(target_count, max_rows), span_x, span_y)

    max_dx = max(0.0, 0.5 * span_x - req_margin)
    max_dy = max(0.0, 0.5 * span_y - req_margin)
    if target_count == 3 and dims is None:
        off_x = min(max_dx, max(0.5 * min_sep if max_dx >= 0.5 * min_sep else max_dx, spread * span_x))
        off_y = min(max_dy, max(0.5 * min_sep if max_dy >= 0.5 * min_sep else max_dy, spread * span_y))
        if span_x >= span_y:
            return [(cx_sym - off_x, cy_sym - 0.85 * off_y),
                    (cx_sym + off_x, cy_sym - 0.85 * off_y),
                    (cx_sym, cy_sym + 0.90 * off_y)]
        return [(cx_sym - 0.85 * off_x, cy_sym - off_y),
                (cx_sym - 0.85 * off_x, cy_sym + off_y),
                (cx_sym + 0.90 * off_x, cy_sym)]

    cols, rows = dims or (1, 1)
    if cols <= 1:
        gx = [cx_sym]
    else:
        min_half_x = 0.5 * (cols - 1) * min_sep
        off_x = min(max_dx, max(min_half_x if max_dx >= min_half_x else max_dx, spread * span_x))
        gx = [cx_sym - off_x + (2.0 * off_x * i) / (cols - 1) for i in range(cols)]
    if rows <= 1:
        gy = [cy_sym]
    else:
        min_half_y = 0.5 * (rows - 1) * min_sep
        off_y = min(max_dy, max(min_half_y if max_dy >= min_half_y else max_dy, spread * span_y))
        gy = [cy_sym - off_y + (2.0 * off_y * j) / (rows - 1) for j in range(rows)]
    return [(x, y) for y in gy for x in gx]
