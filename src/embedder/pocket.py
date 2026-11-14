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
    pause_gcode: bool = True        # machine_pause_gcode is set
    by_object: bool = False         # print sequence "by object": Orca ignores the pause
    raft: bool = False
    variable_layers: bool = False   # layer height profile or a layer range on this object
    instances_rigid: bool = True    # every instance differs only by a Z rotation and a move


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
    shape: str                      # cylinder | box
    size: tuple                     # (diameter, diameter, height) or (x, y, height) of the local mesh
    transform: tuple                # local mesh -> plate frame
    floor: float = None             # embedded only: cavity bottom and top, on the layer grid
    top: float = None
    pause_z: float = None
    cover: float = None
    warnings: tuple = ()

    def mesh(self):
        sx, sy, sz = self.size
        return geometry.cylinder_mesh(sx, sz) if self.shape == "cylinder" else geometry.box_mesh(sx, sy, sz)

    def world_mesh(self):
        verts, tris = self.mesh()
        return tuple(geometry.apply(self.transform, v) for v in verts), tris


def _face(normal, kind):
    if kind == "flat":
        return "top" if normal[2] > 0 else "bottom"
    return kind


def _footprint(insert, cxy):
    return insert.l + 2 * cxy, insert.w + 2 * cxy


def _open(req, ctx, face):
    n = geometry.normalize(req.normal)
    depth = req.insert.t + ctx.z_clearance
    sx, sy = _footprint(req.insert, ctx.xy_clearance)
    origin = tuple(p - depth * k for p, k in zip(req.point, n))
    shape = "cylinder" if req.insert.shape == "disc" else "box"
    return Pocket(req.insert, "open", face, shape, (sx, sy, depth + OVERSHOOT),
                  geometry.frame(origin, n, req.spin))


def _check_embedded(ctx, kind):
    reasons = (("tilted_face", kind == "tilted"), ("by_object", ctx.by_object), ("no_pause_gcode", not ctx.pause_gcode),
               ("raft", ctx.raft), ("variable_layer_height", ctx.variable_layers),
               ("instances_differ", not ctx.instances_rigid))
    for code, hit in reasons:
        if hit:
            raise Blocked(code)


def check_pause(z, grid):
    if z < grid.first + grid.height - EPS:
        raise Blocked("pause_too_low", "the pause would come before the second layer")


def _cavity(nominal_floor, height, grid):
    if nominal_floor < -EPS:
        raise Blocked("below_bed", "the pocket would reach below the bed")
    floor = grid.snap_down(nominal_floor)
    return floor, grid.snap_up(floor + height)


def _embedded_flat(req, ctx, face):
    ins, grid = req.insert, ctx.grid
    height = ins.t + ctx.z_clearance
    z = req.point[2]
    nominal = z - req.cover - height if face == "top" else z + req.cover
    floor, top = _cavity(nominal, height, grid)
    cover = z - top if face == "top" else floor - z
    sx, sy = _footprint(ins, ctx.xy_clearance)
    transform = geometry.frame((req.point[0], req.point[1], floor), (0, 0, 1), req.spin)
    shape = "cylinder" if ins.shape == "disc" else "box"
    return Pocket(ins, "embedded", face, shape, (sx, sy, top - floor), transform, floor, top, cover=cover)


def _embedded_side(req, ctx):
    """The insert stands on edge behind the wall: a vertical slot, dropped in from above."""
    ins, grid, c = req.insert, ctx.grid, ctx.xy_clearance
    nh = geometry.normalize((req.normal[0], req.normal[1], 0.0))
    width, depth = ins.l + 2 * c, ins.t + 2 * c
    height = (ins.l if ins.shape == "disc" else ins.w) + ctx.z_clearance
    floor, top = _cavity(req.point[2] - height / 2, height, grid)
    back = req.cover + depth / 2
    centre = (req.point[0] - nh[0] * back, req.point[1] - nh[1] * back, floor)
    along = math.degrees(math.atan2(nh[0], -nh[1]))   # the wall's tangent (-ny, nx) as an angle from X
    transform = geometry.frame(centre, (0, 0, 1), along)
    return Pocket(ins, "embedded", "side", "box", (width, depth, top - floor), transform, floor, top, cover=req.cover)


def plan(req, ctx):
    """The pocket for one request, or Blocked."""
    if req.mode not in MODES:
        raise Blocked("bad_mode", str(req.mode))
    kind = geometry.tilt(req.normal)
    face = _face(req.normal, kind)
    if req.mode == "open":
        return _open(req, ctx, face)
    _check_embedded(ctx, kind)
    p = _embedded_flat(req, ctx, face) if kind == "flat" else _embedded_side(req, ctx)
    pause_z = round(p.top + ctx.grid.height, 6)
    check_pause(pause_z, ctx.grid)
    thin = p.cover < THIN_COVER_LAYERS * ctx.grid.height - EPS
    return Pocket(**{**p.__dict__, "pause_z": pause_z, "warnings": ("thin_cover",) if thin else ()})


def pause_text(labels):
    counts = Counter(labels)
    return PAUSE_PREFIX + " insert " + ", ".join("%d x %s" % (n, label) for label, n in counts.items())


def pauses(pockets, existing):
    """((top_z, extra), ...) sorted by height, one per height shared by embedded pockets, plus warnings for
    heights that already carry someone else's custom G-code (left alone, no Embedder pause added there)."""
    groups = {}
    for p in pockets:
        if p.pause_z is not None:
            groups.setdefault(round(p.pause_z, 6), []).append(p.insert.label)
    taken = [round(z, 6) for z in existing]
    out, warnings = [], []
    for z in sorted(groups):
        if any(abs(z - e) < 1e-3 for e in taken):
            warnings.append(("existing_gcode_at_layer", z))
        else:
            out.append((z, pause_text(groups[z])))
    return tuple(out), tuple(warnings)


def _reach(p):
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
