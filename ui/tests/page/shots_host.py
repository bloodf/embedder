"""The real plugin behind the screenshots in shots.mjs: plugin.py under the test double of `orca` (tests/fake_orca.py),
with a project built by tests/fixtures.py. Reads the page's messages as JSON lines on stdin and writes the plugin's
messages as JSON lines on stdout, so every reply the page draws (meshes, plans, pauses, the applied copy) is the
plugin's own answer. Storage is a temporary folder that is removed on exit.

    python3 ui/tests/page/shots_host.py
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder"), os.path.join(ROOT, "tests")]

import fake_orca  # noqa: E402
import fixtures  # noqa: E402

SHOWN_STORAGE = "~/OrcaSlicer/plugins/embedder"   # where the result card says the copy went
NAMES = {"en": ("Fridge tile", "Badge"), "pt-BR": ("Ímã de geladeira", "Crachá")}   # the project and its objects, in the page's language
LIVE = {"layer_height": "0.2", "initial_layer_print_height": "0.2", "machine_pause_gcode": "M601",
        "print_sequence": "by layer", "raft_layers": "0", "printable_area": ["0x0", "256x0", "256x256", "0x256"]}


def names():
    return NAMES.get(sys.argv[1] if len(sys.argv) > 1 else "en", NAMES["en"])


def project(path):
    """A fridge tile for magnets and a round badge for an NFC sticker, side by side on plate 1."""
    tile_name, badge_name = names()
    tile = {"name": tile_name, "parts": [fixtures.part(tile_name, fixtures.box(60, 40, 8))]}
    badge = {"name": badge_name, "parts": [fixtures.part(badge_name, fixtures.cylinder(22, 5, n=64))]}
    return fixtures.build(path, objects=[tile, badge],
                          items=[(0, "1 0 0 0 1 0 0 0 1 40 100 0"), (1, "1 0 0 0 1 0 0 0 1 170 120 0")])


def main():
    channel, sys.stdout = sys.stdout, sys.stderr   # the plugin's log lines go to stderr, the stream stays JSON
    work = tempfile.mkdtemp(prefix="embedder-shots-", dir="/tmp" if os.path.isdir("/tmp") else None)
    try:
        storage = os.path.join(work, "storage")
        os.makedirs(storage)
        path = os.path.join(work, names()[0] + ".3mf")
        fake_orca.install_orca(preset=LIVE, storage=storage, source=project(path), project_path=path)
        import plugin
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            plugin.VERSION = tomllib.load(f)["project"]["version"]
        plugin.Embedder().register_capabilities()
        page = plugin.EmbedderPage()
        out = threading.Lock()

        def post(data):
            # the copy's folder as a user would see it, not this run's temporary one (the file name is the plugin's own)
            line = json.dumps(data).replace(json.dumps(storage)[1:-1], SHOWN_STORAGE)
            with out:
                channel.write(line + "\n")
                channel.flush()

        page.post_message = post
        for line in sys.stdin:
            if line.strip():
                page.on_message(json.loads(line))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
