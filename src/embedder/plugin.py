"""OrcaSlicer glue: the Embedder tab. The only module that imports `orca`."""

import json
import os
import re
import sys
import threading

import orca

import settings

VERSION = "0.0.0-dev"

_store = None
_store_lock = threading.Lock()
_storage_dir = None


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


def _read_svg(path):
    with open(path, encoding="utf-8") as f:
        svg = re.sub(r"<\?xml.*?\?>|<!--.*?-->|\s+id=\"[^\"]*\"", "", f.read(), flags=re.S)
    return re.sub(r">\s+<", "><", svg.replace('role="img"', 'aria-hidden="true"')).strip()


def _with_icons(html):
    """Development twin of build.page_html: inline the icons the page references."""
    ui = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
    used = {}
    for prefix, folder in (("icon", "icons"), ("spot", "")):
        for fname in sorted(os.listdir(os.path.join(ui, folder))):
            if not fname.endswith(".svg") or (not folder and not fname.startswith("spot-")):
                continue
            key = "%s/%s" % (prefix, fname[5:-4] if prefix == "spot" else fname[:-4])
            if key in html:
                used[key] = _read_svg(os.path.join(ui, folder, fname))
    return html.replace("__ICONS__", json_for_html(used))


def _asset(name):
    """From the generated _assets module in the wheel; from src/embedder/ui during development."""
    if __package__:
        from . import _assets
        return {"app.html": _assets.APP_HTML, "icon.svg": _assets.ICON_SVG}[name]
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", name), encoding="utf-8") as f:
        text = f.read()
    return _with_icons(text) if name.endswith(".html") else text


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


# ---------------------------------------------------------------------- commands

class CommandError(Exception):
    """An error the page shows: a stable code plus a human detail."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code, self.detail = code, detail


def _cmd_hello(page, args):
    return {"version": VERSION, "settings": get_store(page).effective()}


def _cmd_settings_get(page, args):
    return get_store(page).effective()


def _cmd_settings_save(page, args):
    return get_store(page).update(dict(args.get("settings") or {}))


COMMANDS = {
    "hello": _cmd_hello,
    "settings.get": _cmd_settings_get,
    "settings.save": _cmd_settings_save,
}


# ====================================================================== Embedder tab

class EmbedderPage(orca.pages.PagesPluginCapabilityBase):
    def get_name(self):
        return "Embedder"

    def get_icon(self):
        """The icon file in the plugin storage folder (data_dir(), writable for the plugin); none without it."""
        svg = _asset("icon.svg")
        for folder in [f for f in [_storage()] if f]:
            path = os.path.join(folder, "embedder.svg")
            try:
                try:
                    with open(path, encoding="utf-8") as f:
                        same = f.read() == svg
                except OSError:
                    same = False
                if not same:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(svg)
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
            get_store(self).update({"ui_language": data.get("value")})
            return
        if kind != "cmd":
            return
        handler = COMMANDS.get(data.get("cmd"))
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        try:
            if handler is None:
                raise CommandError("unknown_command", str(data.get("cmd")))
            self.reply(msg_id, handler(self, args))
        except CommandError as e:
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
