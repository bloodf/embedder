"""Orca-style 3MF projects built in code (no binary fixtures), shaped like the files OrcaSlicer 2.5 writes and like the
Phase 0 spike file that Orca accepted and sliced (scratchpad spike/make.py)."""

import json
import math
import zipfile

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="%s" '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="%s" requiredextensions="p">\n' % (CORE, PROD))
SETTINGS = {"layer_height": "0.2", "initial_layer_print_height": "0.2", "machine_pause_gcode": "M601",
            "print_sequence": "by layer", "raft_layers": "0", "printable_area": ["0x0", "256x0", "256x256", "0x256"]}
IDENT = "1 0 0 0 1 0 0 0 1 0 0 0"
VERSION = ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'


def uid(kind, n):
    """A fixed, well-formed UUID per (kind, number), so fixtures are reproducible."""
    return "%08x-0000-4000-8000-%012x" % (kind, n)
CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                 ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                 ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>\n')


def rels(targets):
    rows = "".join(' <Relationship Target="/%s" Id="rel-%d" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
                   % (t, i) for i, t in enumerate(targets, 1))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            + rows + '</Relationships>\n')


def box(sx, sy, sz, x0=0.0, y0=0.0, z0=0.0):
    v = [(x0 + x, y0 + y, z0 + z) for z in (0, sz) for y in (0, sy) for x in (0, sx)]
    t = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
         (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return v, t


def cylinder(r, h, n=16):
    v = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for z in (0, h) for i in range(n)]
    v += [(0, 0, 0), (0, 0, h)]
    t = []
    for i in range(n):
        j = (i + 1) % n
        t += [(i, j, n + j), (i, n + j, n + i), (2 * n, j, i), (2 * n + 1, n + i, n + j)]
    return v, t


def mesh_xml(mesh):
    verts, tris = mesh
    v = "".join('     <vertex x="%g" y="%g" z="%g"/>\n' % p for p in verts)
    t = "".join('     <triangle v1="%d" v2="%d" v3="%d"/>\n' % p for p in tris)
    return "   <mesh>\n    <vertices>\n%s    </vertices>\n    <triangles>\n%s    </triangles>\n   </mesh>\n" % (v, t)


def part(name, mesh, subtype="normal_part", transform=IDENT):
    return {"name": name, "mesh": mesh, "subtype": subtype, "transform": transform}


def cube_object(name="cube", size=20.0, height=None):
    return {"name": name, "parts": [part(name, box(size, size, height or size))]}


def _matrix16(t3mf):
    a = [float(x) for x in t3mf.split()]
    rows = [[a[0], a[3], a[6], a[9]], [a[1], a[4], a[7], a[10]], [a[2], a[5], a[8], a[11]], [0, 0, 0, 1]]
    return " ".join("%g" % x for r in rows for x in r)


def build(path, objects=None, items=None, plates=1, settings=None, submodel="3D/Objects/object_1.model",
          gcode_xml=None, extra=None, plate_items=None):
    """Write a project. objects: [{name, parts: [part(...)]}]; items: [(object index, 3MF transform)];
    plate_items: [[item index, ...] per plate] (default: every item on plate 1).
    submodel=None keeps every mesh in 3D/3dmodel.model (no p:path)."""
    objects = objects or [cube_object()]
    items = items or [(0, "1 0 0 0 1 0 0 0 1 100 100 0")]
    settings = SETTINGS if settings is None else settings
    mesh_objs, comps_by_obj, next_id = [], [], 1
    for obj in objects:
        comps = []
        for p in obj["parts"]:
            mesh_objs.append('  <object id="%d" p:UUID="%s" type="model">\n%s  </object>\n'
                             % (next_id, uid(1, next_id), mesh_xml(p["mesh"])))
            path_attr = ' p:path="/%s"' % submodel if submodel else ""
            comps.append('    <component%s objectid="%d" p:UUID="%s" transform="%s"/>\n'
                         % (path_attr, next_id, uid(2, next_id), p["transform"]))
            next_id += 1
        comps_by_obj.append(comps)
    tops, settings_objs = [], []
    for k, obj in enumerate(objects):
        oid = next_id + k
        tops.append('  <object id="%d" p:UUID="%s" type="model">\n   <components>\n%s   </components>\n  </object>\n'
                    % (oid, uid(3, oid), "".join(comps_by_obj[k])))
        first = sum(len(o["parts"]) for o in objects[:k]) + 1
        parts = "".join('    <part id="%d" subtype="%s">\n      <metadata key="name" value="%s"/>\n'
                        '      <metadata key="matrix" value="%s"/>\n'
                        '      <mesh_stat face_count="%d" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n    </part>\n'
                        % (first + i, p["subtype"], p["name"], _matrix16(p["transform"]), len(p["mesh"][1]))
                        for i, p in enumerate(obj["parts"]))
        settings_objs.append('  <object id="%d">\n    <metadata key="name" value="%s"/>\n    <metadata key="extruder" value="1"/>\n%s  </object>\n'
                             % (oid, obj["name"], parts))
    build_items = "".join('  <item objectid="%d" p:UUID="%s" transform="%s" printable="1"/>\n'
                          % (next_id + k, uid(4, i), t) for i, (k, t) in enumerate(items))
    plate_items = plate_items or [list(range(len(items)))] + [[] for _ in range(plates - 1)]
    seen = {}

    def instance(i):
        k = items[i][0]
        seen[k] = seen.get(k, -1) + 1
        return ('    <model_instance>\n      <metadata key="object_id" value="%d"/>\n      <metadata key="instance_id" value="%d"/>\n'
                '      <metadata key="identify_id" value="%d"/>\n    </model_instance>\n' % (next_id + k, seen[k], 100 + i))
    plate_xml = "".join('  <plate>\n    <metadata key="plater_id" value="%d"/>\n    <metadata key="plater_name" value=""/>\n'
                        '    <metadata key="locked" value="false"/>\n%s  </plate>\n'
                        % (n + 1, "".join(instance(i) for i in plate_items[n])) for n in range(plates))
    main = HEAD + ' <metadata name="Application">BambuStudio-02.05.00.00</metadata>\n' + VERSION + ' <resources>\n'
    main += ("" if submodel else "".join(mesh_objs)) + "".join(tops) + " </resources>\n"
    main += ' <build p:UUID="%s">\n%s </build>\n</model>\n' % (uid(5, 0), build_items)
    files = {
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": rels(["3D/3dmodel.model"]),
        "3D/3dmodel.model": main,
        "Metadata/model_settings.config": '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n%s%s</config>\n'
                                          % ("".join(settings_objs), plate_xml),
        "Metadata/project_settings.config": json.dumps(settings, indent=4),
        "Metadata/plate_1.png": b"\x89PNG\r\n\x1a\n fake thumbnail \x00\x01",
        "Metadata/slice_info.config": '<?xml version="1.0" encoding="UTF-8"?>\n<config><header/></config>\n',
    }
    if submodel:
        files["3D/_rels/3dmodel.model.rels"] = rels([submodel])
        files[submodel] = HEAD + VERSION + ' <resources>\n%s </resources>\n <build/>\n</model>\n' % "".join(mesh_objs)
    if gcode_xml is not None:
        files["Metadata/custom_gcode_per_layer.xml"] = gcode_xml
    files.update(extra or {})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def user_pause_xml(z, plate=1, extra="", gcode=""):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n<plate>\n<plate_info id="%d"/>\n'
            '<layer top_z="%g" type="2" extruder="1" color="" extra="%s" gcode="%s"/>\n<mode value="SingleExtruder"/>\n</plate>\n'
            '</custom_gcodes_per_layer>\n' % (plate, z, extra, gcode))


# ---------------------------------------------------------------- the named fixtures

def cube(path, **kw):
    return build(path, **kw)


def inline(path, **kw):
    return build(path, submodel=None, **kw)


def multipart_with_negative(path, **kw):
    obj = {"name": "body", "parts": [part("body", box(30, 20, 10)),
                                     part("hole", cylinder(3, 12), "negative_part", "1 0 0 0 1 0 0 0 1 15 10 -1")]}
    return build(path, objects=[obj], **kw)


def spaced_submodel(path, **kw):
    return build(path, submodel="3D/Objects/OrcaSlicer Badge Logo_47.model", **kw)


def rotated_mirrored(path, **kw):
    # mirror in X, then rotate 90 deg about Z, placed at (120, 80)
    return build(path, items=[(0, "0 -1 0 -1 0 0 0 0 1 120 80 0")], **kw)


def two_instances(path, **kw):
    return build(path, items=[(0, "1 0 0 0 1 0 0 0 1 60 100 0"), (0, "0 1 0 -1 0 0 0 0 1 160 100 0")], **kw)


def two_plates(path, **kw):
    # plate 2 sits at x + 256 * 1.2 (Orca's plate gap); one instance on each
    return build(path, items=[(0, "1 0 0 0 1 0 0 0 1 100 100 0"), (0, "1 0 0 0 1 0 0 0 1 407.2 100 0")], plates=2,
                 plate_items=[[0], [1]], **kw)


def empty_settings(path, **kw):
    return build(path, settings={}, **kw)


def user_pause(path, z=19.2, **kw):
    return build(path, gcode_xml=user_pause_xml(z), **kw)
