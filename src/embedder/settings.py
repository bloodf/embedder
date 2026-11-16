"""One flat, validated settings store for the Embedder page. Free of the `orca` module."""

import json
import math
import os
import threading

import presets

UI_LANGUAGES = ("auto", "en", "pt-BR", "es", "de", "zh-CN")   # "auto": OrcaSlicer's language, then the system's
DEFAULTS = {
    "ui_language": "auto",
    "xy_clearance": 0.2,     # mm added to the insert's width/diameter on each side
    "z_clearance": 0.2,      # mm added to the insert's thickness
    "cover_magnet": 1.0,     # mm of material sealed over an embedded magnet
    "cover_nfc": 0.6,        # mm of material sealed over an embedded NFC tag
    "user_presets": [],      # the user's own insert presets, validated by presets.clean_user_presets
}
RANGES = {"xy_clearance": (0.0, 1.0), "z_clearance": (0.0, 1.0), "cover_magnet": (0.0, 10.0), "cover_nfc": (0.0, 10.0)}


def _clean(key, value):
    """The value to store for key, or None when it is not valid."""
    if key == "ui_language":
        return value if value in UI_LANGUAGES else None
    if key == "user_presets":
        return presets.clean_user_presets(value)
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
        text = json.dumps(data, indent=1, sort_keys=True)
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
            out = {**DEFAULTS, "user_presets": []}
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
