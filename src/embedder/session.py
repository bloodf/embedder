"""The Embedder job: load a project copy, serve its meshes, plan pockets and write the applied copy. Runs on the
plugin's worker threads or the UI thread as plugin.py decides; free of `orca` (the host is reached only through the
values plugin.py passes in)."""

import base64
import math
import os
import re
import shutil
import sys
import threading
import time
import uuid
from dataclasses import dataclass

import geometry
import pocket
import presets
import threemf

CHUNK_BYTES = 256 * 1024     # raw bytes per mesh chunk (before base64)
POINT_TOLERANCE = 1.0        # mm a clicked point may sit off its triangle's plane
LIVE_KEYS = ("layer_height", "initial_layer_print_height", "machine_pause_gcode", "print_sequence", "raft_layers",
             "printable_area")
GLOBAL_BLOCKS = ("by_object", "no_pause_gcode", "raft")


class SessionError(Exception):
    """A refused request: `code` is stable for the page, `detail` is human text."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Entry:
    """One build item (instance) on the job's plate."""
    item: object                 # threemf.Item
    obj: object                  # threemf.ModelObject
    instance: int                # n-th instance of the object
    meshes: tuple                # per part: (positions array('f'), indices array('I')) in the plate frame


@dataclass(frozen=True)
class Job:
    id: str
    dir: str
    stem: str
    plate: int
    pkg: object                  # threemf.Package
    entries: tuple


def _bytes(arr):
    if sys.byteorder == "big":
        arr = type(arr)(arr.typecode, arr)
        arr.byteswap()
    return arr.tobytes()


def _float(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _number(args, key, default=None, low=-math.inf, high=math.inf):
    value = args.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise SessionError("bad_request", "%s must be a number" % key)
    return float(value)


def _index(args, key, size):
    value = args.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < size:
        raise SessionError("bad_request", "%s is out of range" % key)
    return value


def _stem(project_path):
    name = os.path.basename(str(project_path or "").replace("\\", "/"))
    stem = os.path.splitext(name)[0].strip()
    return re.sub(r"[\x00-\x1f]", "", stem)[:80] or "untitled"


class Session:
    def __init__(self, storage, settings_fn):
        self.storage, self.settings_fn = storage, settings_fn
        self.lock = threading.Lock()
        self.job = None

    # -------------------------------------------------------------- lifecycle

    def new_job(self):
        """A fresh job folder; returns (job id, path the project copy goes to). Older jobs are dropped."""
        job_id = uuid.uuid4().hex[:12]
        folder = os.path.join(self.storage, "jobs", job_id)
        os.makedirs(folder)
        with self.lock:
            self._drop_older(job_id)
            self.job = Job(job_id, folder, "", 0, None, ())
        return job_id, os.path.join(folder, "source.3mf")

    def _drop_older(self, keep):
        jobs = os.path.join(self.storage, "jobs")
        for name in os.listdir(jobs):
            if name != keep:
                shutil.rmtree(os.path.join(jobs, name), ignore_errors=True)

    def _current(self, job_id, loaded=True):
        with self.lock:
            job = self.job
        if job is None or job.id != job_id or (loaded and job.pkg is None):
            raise SessionError("stale_job", "the project was loaded again; load it once more")
        return job

    def load(self, job_id, project_path, plate, live, progress=None):
        """Parse the copy in the job folder. `live`: preset values for settings the project does not carry."""
        job = self._current(job_id, loaded=False)
        try:
            pkg = threemf.read(os.path.join(job.dir, "source.3mf"), {k: live.get(k) for k in LIVE_KEYS if k in live})
        except threemf.ThreeMFError as e:
            raise SessionError(e.code, e.detail) from None
        entries = self._entries(pkg, plate, progress)
        loaded = Job(job.id, job.dir, _stem(project_path), plate, pkg, entries)
        with self.lock:
            if self.job is None or self.job.id != job.id:
                raise SessionError("stale_job", "a newer load replaced this one")
            self.job = loaded
        return self._describe(loaded)

    def _entries(self, pkg, plate, progress):
        out, seen = [], {}
        items = [i for i in pkg.items if i.plate == plate]
        for n, item in enumerate(items):
            obj = pkg.objects[item.object_id]
            meshes = tuple(pkg.plate_mesh(item, p) for p in obj.parts)
            out.append(Entry(item, obj, seen.get(obj.id, 0), meshes))
            seen[obj.id] = seen.get(obj.id, 0) + 1
            if progress:
                progress(n + 1, len(items))
        return tuple(out)

    # -------------------------------------------------------------- describing

    def _settings(self, pkg):
        def text(key):
            v = pkg.setting(key)
            return "" if v is None else str(v)
        raft = _float(text("raft_layers")) or 0
        return {"layer_height": _float(text("layer_height")), "first_layer_height": _float(text("initial_layer_print_height")),
                "pause_gcode": bool(text("machine_pause_gcode").strip()), "print_sequence": text("print_sequence") or "by layer",
                "raft_layers": int(raft)}

    def _global_blocks(self, job):
        s = self._settings(job.pkg)
        seq = job.pkg.plate_meta.get(job.plate, {}).get("print_sequence") or s["print_sequence"]
        hits = {"by_object": seq.strip().lower() == "by object", "no_pause_gcode": not s["pause_gcode"],
                "raft": s["raft_layers"] > 0}
        return [code for code in GLOBAL_BLOCKS if hits[code]]

    def _object_block(self, job, entry):
        blocks = self._global_blocks(job)
        if blocks:
            return blocks[0]
        if job.pkg.variable_layers(entry.obj.id):
            return "variable_layer_height"
        if not job.pkg.instances_rigid(entry.obj.id):
            return "instances_differ"
        return None

    def _describe(self, job):
        pkg = job.pkg
        objects = []
        for k, e in enumerate(job.entries):
            parts = []
            for j, (p, (pos, idx)) in enumerate(zip(e.obj.parts, e.meshes)):
                pb, ib = len(pos) * 4, len(idx) * 4
                parts.append({"part": j, "id": p.id, "name": p.name, "subtype": p.subtype,
                              "embedder": bool(threemf.PART_NAME_RE.match(p.name)) and p.subtype == "negative_part",
                              "vertices": len(pos) // 3, "triangles": len(idx) // 3, "pos_bytes": pb, "idx_bytes": ib,
                              "pos_chunks": max(1, math.ceil(pb / CHUNK_BYTES)), "idx_chunks": max(1, math.ceil(ib / CHUNK_BYTES))})
            objects.append({"object": k, "id": e.obj.id, "name": e.obj.name, "item": e.item.index, "instance": e.instance,
                            "cut": pkg.has_cut_connectors(e.obj.id), "embedded_block": self._object_block(job, e),
                            "parts": parts})
        on_plate = {e.obj.id for e in job.entries}
        return {"job": job.id, "name": job.stem, "plate": job.plate, "plates": pkg.plate_count,
                "config_source": pkg.config_source, "settings": self._settings(pkg), "blocks": self._global_blocks(job),
                "objects": objects, "chunk_bytes": CHUNK_BYTES,
                "existing": [{"id": x.id, "object_id": x.object_id, "name": x.name, "label": x.label, "mode": x.mode}
                             for x in pkg.embedder_parts() if x.object_id in on_plate],
                "pauses": [{"top_z": l.top_z, "type": l.type, "extra": l.extra, "embedder": l.embedder}
                           for l in pkg.layers if l.plate == job.plate]}

    # -------------------------------------------------------------- meshes

    def mesh_chunk(self, args):
        job = self._current(args.get("job"))
        entry = job.entries[_index(args, "object", len(job.entries))]
        j = _index(args, "part", len(entry.meshes))
        kind = args.get("kind")
        if kind not in ("pos", "idx"):
            raise SessionError("bad_request", "kind is pos or idx")
        data = _bytes(entry.meshes[j][0 if kind == "pos" else 1])
        chunks = max(1, math.ceil(len(data) / CHUNK_BYTES))
        i = _index(args, "i", chunks)
        return {"i": i, "chunks": chunks, "bytes": len(data),
                "data": base64.b64encode(data[i * CHUNK_BYTES:(i + 1) * CHUNK_BYTES]).decode("ascii")}

    # -------------------------------------------------------------- planning

    def _grid(self, job, entry):
        s = self._settings(job.pkg)
        height = _float(entry.obj.layer_height) or s["layer_height"]
        try:
            return pocket.Grid(s["first_layer_height"] or height, height)
        except (TypeError, ValueError):
            return None

    def _request(self, job, args):
        entry = job.entries[_index(args, "object", len(job.entries))]
        j = _index(args, "part", len(entry.meshes))
        part = entry.obj.parts[j]
        if part.subtype != "normal_part":
            raise SessionError("bad_part", "pockets go on model parts only")
        if job.pkg.has_cut_connectors(entry.obj.id):
            raise SessionError("cut_object", "%s was cut with connectors" % entry.obj.name)
        pos, idx = entry.meshes[j]
        t = _index(args, "tri", len(idx) // 3)
        corners = [tuple(pos[3 * idx[3 * t + c] + a] for a in range(3)) for c in range(3)]
        try:
            normal = geometry.triangle_normal(*corners)
        except ValueError:
            raise SessionError("bad_triangle", "the face has no area") from None
        point = args.get("point")
        if not (isinstance(point, list) and len(point) == 3):
            raise SessionError("bad_request", "point is [x, y, z]")
        point = tuple(_number({"v": v}, "v") for v in point)
        if abs(sum((p - c) * n for p, c, n in zip(point, corners[0], normal))) > POINT_TOLERANCE:
            raise SessionError("bad_point", "the point is not on the face")
        try:
            insert = presets.resolve(args, self.settings_fn().get("user_presets"))
        except presets.PresetError as e:
            raise SessionError(e.code, e.detail) from None
        cfg = self.settings_fn()
        cover = cfg["cover_magnet"] if insert.kind == "magnet" else cfg["cover_nfc"]
        if args.get("cover") is not None:
            cover = _number(args, "cover", low=0, high=10)
        spin = _number(args, "spin", 0)
        return entry, pocket.Request(insert, args.get("mode"), point, normal, spin, cover)

    def _context(self, job, entry):
        block = self._object_block(job, entry)
        cfg = self.settings_fn()
        grid = self._grid(job, entry)
        return pocket.Context(grid=grid or pocket.Grid(1.0, 1.0), xy_clearance=cfg["xy_clearance"], z_clearance=cfg["z_clearance"],
                              pause_gcode=block != "no_pause_gcode", by_object=block == "by_object", raft=block == "raft",
                              variable_layers=block == "variable_layer_height", instances_rigid=block != "instances_differ"), grid

    def _plan_one(self, job, args):
        """(entry, Pocket) or raises pocket.Blocked / SessionError."""
        if not isinstance(args, dict):
            raise SessionError("bad_request", "a pocket is an object")
        entry, req = self._request(job, args)
        ctx, grid = self._context(job, entry)
        if req.mode == "embedded" and grid is None:
            raise pocket.Blocked("no_layer_height", "the layer height is unknown")
        return entry, pocket.plan(req, ctx)

    def plan(self, args):
        job = self._current(args.get("job"))
        try:
            entry, p = self._plan_one(job, args)
        except pocket.Blocked as e:
            return {"blocked": {"code": e.code, "detail": e.detail}, "preview": None, "mode": args.get("mode")}
        warnings = list(p.warnings)
        others = args.get("others") or []
        if others:
            planned = [p] + [q for _, q in self._plan_quiet(job, others)]
            warnings += [w[0] for w in pocket.proximity_warnings(planned) if 0 in w[1:]]
        return {**_describe_pocket(p), "warnings": warnings, "blocked": None}

    def _plan_quiet(self, job, many):
        out = []
        for args in many:
            try:
                out.append(self._plan_one(job, args))
            except (pocket.Blocked, SessionError):
                continue
        return out

    # -------------------------------------------------------------- applying

    def _kept_pauses(self, job, removed):
        """Embedded Embedder parts that stay: their pause is the layer after their cavity top."""
        out = []
        for e in job.entries:
            if e.instance:
                continue
            grid = self._grid(job, e)
            for part, (pos, _) in zip(e.obj.parts, e.meshes):
                m = threemf.PART_NAME_RE.match(part.name)
                if part.subtype != "negative_part" or not m or m.group(2) != "embedded" or part.id in removed or grid is None:
                    continue
                top = grid.snap_up(max(pos[2::3]))
                label = presets.Preset("kept", m.group(1), "magnet", "disc", 0, 0, 0, False)
                out.append(pocket.Pocket(label, "embedded", "", "", (0, 0, 0), geometry.IDENTITY, pause_z=round(top + grid.height, 6)))
        return out

    def _output(self, job):
        """<storage>/<stem>-embedder-<YYYYmmdd-HHMMSS>-<id6>.3mf; a second apply in the same second gets -2, -3..."""
        base = os.path.join(self.storage, "%s-embedder-%s-%s" % (job.stem, time.strftime("%Y%m%d-%H%M%S"), job.id[:6]))
        n, out = 1, base + ".3mf"
        while os.path.exists(out):
            n += 1
            out = "%s-%d.3mf" % (base, n)
        return out

    def apply(self, args):
        job = self._current(args.get("job"))
        many, remove = args.get("pockets", []), args.get("remove", [])
        if not isinstance(many, list) or not isinstance(remove, list) or not all(isinstance(r, str) for r in remove):
            raise SessionError("bad_request", "pockets and remove are lists")
        planned = []
        for n, a in enumerate(many):
            try:
                planned.append(self._plan_one(job, a))
            except pocket.Blocked as e:
                raise SessionError("pocket_blocked", "pocket %d: %s" % (n + 1, e.code)) from None
        pockets = [p for _, p in planned]
        existing = [l.top_z for l in job.pkg.layers if l.plate == job.plate and not l.embedder]
        pauses, pause_warnings = pocket.pauses(pockets + self._kept_pauses(job, set(remove)), existing)
        adds = [threemf.Addition(e.obj.id, e.item.index, "Embedder %s (%s)" % (p.insert.label, p.mode), *p.mesh(), p.transform)
                for e, p in planned]
        out = self._output(job)
        try:
            threemf.write(job.pkg, out, job.plate, adds, remove, pauses)
        except threemf.ThreeMFError as e:
            raise SessionError(e.code, e.detail) from None
        warnings = sorted({w for p in pockets for w in p.warnings} | {w[0] for w in pause_warnings}
                          | {w[0] for w in pocket.proximity_warnings(pockets)})
        return {"path": out, "name": os.path.basename(out), "pockets": len(pockets), "removed": len(remove),
                "pauses": [{"top_z": z, "extra": x} for z, x in pauses], "warnings": warnings}


def _round(v):
    return None if v is None else round(v, 6)


def _describe_pocket(p):
    verts, tris = p.world_mesh()
    return {"mode": p.mode, "face": p.face, "shape": p.shape, "size": [round(v, 6) for v in p.size],
            "transform": [round(v, 9) for v in p.transform], "floor": _round(p.floor), "top": _round(p.top),
            "pause_z": _round(p.pause_z), "cover": _round(p.cover), "label": p.insert.label, "kind": p.insert.kind,
            "preview": {"positions": [round(c, 4) for v in verts for c in v], "indices": [i for t in tris for i in t]}}
