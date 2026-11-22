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
from dataclasses import dataclass, replace

import geometry
import pocket
import presets
import threemf

CHUNK_BYTES = 256 * 1024     # raw bytes per mesh chunk (before base64)
POINT_TOLERANCE = 1.0        # mm a clicked point may sit off its triangle's plane
LIVE_KEYS = ("layer_height", "initial_layer_print_height", "machine_pause_gcode", "print_sequence", "raft_layers",
             "printable_area")
GLOBAL_BLOCKS = ("by_object", "no_pause_gcode", "raft")
# Applied copies: <project>-embedder-<YYYYmmdd-HHMMSS>-<id6>[-n].3mf; a copy of a copy keeps the first project name.
COPY_RE = re.compile(r"^(.*?)(?:-embedder-\d{8}-\d{6}-[0-9a-f]{6}(?:-\d+)?)+\.3mf$")
KEEP_COPIES = 10             # older copies kept after an apply, besides the ones OrcaSlicer may have open
KEEP_DAYS = 30               # ...and none of them older than this
READ_SLACK = 1e-4            # mm; a height read back from a float32 mesh is off by up to ~3e-5 at 300 mm


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
    applied: bool = False        # written once: the copy is now the project; Load again before more pockets

    def copies(self, object_id):
        """How many instances of the object print on this plate (a negative part cuts each of them)."""
        return sum(1 for e in self.entries if e.obj.id == object_id)


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
    stem = re.sub(r"[\x00-\x1f]", "", stem)[:80]
    # a file name is at most 255 bytes on Linux: keep room for the suffix and the temporary name
    return stem.encode("utf-8")[:150].decode("utf-8", "ignore").strip() or "untitled"


class Session:
    def __init__(self, storage, settings_fn):
        self.storage, self.settings_fn = storage, settings_fn
        self.lock = threading.Lock()
        self.job = None          # the loaded project; it stays usable until a newer load succeeds
        self.pending = None      # id of the load in flight: its export or parse may still fail
        self.written = set()     # copies applied in this OrcaSlicer session: any of them may be open

    # -------------------------------------------------------------- lifecycle

    def new_job(self):
        """A fresh job folder; returns (job id, path the project copy goes to). The loaded job stays current until
        this one loads, so a failed export or parse leaves the project on screen working."""
        job_id = uuid.uuid4().hex[:12]
        folder = os.path.join(self.storage, "jobs", job_id)
        with self.lock:   # under the lock: a load finishing now must not list this folder as old
            os.makedirs(folder)
            self.pending = job_id
        return job_id, os.path.join(folder, "source.3mf")

    def _current(self, job_id):
        with self.lock:
            job = self.job
        if job is None or job.id != job_id or job.applied:
            raise SessionError("stale_job", "the project was loaded again or already applied; load it once more")
        return job

    def _is_current(self, job_id):
        with self.lock:
            return self.job is not None and self.job.id == job_id

    def _is_pending(self, job_id):
        with self.lock:
            return self.pending == job_id

    def load(self, job_id, project_path, plate, live, progress=None):
        """Parse the copy in the job folder. `live`: preset values for settings the project does not carry."""
        if not self._is_pending(job_id):
            raise SessionError("stale_job", "a newer load replaced this one")
        folder = os.path.join(self.storage, "jobs", job_id)
        try:
            pkg = threemf.read(os.path.join(folder, "source.3mf"), {k: live.get(k) for k in LIVE_KEYS if k in live})
            entries = self._entries(pkg, plate, progress)
        except threemf.ThreeMFError as e:
            if not self._is_pending(job_id):
                raise SessionError("stale_job", "a newer load replaced this one") from None
            raise SessionError(e.code, e.detail) from None
        except OSError:
            if not self._is_pending(job_id):
                raise SessionError("stale_job", "a newer load replaced this one") from None
            raise
        loaded = Job(job_id, folder, _stem(project_path), plate, pkg, entries)
        jobs = os.path.join(self.storage, "jobs")
        with self.lock:
            if self.pending != job_id:
                raise SessionError("stale_job", "a newer load replaced this one")
            self.job, self.pending = loaded, None
            old = [os.path.join(jobs, n) for n in os.listdir(jobs) if n != job_id]
        if old:   # off this thread; a worker still reading one of them gets stale_job
            threading.Thread(target=lambda: [shutil.rmtree(d, ignore_errors=True) for d in old], daemon=True).start()
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
        if any(i.plate != job.plate for i in job.pkg.items if i.object_id == entry.obj.id):
            return "instances_other_plate"
        if job.pkg.variable_layers(entry.obj.id):
            return "variable_layer_height"
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
        arr = entry.meshes[j][0 if kind == "pos" else 1]
        size = len(arr) * arr.itemsize
        chunks = max(1, math.ceil(size / CHUNK_BYTES))
        i = _index(args, "i", chunks)
        per = CHUNK_BYTES // arr.itemsize   # only this chunk is copied: the whole array per chunk was quadratic
        return {"i": i, "chunks": chunks, "bytes": size,
                "data": base64.b64encode(_bytes(arr[i * per:(i + 1) * per])).decode("ascii")}

    # -------------------------------------------------------------- planning

    def _grid(self, job, entry):
        s = self._settings(job.pkg)
        height = _float(entry.obj.layer_height) or s["layer_height"]
        try:
            return pocket.Grid(s["first_layer_height"] or height, height)
        except (TypeError, ValueError):
            return None

    def _usable_entry(self, job, args):
        obj_idx = _index(args, "object", len(job.entries))
        entry = job.entries[obj_idx]
        if job.pkg.has_cut_connectors(entry.obj.id):
            raise SessionError("cut_object", entry.obj.name)   # the detail is the name: the page writes the sentence
        if not job.pkg.has_settings:
            raise SessionError("no_model_settings", "the project has no model_settings.config")
        if entry.obj.plain:
            raise SessionError("unsupported_object", entry.obj.name)
        return obj_idx, entry

    def _request(self, job, args):
        _, entry = self._usable_entry(job, args)
        j = _index(args, "part", len(entry.meshes))
        part = entry.obj.parts[j]
        if part.subtype != "normal_part":
            raise SessionError("bad_part", "pockets go on model parts only")
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
        center = args.get("center", False)
        if not isinstance(center, bool):
            raise SessionError("bad_request", "center is true or false")
        if center:   # the middle of the flat face that was clicked; the click itself when the middle is off the face
            point = geometry.face_centre(pos, idx, t, normal) or point
        try:
            insert = presets.resolve(args, self.settings_fn().get("user_presets"))
        except presets.PresetError as e:
            raise SessionError(e.code, e.detail) from None
        cfg = self.settings_fn()
        cover = cfg["cover_magnet"] if insert.kind == "magnet" else cfg["cover_nfc"]
        if args.get("cover") is not None:
            cover = _number(args, "cover", low=0, high=10)
        spin = _number(args, "spin", 0)
        return entry, j, pocket.Request(insert, args.get("mode"), point, normal, spin, cover, args.get("pocket_shape"))

    def _context(self, job, entry):
        block = self._object_block(job, entry)
        cfg = self.settings_fn()
        grid = self._grid(job, entry)
        return pocket.Context(grid=grid or pocket.Grid(1.0, 1.0), xy_clearance=cfg["xy_clearance"], z_clearance=cfg["z_clearance"],
                              block=block, instances_rigid=job.pkg.instances_rigid(entry.obj.id)), grid

    def _plan_one(self, job, args):
        """(entry, Pocket) or raises pocket.Blocked / SessionError."""
        return self._plan_at(job, args)[:2]

    def _plan_at(self, job, args):
        """(entry, Pocket, the point it was planned at: the face's middle under center)."""
        if not isinstance(args, dict):
            raise SessionError("bad_request", "a pocket is an object")
        entry, j, req = self._request(job, args)
        ctx, grid = self._context(job, entry)
        if req.mode == "embedded" and grid is None:
            raise pocket.Blocked("no_layer_height", "the layer height is unknown")
        p = pocket.plan(req, ctx)
        if pocket.breaks_surface(p, *entry.meshes[j]):
            p = replace(p, warnings=p.warnings + ("breaks_surface",))
        return entry, p, req.point

    def plan(self, args):
        job = self._current(args.get("job"))
        try:
            entry, p, point = self._plan_at(job, args)
        except pocket.Blocked as e:
            return {"blocked": {"code": e.code, "detail": e.detail}, "preview": None, "mode": args.get("mode")}
        warnings = list(p.warnings) + [w[0] for w in pocket.pauses([p], self._user_layers(job))[1]]
        others = args.get("others") or []
        if not isinstance(others, list):
            raise SessionError("bad_request", "others is a list")
        if others:
            planned = [p] + [q for _, q in self._plan_quiet(job, others)]
            warnings += [w[0] for w in pocket.proximity_warnings(planned) if 0 in w[1:]]
        return {**_describe_pocket(p), "point": [round(v, 6) for v in point], "copies": job.copies(entry.obj.id),
                "warnings": warnings, "blocked": None}

    def auto_fridge(self, args):
        """Plan 1, 2, 3, or 4 symmetric bottom-face fridge magnet pockets on the selected object."""
        job = self._current(args.get("job"))
        obj_idx, entry = self._usable_entry(job, args)

        raw_count = args.get("count", "auto")
        if raw_count != "auto" and raw_count is not None:
            if isinstance(raw_count, bool) or not isinstance(raw_count, int) or not 1 <= raw_count <= 8:
                raise SessionError("bad_request", "count is auto or 1..8")
        spread = _number(args, "spread", 0.28, low=0.10, high=0.45)

        normal_parts = [(j, entry.meshes[j][0], entry.meshes[j][1])
                        for j, p in enumerate(entry.obj.parts)
                        if p.subtype == "normal_part" and len(entry.meshes[j][0]) >= 9]
        if not normal_parts:
            raise SessionError("bad_part", "object has no normal model parts")
        down_tris = geometry.bottom_triangles(normal_parts)
        if not down_tris:
            raise SessionError("bad_part", "no bottom face found on this object")

        resolve_args = dict(args)
        if resolve_args.get("preset") is None and resolve_args.get("custom") is None:
            resolve_args["preset"] = "magnet-disc-6x2"
        try:
            insert = presets.resolve(resolve_args, self.settings_fn().get("user_presets"))
        except presets.PresetError as e:
            raise SessionError(e.code, e.detail) from None

        cfg = self.settings_fn()
        targets = pocket.fridge_targets(down_tris, insert, cfg["xy_clearance"], raw_count, spread)

        mode = args.get("mode") if args.get("mode") in ("embedded", "open") else "embedded"
        if self._object_block(job, entry) and mode == "embedded":
            mode = "open"
        cover = args.get("cover")
        if cover is None:
            cover = min(cfg["cover_magnet"], 0.4)

        def build_args(part_j, tri_t, pt, item_mode):
            out = {"object": obj_idx, "part": part_j, "tri": tri_t, "point": pt, "mode": item_mode}
            if isinstance(args.get("custom"), dict):
                out["custom"] = args["custom"]
            else:
                out["preset"] = insert.id
            if args.get("spin"):
                out["spin"] = args["spin"]
            if item_mode == "embedded" and cover is not None:
                out["cover"] = float(cover)
            if args.get("pocket_shape"):
                out["pocket_shape"] = args["pocket_shape"]
            return out

        planned_entries = []
        for tx, ty in targets:
            part_j, tri_t, pt = geometry.snap_to_bottom(tx, ty, down_tris)
            p_args = build_args(part_j, tri_t, pt, mode)
            p, point = None, None
            try:
                _, p, point = self._plan_at(job, p_args)
            except pocket.Blocked:
                pass
            if p_args["mode"] == "embedded" and (
                p is None or (args.get("cover") is None and "breaks_surface" in p.warnings)
            ):
                open_args = build_args(part_j, tri_t, pt, "open")
                try:
                    _, open_p, open_pt = self._plan_at(job, open_args)
                    if p is None or "breaks_surface" not in open_p.warnings:
                        p_args, p, point = open_args, open_p, open_pt
                except pocket.Blocked:
                    pass
            if p is not None:
                planned_entries.append((p_args, p, point))

        all_pockets = [p for _, p, _ in planned_entries]
        prox = pocket.proximity_warnings(all_pockets) if len(all_pockets) > 1 else ()
        user_layers = self._user_layers(job)
        copies = job.copies(entry.obj.id)
        staged_out = []
        for idx_i, (p_args, p, point) in enumerate(planned_entries):
            warnings = list(p.warnings) + [w[0] for w in pocket.pauses([p], user_layers)[1]]
            warnings += [w[0] for w in prox if idx_i in w[1:]]
            plan_res = {**_describe_pocket(p), "point": [round(v, 6) for v in point], "copies": copies,
                        "warnings": warnings, "blocked": None}
            staged_out.append({"args": p_args, "plan": plan_res})
        return {"items": staged_out, "count": len(staged_out)}

    def _plan_quiet(self, job, many):
        out = []
        for args in many:
            try:
                out.append(self._plan_one(job, args))
            except (pocket.Blocked, SessionError):
                continue
        return out

    # -------------------------------------------------------------- applying

    def _user_layers(self, job):
        """Heights on the job's plate that carry someone else's custom G-code."""
        return [l.top_z for l in job.pkg.layers if l.plate == job.plate and not l.embedder]

    def _kept_pauses(self, job, removed):
        """Embedded Embedder parts that stay: ((Pocket, copies), ...); the pause is the layer after the cavity top."""
        out = []
        for e in job.entries:
            if e.instance:
                continue
            grid = self._grid(job, e)
            for part, (pos, _) in zip(e.obj.parts, e.meshes):
                m = threemf.PART_NAME_RE.match(part.name)
                if part.subtype != "negative_part" or not m or m.group(2) != "embedded" or part.id in removed or grid is None \
                        or not pos:
                    continue
                top = grid.snap_up(max(pos[2::3]) - READ_SLACK)   # 8.6 reads 8.6000004: not the next layer
                label = presets.Preset("kept", m.group(1), "magnet", "disc", 0, 0, 0, False)
                out.append((pocket.Pocket(label, "embedded", "", "", (0, 0, 0), geometry.IDENTITY,
                                          pause_z=round(top + grid.height, 6)), job.copies(e.obj.id)))
        return out

    def _write(self, job, adds, remove, pauses):
        """Write <storage>/<stem>-embedder-<YYYYmmdd-HHMMSS>-<id6>.3mf; a name taken in the meantime gets -2, -3...
        threemf.write never replaces a file, so the name is claimed atomically."""
        base = os.path.join(self.storage, "%s-embedder-%s-%s" % (job.stem, time.strftime("%Y%m%d-%H%M%S"), job.id[:6]))
        for n in range(1, 100):
            out = base + (".3mf" if n == 1 else "-%d.3mf" % n)
            try:
                threemf.write(job.pkg, out, job.plate, adds, remove, pauses)
                return out
            except threemf.ThreeMFError as e:
                if e.code != "exists":
                    raise SessionError(e.code, e.detail) from None
            except OSError:
                if not self._is_current(job.id):
                    raise SessionError("stale_job", "a newer load replaced this one") from None
                raise
        raise SessionError("exists", base)

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
        kept = self._kept_pauses(job, set(remove))
        pauses, pause_warnings = pocket.pauses(pockets + [k for k, _ in kept], self._user_layers(job),
                                               [job.copies(e.obj.id) for e, _ in planned] + [n for _, n in kept])
        adds = [threemf.Addition(e.obj.id, e.item.index, "Embedder %s (%s)" % (p.insert.label, p.mode), *p.mesh(), p.transform)
                for e, p in planned]
        out = self._write(job, adds, remove, pauses)
        with self.lock:
            self.written.add(out)
            if self.job is not None and self.job.id == job.id:
                self.job = replace(self.job, applied=True)
        pruned = self._prune()
        warnings = sorted({w for p in pockets for w in p.warnings} | {w[0] for w in pause_warnings}
                          | {w[0] for w in pocket.proximity_warnings(pockets)})
        return {"path": out, "name": os.path.basename(out), "pockets": len(pockets), "removed": len(remove),
                "pauses": [{"top_z": z, "extra": x} for z, x in pauses], "warnings": warnings,
                "pruned": pruned}

    # -------------------------------------------------------------- applied copies

    def _old_copies(self):
        """The applied copies that may be deleted, newest first: (path, mtime, size). Kept: the newest copy of each
        project and every copy written in this session, since OrcaSlicer may have any of those open."""
        found = []
        for name in os.listdir(self.storage):
            m, path = COPY_RE.match(name), os.path.join(self.storage, name)
            if m and os.path.isfile(path) and not os.path.islink(path):
                st = os.stat(path)
                found.append((path, m.group(1), st.st_mtime, st.st_size))
        found.sort(key=lambda c: c[2], reverse=True)
        with self.lock:
            written = set(self.written)
        seen, old = set(), []
        for path, project, mtime, size in found:
            if project not in seen:
                seen.add(project)
            elif path not in written:
                old.append((path, mtime, size))
        return old, len(found) - len(old)

    @staticmethod
    def _delete(copies):
        """(removed, bytes freed, failed) for deleting these copies."""
        removed = freed = failed = 0
        for path, _, size in copies:
            try:
                os.remove(path)
            except FileNotFoundError:
                continue
            except OSError:
                failed += 1
                continue
            removed, freed = removed + 1, freed + size
        return removed, freed, failed

    def _prune(self):
        """After an apply: drop old copies past KEEP_COPIES or KEEP_DAYS. Best effort: a copy that can't be deleted
        now is tried again after the next apply. Returns how many went."""
        try:
            old, _ = self._old_copies()
        except OSError:
            return 0
        cutoff = time.time() - KEEP_DAYS * 86400
        return self._delete([c for n, c in enumerate(old) if n >= KEEP_COPIES or c[1] < cutoff])[0]

    def copies_status(self):
        old, kept = self._old_copies()
        return {"count": len(old), "bytes": sum(c[2] for c in old), "kept": kept}

    def clear_copies(self):
        """Delete every copy that may go; {removed, freed, failed} plus the status afterwards."""
        removed, freed, failed = self._delete(self._old_copies()[0])
        return {"removed": removed, "freed": freed, "failed": failed, **self.copies_status()}


def _round(v):
    return None if v is None else round(v, 6)


def _describe_pocket(p):
    verts, tris = p.world_mesh()
    return {"mode": p.mode, "face": p.face, "shape": p.shape, "size": [round(v, 6) for v in p.size],
            "outer": [round(v, 6) for v in p.outer()],
            "transform": [round(v, 9) for v in p.transform], "floor": _round(p.floor), "top": _round(p.top),
            "pause_z": _round(p.pause_z), "cover": _round(p.cover), "label": p.insert.label, "kind": p.insert.kind,
            "preview": {"positions": [round(c, 4) for v in verts for c in v], "indices": [i for t in tris for i in t]}}
