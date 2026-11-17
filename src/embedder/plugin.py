"""OrcaSlicer glue: the Embedder tab. The only module that imports `orca`. The page bridge runs on OrcaSlicer's
UI thread; parsing and writing project copies run on the plugin's own threads (session.py)."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import orca

import presets
import session
import settings

VERSION = "0.0.0-dev"

_store = None
_store_lock = threading.Lock()
_storage_dir = None
_session = None
_session_lock = threading.Lock()


def log(msg):
    line = "[embedder] " + str(msg)
    try:
        print(line)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(line.encode(enc, "replace").decode(enc))


def json_for_html(data):
    """JSON safe inside a <script> block: no literal <, > or & can end it or open a tag."""
    return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


# ---------------------------------------------------------------------- storage, settings, assets

def _storage():
    """The plugin's storage folder ("" when unknown). OrcaSlicer 2.5 answers plugin.storage() only inside a
    plugin callback, so the first answer is kept for the worker threads."""
    global _storage_dir
    if _storage_dir:
        return _storage_dir
    try:
        _storage_dir = orca.host.plugin.storage() or None
    except Exception as e:
        log("no storage folder (%s)" % e)
    return _storage_dir or ""


def _storage_or_raise():
    folder = _storage()
    if not folder:
        raise RuntimeError("no storage folder")
    return folder


def get_store(cap=None):
    """The shared settings store: a file in the storage folder, else the capability's own config."""
    global _store
    with _store_lock:
        if _store is None:
            try:
                _store = settings.Store(os.path.join(_storage_or_raise(), "settings.json"))
            except Exception as e:
                log("settings: no storage folder (%s); using the plugin config" % e)
                if cap is None:
                    return settings.Store()
                _store = settings.Store(load=lambda: json.dumps(_cap_config(cap).get("embedder_settings") or {}),
                                        save=lambda text: cap.save_config(
                                            json.dumps({**_cap_config(cap), "embedder_settings": json.loads(text)})))
        return _store


def _cap_config(cap):
    try:
        data = json.loads(cap.get_config())
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _asset(name):
    """From the generated _assets module in the wheel; from src/embedder/ui during development."""
    if __package__:
        from . import _assets
        return {"app.html": _assets.APP_HTML, "icon.png": _assets.ICON_PNG}[name]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", name)
    if name.endswith(".png"):
        with open(path, "rb") as f:
            return f.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def _host_language():
    try:
        attr = orca.host.app_language
        lang = attr() if callable(attr) else attr
    except Exception:
        return None
    return lang if isinstance(lang, str) and lang else None


def page_html(language="auto"):
    boot = {"version": VERSION, "lang": _host_language(),
            "pref": language if language in settings.UI_LANGUAGES else "auto"}
    return _asset("app.html").replace("__BOOT__", json_for_html(boot), 1)


# ---------------------------------------------------------------------- host reads (UI thread only)

def _call(obj, name):
    attr = getattr(obj, name)
    return attr() if callable(attr) else attr


def _current_plate():
    """1-based plate selected in Orca; plate 1 when the host does not say."""
    try:
        return int(_call(orca.host.model(), "current_plate_index")) + 1
    except Exception:
        return 1


def _live_values():
    """The live preset values a project without its own settings falls back to."""
    out = {}
    try:
        bundle = orca.host.preset_bundle()
    except Exception as e:
        log("no preset bundle (%s)" % e)
        return out
    for key in session.LIVE_KEYS:
        try:
            value = bundle.full_config_value(key)
        except Exception:
            continue
        if value is not None:
            out[key] = value
    return out


def open_in_orca(path):
    """Ask the running OrcaSlicer to open `path` (port of orca_organizer's _open_in_orca). False: no launcher."""
    if sys.platform == "darwin":
        app = next((p for p in Path(sys.prefix).resolve().parents if p.suffix == ".app"), None)
        cmd = ["open", "-a", str(app) if app else "OrcaSlicer", str(path)]
    elif sys.platform.startswith("linux"):
        exe = os.environ.get("APPIMAGE") or os.path.realpath("/proc/self/exe")
        cmd = [exe, str(path)]
    else:
        candidates = [Path(sys.executable)] + [Path(sys.prefix).parent / n for n in ("orca-slicer.exe", "OrcaSlicer.exe")]
        exe = next((c for c in candidates if c.is_file() and "orca" in c.name.lower()), None)
        if exe is None:
            return False
        cmd = [str(exe), str(path)]
    subprocess.Popen(cmd)
    return True


_open_in_orca = open_in_orca


# ---------------------------------------------------------------------- commands

class CommandError(Exception):
    """An error the page shows: a stable code plus a human detail."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code, self.detail = code, detail


def get_session(page):
    global _session
    with _session_lock:
        if _session is None:
            _session = session.Session(_storage_or_raise(), lambda: get_store(page).effective())
        return _session


def _cmd_hello(page, args):
    return {"version": VERSION, "settings": get_store(page).effective()}


def _cmd_settings_get(page, args):
    return get_store(page).effective()


def _cmd_settings_save(page, args):
    return get_store(page).update(dict(args.get("settings") or {}))


def _cmd_presets_list(page, args):
    return {"builtin": [p.as_dict() for p in presets.BUILTIN], "user": get_store(page).effective()["user_presets"]}


def _cmd_presets_save(page, args):
    store = get_store(page)
    raw = args.get("preset")
    users = presets.upsert(store.effective()["user_presets"], raw)
    saved = users[-1] if not (isinstance(raw, dict) and raw.get("id")) else next(u for u in users if u["id"] == raw["id"])
    return {"id": saved["id"], "user": store.update({"user_presets": users})["user_presets"]}


def _cmd_presets_delete(page, args):
    store = get_store(page)
    users = presets.delete(store.effective()["user_presets"], args.get("id"))
    return {"user": store.update({"user_presets": users})["user_presets"]}


def _cmd_project_load(page, args, msg_id):
    """UI thread: export the open project (export_3mf_copy is UI-thread only), then parse on a worker."""
    sess = get_session(page)
    plater = orca.host.plater()
    project, plate, live = _call(plater, "project_path") or "", _current_plate(), _live_values()
    job_id, source = sess.new_job()
    try:
        ok = plater.export_3mf_copy(source)
    except Exception as e:
        raise CommandError("export_failed", str(e)) from None
    if ok is False or not os.path.isfile(source):
        raise CommandError("export_failed", "OrcaSlicer did not write the project copy")

    def progress(done, total):
        page.post_message({"type": "progress", "job": job_id, "stage": "meshes", "done": done, "total": total})

    _worker(page, msg_id, lambda: sess.load(job_id, project, plate, live, progress))


def _cmd_project_apply(page, args, msg_id):
    sess = get_session(page)
    _worker(page, msg_id, lambda: sess.apply(args))


def _cmd_project_open(page, args):
    """UI thread: hand an applied copy (a .3mf directly in the storage folder) to OrcaSlicer."""
    path = args.get("path")
    folder = os.path.realpath(_storage_or_raise())
    real = os.path.realpath(path) if isinstance(path, str) else ""
    if not (real.endswith(".3mf") and os.path.isfile(real) and os.path.dirname(real) == folder):
        raise CommandError("bad_request", "only an applied copy in the plugin folder can be opened")
    try:
        opened = _open_in_orca(real)   # the checked file itself, not a link that could change later
    except Exception as e:
        raise CommandError("open_failed", str(e)) from None
    return {"open": "asked" if opened else "none"}


def _worker(page, msg_id, fn):
    def run():
        try:
            page.reply(msg_id, fn())
        except session.SessionError as e:
            page.reply(msg_id, error={"code": e.code, "detail": e.detail})
        except Exception as e:
            log("worker failed: %r" % e)
            page.reply(msg_id, error={"code": "internal", "detail": str(e)})
    threading.Thread(target=run, daemon=True).start()


COMMANDS = {
    "hello": _cmd_hello,
    "settings.get": _cmd_settings_get,
    "settings.save": _cmd_settings_save,
    "presets.list": _cmd_presets_list,
    "presets.save": _cmd_presets_save,
    "presets.delete": _cmd_presets_delete,
    "mesh.chunk": lambda page, args: get_session(page).mesh_chunk(args),
    "pocket.plan": lambda page, args: get_session(page).plan(args),
    "project.open": _cmd_project_open,
    "copies.status": lambda page, args: get_session(page).copies_status(),
    "copies.clear": lambda page, args: get_session(page).clear_copies(),
}
ASYNC_COMMANDS = {"project.load": _cmd_project_load, "project.apply": _cmd_project_apply}


# ====================================================================== Embedder tab

class EmbedderPage(orca.pages.PagesPluginCapabilityBase):
    def get_name(self):
        return "Embedder"

    def get_icon(self):
        """The icon file in the plugin storage folder (data_dir(), writable for the plugin); none without it.

        The brand tile at 40x40 RGBA with a transparent surround (OrcaSlicer draws it at 20 px). The host tries an .svg of the same name before the
        .png, so the file is not called embedder.png: 0.4.0 and earlier left an embedder.svg in this folder."""
        png = _asset("icon.png")
        for folder in [f for f in [_storage()] if f]:
            path = os.path.join(folder, "embedder-icon.png")
            try:
                try:
                    with open(path, "rb") as f:
                        same = f.read() == png
                except OSError:
                    same = False
                if not same:
                    with open(path, "wb") as f:
                        f.write(png)
                return path
            except OSError as e:
                log("icon: can't write %s (%s)" % (path, e))
        return ""

    def get_default_config(self):
        return {}

    def get_ui(self):
        return page_html(get_store(self).effective()["ui_language"])

    def reply(self, msg_id, result=None, error=None):
        if error is None:
            self.post_message({"type": "reply", "id": msg_id, "result": result})
        else:
            self.post_message({"type": "reply", "id": msg_id, "error": error})

    def on_message(self, data):
        if not isinstance(data, dict):
            return
        _storage()
        kind, msg_id = data.get("type"), data.get("id")
        if kind == "ui_language":
            try:
                get_store(self).update({"ui_language": data.get("value")})
            except Exception as e:   # a notice with no reply: log it, never raise into OrcaSlicer's callback
                log("ui_language not saved: %r" % e)
            return
        if kind != "cmd":
            return
        cmd = data.get("cmd")
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        try:
            if cmd in ASYNC_COMMANDS:
                ASYNC_COMMANDS[cmd](self, args, msg_id)
                return
            if cmd not in COMMANDS:
                raise CommandError("unknown_command", str(cmd))
            self.reply(msg_id, COMMANDS[cmd](self, args))
        except (CommandError, session.SessionError, presets.PresetError) as e:
            self.reply(msg_id, error={"code": e.code, "detail": e.detail})
        except Exception as e:
            log("command %s failed: %r" % (data.get("cmd"), e))
            self.reply(msg_id, error={"code": "internal", "detail": str(e)})

    def on_load(self):
        _storage()

    def on_unload(self):
        pass


@orca.plugin
class Embedder(orca.base):
    def register_capabilities(self):
        _storage()
        # Work on project copies runs on the plugin's own threads; everything stays inside the storage folder.
        orca.request_permissions(threading=True)
        orca.register_capability(EmbedderPage)
