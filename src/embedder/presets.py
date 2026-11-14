"""Insert presets: the built-in magnet and NFC table plus validation of the user's own presets. Free of `orca`."""

import math
import uuid
from dataclasses import dataclass

KINDS = ("magnet", "nfc")
SHAPES = ("disc", "block")
MAX_USER_PRESETS = 200
MAX_NAME = 40
MAX_DIM = 300.0          # mm; nothing bigger fits a printer bed
NFC_STICKER_T = 0.4      # mm pocket depth for a round NFC sticker


class PresetError(ValueError):
    """An invalid or unknown preset; `code` is stable for the page."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    kind: str      # magnet | nfc
    shape: str     # disc | block
    l: float       # diameter for a disc
    w: float       # equals l for a disc
    t: float       # thickness
    builtin: bool = True

    @property
    def d(self):
        return self.l

    def as_dict(self):
        dims = {"d": self.l, "t": self.t} if self.shape == "disc" else {"l": self.l, "w": self.w, "t": self.t}
        return {"id": self.id, "name": self.label, "kind": self.kind, "shape": self.shape, **dims, "builtin": self.builtin}


def _g(v):
    return "%g" % v


def _disc(pid, label, kind, d, t, builtin=True):
    return Preset(pid, label, kind, "disc", float(d), float(d), float(t), builtin)


def _block(pid, label, kind, l, w, t, builtin=True):
    return Preset(pid, label, kind, "block", float(l), float(w), float(t), builtin)


def _table():
    out = []
    for d, t in ((3, 1), (4, 2), (5, 1), (5, 2), (5, 3), (6, 2), (6, 3), (8, 2), (8, 3), (10, 2), (10, 3), (10, 5),
                 (12, 3), (15, 3), (20, 3)):
        out.append(_disc("magnet-disc-%dx%d" % (d, t), "%dx%d magnet" % (d, t), "magnet", d, t))
    for l, w, t in ((10, 5, 2), (10, 5, 3), (20, 10, 2), (20, 10, 5)):
        out.append(_block("magnet-block-%dx%dx%d" % (l, w, t), "%dx%dx%d magnet" % (l, w, t), "magnet", l, w, t))
    for d in (10, 13, 20, 22, 25, 30, 38):
        out.append(_disc("nfc-sticker-%d" % d, "%d mm NFC sticker" % d, "nfc", d, NFC_STICKER_T))
    for d, t in ((25, 1), (30, 2)):
        out.append(_disc("nfc-coin-%dx%d" % (d, t), "%dx%d NFC coin" % (d, t), "nfc", d, t))
    out.append(_block("nfc-card", "NFC card", "nfc", 85.6, 54, 0.9))
    return tuple(out)


BUILTIN = _table()
_BY_ID = {p.id: p for p in BUILTIN}


def find(pid):
    return _BY_ID.get(pid)


def _dim(raw, key):
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PresetError("bad_dimension", "%s must be a number" % key)
    if not 0 < value <= MAX_DIM:
        raise PresetError("bad_dimension", "%s must be between 0 and %g mm" % (key, MAX_DIM))
    return float(value)


def _shape_dims(raw):
    kind, shape = raw.get("kind"), raw.get("shape")
    if kind not in KINDS:
        raise PresetError("bad_kind", "kind must be magnet or nfc")
    if shape not in SHAPES:
        raise PresetError("bad_shape", "shape must be disc or block")
    if shape == "disc":
        d = _dim(raw, "d")
        return kind, shape, d, d, _dim(raw, "t")
    return kind, shape, _dim(raw, "l"), _dim(raw, "w"), _dim(raw, "t")


def default_label(kind, shape, l, w, t):
    dims = "x".join(_g(v) for v in ((l, t) if shape == "disc" else (l, w, t)))
    return "%s %s" % (dims, "magnet" if kind == "magnet" else "NFC")


def parse_user(raw):
    """A user preset from page or file data; raises PresetError."""
    if not isinstance(raw, dict):
        raise PresetError("bad_preset", "a preset must be an object")
    name = " ".join(str(raw.get("name") or "").split())
    if not name or len(name) > MAX_NAME:
        raise PresetError("bad_name", "the name must have 1 to %d characters" % MAX_NAME)
    pid = raw.get("id")
    if pid is None:
        pid = "user-" + uuid.uuid4().hex[:8]
    if not isinstance(pid, str) or not pid.startswith("user-") or len(pid) > 40:
        raise PresetError("bad_id", "user preset ids start with user-")
    kind, shape, l, w, t = _shape_dims(raw)
    return Preset(pid, name, kind, shape, l, w, t, builtin=False)


def clean_user_presets(value):
    """The valid, distinct user presets (as dicts, at most MAX_USER_PRESETS), or None when value is not a list."""
    if not isinstance(value, list):
        return None
    out, seen = [], set()
    for raw in value:
        try:
            p = parse_user(raw)
        except PresetError:
            continue
        if p.id not in seen and len(out) < MAX_USER_PRESETS:
            seen.add(p.id)
            out.append(p.as_dict())
    return out


def resolve(args, user_presets):
    """The insert a plan request names: {"preset": id} or {"custom": {kind, shape, dims}}."""
    if isinstance(args.get("custom"), dict):
        kind, shape, l, w, t = _shape_dims(args["custom"])
        return Preset("custom", default_label(kind, shape, l, w, t), kind, shape, l, w, t, builtin=False)
    pid = args.get("preset")
    if not isinstance(pid, str):
        raise PresetError("no_preset", "name a preset or give custom dimensions")
    found = find(pid)
    if found:
        return found
    for raw in user_presets or []:
        if isinstance(raw, dict) and raw.get("id") == pid:
            return parse_user(raw)
    raise PresetError("unknown_preset", pid)


def upsert(user_presets, raw):
    """A new list with `raw` added or replacing the preset with the same id."""
    p = parse_user(raw)
    rest = [u for u in user_presets if u.get("id") != p.id]
    if len(rest) >= MAX_USER_PRESETS:
        raise PresetError("too_many_presets", "at most %d presets" % MAX_USER_PRESETS)
    replaced = len(rest) != len(user_presets)
    if replaced:
        return [p.as_dict() if u.get("id") == p.id else u for u in user_presets]
    return [*user_presets, p.as_dict()]


def delete(user_presets, pid):
    rest = [u for u in user_presets if u.get("id") != pid]
    if len(rest) == len(user_presets):
        raise PresetError("unknown_preset", str(pid))
    return rest
