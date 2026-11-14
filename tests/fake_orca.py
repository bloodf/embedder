"""Test double: a fake `orca` module with the parts Embedder uses (pages capability, plugin storage, the plater's
3MF export, the current plate, the host language and the preset bundle's full config)."""

import json
import shutil
import sys
import tempfile
import types


class FakePlater:
    """export_3mf_copy(path) copies `source` (a 3MF on disk) to path; project_path() names the open project."""

    def __init__(self, source=None, project_path=""):
        self.source, self._project_path, self.exports = source, project_path, []

    def project_path(self):
        return self._project_path

    def export_3mf_copy(self, path):
        self.exports.append(path)
        if not self.source:
            return False
        shutil.copyfile(self.source, path)
        return True


def install_orca(preset=None, storage=None, source=None, project_path="", plate_index=0, language="en"):
    """Register a fake `orca` module. preset: {key: value} answered by preset_bundle().full_config_value."""
    orca = types.ModuleType("orca")

    class Base:
        _stored = None

        def get_config(self):
            return json.dumps(self._stored if self._stored is not None else self.get_default_config())

        def save_config(self, text):
            self._stored = json.loads(text)
            return True

        def get_default_config(self):
            return {}

        def post_message(self, data):
            self.posted = getattr(self, "posted", []) + [data]

    preset = dict(preset or {})
    orca.LifecycleEvent = types.SimpleNamespace(ProjectOpened=3)
    orca.permissions = []
    orca.pages = types.SimpleNamespace(PagesPluginCapabilityBase=Base)
    orca.base = object
    orca.registered = []
    orca.plugin = lambda cls: cls
    orca.register_capability = orca.registered.append
    orca.request_permissions = lambda **kw: orca.permissions.append(kw)
    orca.plater = FakePlater(source, project_path)
    orca.opened = []
    store_dir = storage or tempfile.mkdtemp()
    orca.storage_calls = {"inside": True}

    def storage_fn():
        if not orca.storage_calls["inside"]:
            raise RuntimeError("storage() is only available inside a plugin callback")
        return store_dir

    bundle = types.SimpleNamespace(full_config_value=lambda k: preset.get(k))
    orca.host = types.SimpleNamespace(
        plater=lambda: orca.plater,
        model=lambda: types.SimpleNamespace(current_plate_index=plate_index),
        app_language=language,
        preset_bundle=lambda: bundle,
        plugin=types.SimpleNamespace(storage=storage_fn))
    sys.modules["orca"] = orca
    return orca


def load_wheel(path):
    """Import the wheel's package `embedder` (zipimport) and return its namespace. Call install_orca() first."""
    import importlib
    for name in [n for n in sys.modules if n == "embedder" or n.startswith("embedder.")]:
        del sys.modules[name]
    sys.path[:] = [p for p in sys.path if not p.endswith(".whl")]
    sys.path.insert(0, str(path))
    sys.path_importer_cache.pop(str(path), None)
    importlib.invalidate_caches()
    return vars(importlib.import_module("embedder"))
