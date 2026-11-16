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


@dataclass(frozen=True)
class Pocket:
    insert: object
    mode: str
    face: str                       # top | bottom | side | tilted
    shape: str                      # hexagon (a disc lying flat) | box (a block) | slot (any insert on edge behind a wall)
    size: tuple                     # the fit: (across flats, across flats, height) or (x, y, height) of the local mesh
    transform: tuple                # local mesh -> plate frame
    floor: float = None             # embedded only: cavity bottom and top, on the layer grid
    top: float = None
    pause_z: float = None
    cover: float = None
    warnings: tuple = ()

    def mesh(self):
        """A hexagon holds a disc on its six flats and vents at its six corners; a box vents through a round relief on
        each corner. A slot is a box whose face towards the wall (local -Y) stays flat, so the wall keeps its cover."""
        sx, sy, sz = self.size
        if self.shape == "hexagon":
            return geometry.hexagon_mesh(sx, sz)
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


def _footprint(insert, cxy):
    return insert.l + 2 * cxy, insert.w + 2 * cxy


def _shape(insert):
    return "hexagon" if insert.shape == "disc" else "box"


def vent_radius(sx, sy):
    return min(VENT_DIAMETER / 2, VENT_SHARE * min(sx, sy))


def _open(req, ctx, face):
    n = geometry.normalize(req.normal)
    depth = req.insert.t + ctx.z_clearance
    sx, sy = _footprint(req.insert, ctx.xy_clearance)
    origin = tuple(p - depth * k for p, k in zip(req.point, n))
    return Pocket(req.insert, "open", face, _shape(req.insert), (sx, sy, depth + OVERSHOOT),
                  geometry.frame(origin, n, req.spin))


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
    sx, sy = _footprint(ins, ctx.xy_clearance)
    transform = geometry.frame((req.point[0], req.point[1], floor), (0, 0, 1), req.spin)
    return Pocket(ins, "embedded", face, _shape(ins), (sx, sy, top - floor), transform, floor, top, cover=cover)


def _embedded_side(req, ctx):
    """The insert stands on edge behind the wall: a vertical slot, dropped in from above. Local -Y faces the wall."""
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
        return _open(req, ctx, face)
    _check_embedded(ctx, kind)
    p = _embedded_flat(req, ctx, face) if kind == "flat" else _embedded_side(req, ctx)
    pause_z = round(p.top + ctx.grid.height, 6)
    check_pause(pause_z, ctx.grid)
    limit = THIN_SIDE_WALL if p.face == "side" else THIN_COVER_LAYERS * ctx.grid.height
    thin = p.cover < limit - EPS
    return Pocket(**{**p.__dict__, "pause_z": pause_z, "warnings": ("thin_cover",) if thin else ()})


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
            groups.setdefault(round(p.pause_z, 6), []).extend([p.insert.label] * n)
    taken = [round(z, 6) for z in existing]
    out, warnings = [], []
    for z in sorted(groups):
        if any(abs(z - e) < 1e-3 for e in taken):
            warnings.append(("existing_gcode_at_layer", z))
        else:
            out.append((z, pause_text(groups[z])))
    return tuple(out), tuple(warnings)


def _reach(p):
    """Where the insert can be: the fit, not the hexagon's corners or a box's vents, which hold only air."""
    centre = geometry.apply(p.transform, (0, 0, 0))
    return centre, max(p.size[0], p.size[1]) / 2


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
    """Local (x, y) points INSET inside the cavity's outline, at its extremes: a hexagon's corners and the middle of its
    flats; a box's edge middles and, on each corner, where the vent reaches furthest along X, along Y and between."""
    sx, sy, _ = p.size
    if p.shape == "hexagon":
        radius = (geometry.hexagon_corners(sx) / 2 - INSET, sx / 2 - INSET)
        return [(radius[k % 2] * math.cos(k * math.pi / 6), radius[k % 2] * math.sin(k * math.pi / 6)) for k in range(12)]
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


def _crossings(x, y, pos, idx):
    """Heights where the vertical line through (x, y) crosses the mesh."""
    out = []
    for k in range(0, len(idx), 3):
        a, b, c = idx[k] * 3, idx[k + 1] * 3, idx[k + 2] * 3
        ax, ay, bx, by, cx, cy = pos[a], pos[a + 1], pos[b], pos[b + 1], pos[c], pos[c + 1]
        d = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(d) < 1e-12:
            continue
        u = ((bx - x) * (cy - y) - (cx - x) * (by - y)) / d
        v = ((cx - x) * (ay - y) - (ax - x) * (cy - y)) / d
        w = 1 - u - v
        if u >= 0 and v >= 0 and w >= 0:
            out.append(u * pos[a + 2] + v * pos[b + 2] + w * pos[c + 2])
    return sorted(out)


def _near(p, pos, idx):
    """The triangles whose XY box overlaps the cavity's (one pass), so each probe tests only those.
    ponytail: linear scan per plan; add a per-part grid index if very large meshes make placing slow."""
    corners = [geometry.apply(p.transform, (x, y, 0.0)) for x in (-p.size[0], p.size[0]) for y in (-p.size[1], p.size[1])]
    x0, x1 = min(c[0] for c in corners), max(c[0] for c in corners)
    y0, y1 = min(c[1] for c in corners), max(c[1] for c in corners)
    out = []
    for k in range(0, len(idx), 3):
        a, b, c = idx[k] * 3, idx[k + 1] * 3, idx[k + 2] * 3
        if max(pos[a], pos[b], pos[c]) < x0 or min(pos[a], pos[b], pos[c]) > x1:
            continue
        if max(pos[a + 1], pos[b + 1], pos[c + 1]) < y0 or min(pos[a + 1], pos[b + 1], pos[c + 1]) > y1:
            continue
        out.extend((idx[k], idx[k + 1], idx[k + 2]))
    return out


def _inside(z, crossings):
    return sum(1 for c in crossings if c > z) % 2 == 1


def breaks_surface(p, pos, idx):
    """True when an embedded cavity leaves the part (pos/idx: the part's plate-frame mesh). Open pockets are open
    by design and are not checked. Probes sit slightly off-axis so a ray never runs along an edge."""
    if p.mode != "embedded":
        return False
    jitter = 1.7e-4
    idx = _near(p, pos, idx)
    if p.face == "side":     # a slot only has to stay inside the part; a flat cavity also needs its floor and its cover
        heights = (p.floor + INSET, p.top - INSET)
    else:
        heights = ((p.floor + p.top) / 2, p.top + INSET, p.floor - INSET)
    for x, y in _probes(p):
        cross = _crossings(x + jitter, y + jitter, pos, idx)
        if not all(_inside(z, cross) for z in heights):
            return True
    return False
