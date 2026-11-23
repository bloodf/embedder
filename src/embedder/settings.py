"""One flat, validated settings store for the Embedder page. Free of the `orca` module."""

import json
import math
import os
import threading

import pocket
import presets

UI_LANGUAGES = ("auto", "en", "pt-BR", "es", "de", "zh-CN", "pl")   # "auto": OrcaSlicer's language, then the system's
MAGNET_GRADES = ("N35", "N42", "N52", "ferrite")
FRIDGE_SURFACES = ("steel", "stainless", "board")
DEFAULTS = {
    "ui_language": "auto",
    "xy_clearance": 0.2,     # mm added to the insert's width/diameter on each side
    "z_clearance": 0.2,      # mm added to the insert's thickness
    "cover_magnet": 1.0,     # mm of material sealed over an embedded magnet
    "cover_nfc": 0.6,        # mm of material sealed over an embedded NFC tag
    "magnet_grade": "N35",   # N35 | N42 | N52 | ferrite
    "fridge_surface": "steel",  # steel | stainless | board
    "user_presets": [],      # the user's own insert presets, validated by presets.clean_user_presets
    "pocket_shapes": {},     # preset id -> the pocket shape the user picked for it (pocket.SHAPES), oldest first
}
MAX_POCKET_SHAPES = 500
RANGES = {"xy_clearance": (0.0, 1.0), "z_clearance": (0.0, 1.0), "cover_magnet": (0.0, 10.0), "cover_nfc": (0.0, 10.0)}


def _clean(key, value):
    """The value to store for key, or None when it is not valid."""
    if key == "ui_language":
        return value if value in UI_LANGUAGES else None
    if key == "magnet_grade":
        return value if value in MAGNET_GRADES else None
    if key == "fridge_surface":
        return value if value in FRIDGE_SURFACES else None
    if key == "user_presets":
        return presets.clean_user_presets(value)
    if key == "pocket_shapes":
        if not isinstance(value, dict):
            return None
        good = [(k, v) for k, v in value.items() if isinstance(k, str) and 0 < len(k) <= 40 and v in pocket.SHAPES]
        return dict(good[-MAX_POCKET_SHAPES:])     # the newest: the page adds a pick last
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    low, high = RANGES[key]
    return float(value) if low <= value <= high else None


class Store:
    """JSON file at `path`, or load() -> text / save(text) callables when no path is available."""

    def __init__(self, path=None, load=None, save=None):
        self.path, self._load, self._save = path, load, save
        self.lock = threading.RLock()
        self.data = self._read()

    def _read(self):
        try:
            if self.path:
                with open(self.path, encoding="utf-8") as f:
                    text = f.read()
            elif self._load:
                text = self._load()
            else:
                return {}
            data = json.loads(text)
        except (OSError, ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data):
        text = json.dumps(data, indent=1)   # in order: pocket_shapes keeps its newest last
        if self.path:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, self.path)
        elif self._save:
            self._save(text)
        self.data = data

    def effective(self):
        with self.lock:
            out = {**DEFAULTS, "user_presets": [], "pocket_shapes": {}}
            for key in DEFAULTS:
                if key in self.data:
                    clean = _clean(key, self.data[key])
                    if clean is not None:
                        out[key] = clean
            return out

    def raw(self):
        with self.lock:
            return dict(self.data)

    def update(self, changes):
        """Validate and persist {key: value}; unknown or invalid keys are ignored. Returns effective()."""
        with self.lock:
            data = dict(self.data)
            for key, value in (changes if isinstance(changes, dict) else {}).items():
                clean = _clean(key, value) if key in DEFAULTS else None
                if clean is not None:
                    data[key] = clean
            if data != self.data:
                self._write(data)
            return self.effective()
