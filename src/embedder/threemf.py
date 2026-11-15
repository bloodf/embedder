"""Read an Orca/Bambu 3MF project (objects, parts, transforms, plates, settings, pauses) and write a copy with
Embedder's negative parts and pauses. XML is edited as text so everything else stays byte for byte; zip entries
that are not edited are copied as they are. Nothing is extracted to disk. Free of `orca`."""

import json
import math
import os
import html
import re
import shutil
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
import zipfile
import zlib
from array import array
from dataclasses import dataclass, field
from xml.sax.saxutils import quoteattr

import geometry

CORE_URI = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD_URI = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
CORE, PROD = "{%s}" % CORE_URI, "{%s}" % PROD_URI
UNIT = "millimeter"
PLATE_GAP = 0.2            # Orca lays plates out at 1.2x the bed size (LOGICAL_PART_PLATE_GAP)
SETTINGS = "Metadata/model_settings.config"
PROJECT = "Metadata/project_settings.config"
GCODES = "Metadata/custom_gcode_per_layer.xml"
PROFILE = "Metadata/layer_heights_profile.txt"
RANGES = "Metadata/layer_config_ranges.xml"
CUT = "Metadata/cut_information.xml"
PART_PREFIX = "Embedder "
PAUSE_PREFIX = "Embedder:"
PART_NAME_RE = re.compile(r"^Embedder (.+) \((embedded|open)\)$")


class ThreeMFError(ValueError):
    """A project this module cannot read or edit safely; `code` is stable for the page."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class MeshData:
    positions: array      # float32 x y z ..., object-local
    indices: array        # uint32 v1 v2 v3 ...
    bbox: tuple = ()      # (min x, min y, min z, max x, max y, max z); () for an empty mesh


@dataclass(frozen=True)
class Part:
    id: str               # component objectid (= model_settings part id)
    name: str
    subtype: str
    matrix: tuple         # part -> object
    file: str             # model file holding the mesh
    extruder: str = ""


@dataclass(frozen=True)
class ModelObject:
    id: str
    name: str
    index: int            # 1-based model object index (layer ranges, cut info)
    parts: tuple
    extruder: str
    uses_path: bool       # components carry p:path
    plain: bool = False   # a bare mesh object without components
    layer_height: str = ""


@dataclass(frozen=True)
class Item:
    index: int
    object_id: str
    transform: tuple
    printable: bool
    plate: int = None


@dataclass(frozen=True)
class Layer:
    plate: int
    top_z: float
    type: str
    extra: str
    gcode: str
    embedder: bool


@dataclass(frozen=True)
class EmbedderPart:
    id: str
    object_id: str
    name: str
    label: str
    mode: str


@dataclass(frozen=True)
class Addition:
    """A new negative part: mesh in its local frame and the local -> plate frame transform."""
    object_id: str
    item: int             # the build item (instance) the transform was planned on
    name: str
    verts: tuple
    tris: tuple
    transform: tuple


@dataclass(frozen=True)
class Package:
    path: str
    main_name: str
    objects: dict
    items: tuple
    meshes: dict          # (file, object id) -> MeshData
    project: dict
    fallback: dict
    plate_count: int
    plate_meta: dict      # plate -> {key: value} from model_settings
    listed: dict          # (object id, instance number) -> plate, from model_settings <model_instance>
    layers: tuple
    profile: bool         # a variable layer height profile is present
    ranges: frozenset     # model object indexes with a layer_height range
    cut: frozenset        # model object indexes with cut connectors
    bed: tuple = None     # ((min x, min y), (max x, max y)) of the printable area
    config_source: str = field(default="project")

    def setting(self, key):
        value = self.project[key] if key in self.project else self.fallback.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        return value

    def plate_origin(self, plate):
        if self.bed is None or plate <= 1:
            return (0.0, 0.0)
        cols = max(1, math.ceil(math.sqrt(self.plate_count)))
        row, col = divmod(plate - 1, cols)
        (x0, y0), (x1, y1) = self.bed
        return (round(col * (x1 - x0) * (1 + PLATE_GAP), 6), round(-row * (y1 - y0) * (1 + PLATE_GAP), 6))

    def to_plate(self, item):
        """Object frame -> plate frame for a build item."""
        ox, oy = self.plate_origin(item.plate or 1)
        return geometry.mul(geometry.translation(-ox, -oy, 0), item.transform)

    def item(self, index):
        """The build item with this position in <build> (Item.index)."""
        for it in self.items:
            if it.index == index:
                return it
        raise ThreeMFError("bad_item", "no build item %s" % index)

    def plate_mesh(self, item, part):
        """Plate-frame float32 positions and uint32 indices, wound outward (flipped when mirrored)."""
        m = geometry.mul(self.to_plate(item), part.matrix)
        mesh = self.meshes[(part.file, part.id)]
        src = mesh.positions
        xs, ys, zs = src[0::3], src[1::3], src[2::3]
        pos = array("f", bytes(4 * len(src)))
        for row in range(3):
            a, b, c, d = m[row * 4:row * 4 + 4]
            pos[row::3] = array("f", [a * x + b * y + c * z + d for x, y, z in zip(xs, ys, zs)])
        idx = array("I", mesh.indices)
        if geometry.det(m) < 0:
            idx[1::3], idx[2::3] = idx[2::3], idx[1::3]
        return pos, idx

    def embedder_parts(self):
        out = []
        for obj in self.objects.values():
            for p in obj.parts:
                m = PART_NAME_RE.match(p.name)
                if p.subtype == "negative_part" and m:
                    out.append(EmbedderPart(p.id, obj.id, p.name, m.group(1), m.group(2)))
        return tuple(out)

    def instances_rigid(self, object_id):
        mats = [i.transform for i in self.items if i.object_id == object_id]
        first = geometry.inverse(mats[0]) if mats else None
        return all(geometry.rigid_z(geometry.mul(first, m)) and abs(m[11] - mats[0][11]) < 1e-6 for m in mats[1:])

    def variable_layers(self, object_id):
        return self.profile or self.objects[object_id].index in self.ranges

    def has_cut_connectors(self, object_id):
        return self.objects[object_id].index in self.cut


# ---------------------------------------------------------------- reading

def _text(zf, name):
    return zf.read(name).decode("utf-8")


def _main_name(zf, names):
    rels = _text(zf, "_rels/.rels") if "_rels/.rels" in names else ""
    m = re.search(r'Target="/?([^"]+\.model)"', rels)
    name = m.group(1) if m else "3D/3dmodel.model"
    if name not in names:
        raise ThreeMFError("no_model", "no 3D model in the project")
    return name


def _resolve(path_attr, current, names):
    if not path_attr:
        return current
    name = path_attr.lstrip("/")
    if name not in names and urllib.parse.unquote(name) in names:
        name = urllib.parse.unquote(name)
    if name not in names:
        raise ThreeMFError("missing_model_file", name)
    return name


def _parse_model(zf, name, names):
    """{object id: (mesh or None, ((file, objectid, transform, has_path), ...))}, build items, object ids in order."""
    try:
        with zf.open(name) as f:
            return _walk(ET.iterparse(f, events=("start", "end")), name, names)
    except ET.ParseError as e:
        raise ThreeMFError("bad_xml", "%s: %s" % (name, e)) from None
    except ThreeMFError:
        raise
    except (ValueError, TypeError) as e:
        raise ThreeMFError("bad_xml", "%s: %s" % (name, e)) from None


def _walk(events, name, names):
    """Stream one model file: vertices and triangles go straight into arrays and their elements are cleared."""
    objects, items, order = {}, [], []
    cur = verts = tris = comps = None
    for event, elem in events:
        tag = elem.tag
        if event == "start":
            if tag == CORE + "model" and elem.get("unit", UNIT) != UNIT:
                raise ThreeMFError("bad_unit", "unit %s is not supported; only millimetre files" % elem.get("unit"))
            if tag == CORE + "object":
                cur, verts, tris, comps = elem.get("id"), None, None, []
            elif tag == CORE + "mesh":
                verts, tris = array("f"), array("I")
        elif tag == CORE + "vertex":
            verts.extend((float(elem.get("x")), float(elem.get("y")), float(elem.get("z"))))
            elem.clear()
        elif tag == CORE + "triangle":
            tris.extend((int(elem.get("v1")), int(elem.get("v2")), int(elem.get("v3"))))
            elem.clear()
        elif tag == CORE + "component":
            path = elem.get(PROD + "path")
            comps.append((_resolve(path, name, names), elem.get("objectid"), geometry.from_3mf(elem.get("transform")),
                          path is not None))
        elif tag == CORE + "object":
            objects[cur] = (_mesh(cur, verts, tris), tuple(comps))
            order.append(cur)
            elem.clear()
        elif tag == CORE + "item":
            items.append((elem.get("objectid"), geometry.from_3mf(elem.get("transform")), elem.get("printable") != "0"))
    return objects, items, order


def _mesh(oid, verts, tris):
    if verts is None:
        return None
    if tris and max(tris) >= len(verts) // 3:
        raise ThreeMFError("bad_mesh", "object %s has a triangle outside its vertices" % oid)
    if not verts:
        return MeshData(verts, tris)
    axes = [verts[k::3] for k in range(3)]
    return MeshData(verts, tris, tuple(min(a) for a in axes) + tuple(max(a) for a in axes))


def _model_settings(text):
    objects, plates, listed = {}, {}, {}
    if not text:
        return objects, plates, listed
    root = ET.fromstring(text)
    for obj in root.iter("object"):
        meta = {m.get("key"): m.get("value", "") for m in obj.findall("metadata")}
        parts = {}
        for p in obj.findall("part"):
            pm = {m.get("key"): m.get("value", "") for m in p.findall("metadata")}
            parts[p.get("id")] = {"name": pm.get("name", ""), "subtype": p.get("subtype", "normal_part"),
                                  "extruder": pm.get("extruder", "")}
        objects[obj.get("id")] = {"name": meta.get("name", ""), "extruder": meta.get("extruder") or "1",
                                  "layer_height": meta.get("layer_height", ""), "parts": parts}
    for n, plate in enumerate(root.iter("plate"), 1):
        meta = {m.get("key"): m.get("value", "") for m in plate.findall("metadata")}
        pid = int(meta.get("plater_id") or n)
        plates[pid] = meta
        for mi in plate.findall("model_instance"):
            kv = {m.get("key"): m.get("value", "") for m in mi.findall("metadata")}
            if kv.get("object_id") and (kv.get("instance_id") or "0").isdigit():
                listed.setdefault((kv["object_id"], int(kv.get("instance_id") or 0)), pid)
    return objects, plates, listed


def _objects(models, main, order, items, meta):
    """Top-level objects referenced by the build, with their parts resolved through components."""
    referenced = {oid for oid, _, _ in items}
    out = {}
    for oid in [o for o in order if o in referenced]:
        mesh, comps = models[main][0][oid]
        info = meta.get(oid, {"name": "", "extruder": "1", "layer_height": "", "parts": {}})
        if mesh is not None:
            parts = (Part(oid, info["name"], "normal_part", geometry.IDENTITY, main),)
        else:
            parts = tuple(_part(models, file, cid, t, info) for file, cid, t, _ in comps)
        out[oid] = ModelObject(oid, info["name"] or "object %s" % oid, len(out) + 1, parts, info["extruder"],
                               any(c[3] for c in comps), mesh is not None, info["layer_height"])
    return out


def _part(models, file, cid, transform, info):
    target = models[file][0].get(cid)
    if target is None or target[0] is None:
        raise ThreeMFError("nested_components", "component %s is not a mesh" % cid)
    p = info["parts"].get(cid, {})
    return Part(cid, p.get("name", ""), p.get("subtype", "normal_part"), transform, file, p.get("extruder", ""))


def _layers(text):
    if not text:
        return ()
    out = []
    for plate in ET.fromstring(text).iter("plate"):
        info = plate.find("plate_info")
        pid = int(info.get("id")) if info is not None else 1
        for layer in plate.iter("layer"):
            if layer.get("top_z") is None:
                continue
            extra = layer.get("extra", "")
            out.append(Layer(pid, float(layer.get("top_z")), layer.get("type", ""), extra, layer.get("gcode", ""),
                             extra.startswith(PAUSE_PREFIX)))
    return tuple(out)


def _indexes(text, child_test):
    if not text:
        return frozenset()
    return frozenset(int(o.get("id")) for o in ET.fromstring(text).iter("object") if child_test(o))


def _has_layer_range(obj):
    return any(opt.get("opt_key") == "layer_height" for opt in obj.iter("option"))


def _has_connectors(obj):
    cut_id = obj.find("cut_id")
    return obj.find("connectors") is not None or (cut_id is not None and int(cut_id.get("connectors_cnt", "0")) > 0)


def _bed(value):
    if isinstance(value, str):
        value = value.split(",")
    try:
        pts = [tuple(float(c) for c in str(p).split("x")) for p in value or []]
    except ValueError:
        return None
    if len(pts) < 3:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys)), (max(xs), max(ys))


def _project(zf, names):
    if PROJECT not in names:
        return {}
    try:
        data = json.loads(_text(zf, PROJECT) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def read(path, fallback=None):
    """Parse a project. `fallback`: preset values used when the project does not carry a setting."""
    if not os.path.isfile(path):
        raise ThreeMFError("not_found", str(path))
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise ThreeMFError("bad_package", str(e)) from None
    with zf:
        try:
            return _read(zf, path, dict(fallback or {}))
        except ThreeMFError:
            raise
        except (ET.ParseError, KeyError, zipfile.BadZipFile, ValueError, TypeError, EOFError, zlib.error) as e:
            raise ThreeMFError("bad_package", "%s: %s" % (type(e).__name__, e)) from None


def _read(zf, path, fallback):
    names = set(zf.namelist())
    main = _main_name(zf, names)
    models = {main: _parse_model(zf, main, names)}
    for _, comps in list(models[main][0].values()):
        for file, _, _, _ in comps:
            if file not in models:
                models[file] = _parse_model(zf, file, names)
    meta, plate_meta, listed = _model_settings(_text(zf, SETTINGS) if SETTINGS in names else "")
    raw_items = models[main][1]
    objects = _objects(models, main, models[main][2], raw_items, meta)
    meshes = {(file, oid): mesh for file, (objs, _, _) in models.items() for oid, (mesh, _) in objs.items() if mesh is not None}
    project = _project(zf, names)
    pkg = Package(path=str(path), main_name=main, objects=objects,
                  items=tuple(Item(i, oid, t, printable) for i, (oid, t, printable) in enumerate(raw_items) if oid in objects),
                  meshes=meshes, project=project, fallback=fallback, plate_count=max(1, len(plate_meta)),
                  plate_meta=plate_meta, listed=listed, layers=_layers(_text(zf, GCODES) if GCODES in names else ""),
                  profile=PROFILE in names and bool(_text(zf, PROFILE).strip()),
                  ranges=_indexes(_text(zf, RANGES) if RANGES in names else "", _has_layer_range),
                  cut=_indexes(_text(zf, CUT) if CUT in names else "", _has_connectors),
                  config_source="project" if project else "preset")
    pkg = Package(**{**pkg.__dict__, "bed": _bed(project.get("printable_area", fallback.get("printable_area")))})
    seen, items = {}, []
    for it in pkg.items:
        n = seen.get(it.object_id, 0)
        seen[it.object_id] = n + 1
        plate = pkg.listed.get((it.object_id, n)) or _plate_of(pkg, it)
        items.append(Item(it.index, it.object_id, it.transform, it.printable, plate))
    return Package(**{**pkg.__dict__, "items": tuple(items)})


def _plate_of(pkg, item):
    """Fallback when model_settings does not list the instance: the first plate whose area the item's bounding
    box touches (Orca: PartPlateList::reload_all_objects), from the parts' cached boxes."""
    if pkg.plate_count == 1:
        return 1
    if pkg.bed is None:
        raise ThreeMFError("no_bed", "the printable area is unknown; plates cannot be told apart")
    xs, ys = [], []
    for part in pkg.objects[item.object_id].parts:
        box = pkg.meshes[(part.file, part.id)].bbox
        if part.subtype != "normal_part" or not box:
            continue
        m = geometry.mul(item.transform, part.matrix)
        for corner in ((x, y, z) for x in (box[0], box[3]) for y in (box[1], box[4]) for z in (box[2], box[5])):
            x, y, _ = geometry.apply(m, corner)
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    (bx0, by0), (bx1, by1) = pkg.bed
    for plate in range(1, pkg.plate_count + 1):
        ox, oy = Package.plate_origin(pkg, plate)
        if min(xs) <= ox + bx1 and max(xs) >= ox + bx0 and min(ys) <= oy + by1 and max(ys) >= oy + by0:
            return plate
    return None


# ---------------------------------------------------------------- writing

def _prefix(text, uri):
    """The first non-empty XML prefix bound to `uri` in text, or None."""
    for m in re.finditer(r"""\sxmlns:([\w.-]+)\s*=\s*(["'])(.*?)\2""", text):
        if m.group(3) == uri:
            return m.group(1)
    return None


def _object_span(text, oid, settings=False):
    pattern = r'<object id="%s">.*?</object>' if settings else r'<object\b[^>]*?\sid="%s"[^>]*>.*?</object>'
    m = re.search(pattern % re.escape(oid), text, re.S)
    if not m:
        raise ThreeMFError("xml_layout", "object %s not found where expected" % oid)
    return m.span()


def _insert_before(text, span, closing, block):
    """Insert `block` (whole lines) at the start of the line holding the last `closing` tag inside span."""
    a, b = span
    at = text.rfind(closing, a, b)
    if at < 0:
        raise ThreeMFError("xml_layout", "%s not found where expected" % closing)
    nl = text.rfind("\n", a, at)
    line = nl + 1 if nl >= 0 else at   # one-line XML: right before the tag itself
    return text[:line] + block + text[line:]


def _remove(text, span, pattern):
    a, b = span
    new, n = re.subn(pattern, "", text[a:b], count=1, flags=re.S)
    if n != 1:
        raise ThreeMFError("xml_layout", "entry not found for removal")
    return text[:a] + new + text[b:]


def _max_id(texts):
    return max([int(v) for t in texts for v in re.findall(r'(?<![\w:])(?:id|objectid)="(\d+)"', t)] or [0])


def _mesh_object(oid, verts, tris, prod):
    uid = ' %s:UUID="%s"' % (prod, uuid.uuid4()) if prod else ""
    v = "".join('     <vertex x="%s" y="%s" z="%s"/>\n' % tuple(geometry.fmt(c) for c in p) for p in verts)
    t = "".join('     <triangle v1="%d" v2="%d" v3="%d"/>\n' % tri for tri in tris)
    return ('  <object id="%s"%s type="other">\n   <mesh>\n    <vertices>\n%s    </vertices>\n    <triangles>\n%s'
            '    </triangles>\n   </mesh>\n  </object>\n' % (oid, uid, v, t))


def _part_xml(oid, name, matrix, extruder, faces):
    return ('    <part id="%s" subtype="negative_part">\n      <metadata key="name" value=%s/>\n'
            '      <metadata key="matrix" value="%s"/>\n      <metadata key="extruder" value="%s"/>\n'
            '      <mesh_stat face_count="%d" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
            '    </part>\n' % (oid, quoteattr(name), geometry.to_config(matrix), extruder, faces))


def _component_matrix(pkg, add):
    """Object frame transform of the new part: inverse(item) x pocket world, made right-handed."""
    item = pkg.item(add.item)
    world = geometry.mul(geometry.translation(*pkg.plate_origin(item.plate or 1), 0), add.transform)
    m = geometry.mul(geometry.inverse(item.transform), world)
    return geometry.mul(m, geometry.scale(-1, 1, 1)) if geometry.det(m) < 0 else m


class _Edit:
    """Texts being edited, read lazily from the source zip."""

    def __init__(self, zf):
        self.zf, self.texts = zf, {}

    def get(self, name):
        if name not in self.texts:
            self.texts[name] = _text(self.zf, name)
        return self.texts[name]

    def set(self, name, text):
        self.texts[name] = text


def _remove_part(pkg, ed, pid):
    owner = next((o for o in pkg.objects.values() for p in o.parts if p.id == pid), None)
    if owner is None or pid not in {e.id for e in pkg.embedder_parts()}:
        raise ThreeMFError("not_embedder_part", "part %s is not an Embedder pocket" % pid)
    part = next(p for p in owner.parts if p.id == pid)
    main = ed.get(pkg.main_name)
    ed.set(pkg.main_name, _remove(main, _object_span(main, owner.id),
                                  r'[ \t]*<component\b[^>]*?\sobjectid="%s"[^>]*/>[ \t]*\n?' % re.escape(pid)))
    text = ed.get(part.file)
    ed.set(part.file, _remove(text, (0, len(text)), r'[ \t]*<object\b[^>]*?\sid="%s"[^>]*>.*?</object>[ \t]*\n?' % re.escape(pid)))
    cfg = ed.get(SETTINGS)
    ed.set(SETTINGS, _remove(cfg, _object_span(cfg, owner.id, True), r'[ \t]*<part id="%s"[^>]*>.*?</part>[ \t]*\n?' % re.escape(pid)))


def _component_tag(main_obj_text, first_part, new_id, matrix, prod):
    """The new <component>: its p:path names the file the new mesh went into, the file of the first part."""
    first = re.search(r'<[\w.:-]*component\b[^>]*?\sobjectid="%s"[^>]*>' % re.escape(first_part), main_obj_text)
    path = re.search(r'\s([\w.-]+:path)="([^"]*)"', first.group(0)) if first else None
    attrs = ' %s="%s"' % (path.group(1), path.group(2)) if path else ""
    uid = ' %s:UUID="%s"' % (prod, uuid.uuid4()) if prod else ""
    return '    <component%s objectid="%s"%s transform="%s"/>\n' % (attrs, new_id, uid, geometry.to_3mf(matrix))


def _add_part(pkg, ed, add, new_id):
    obj = pkg.objects.get(add.object_id)
    if obj is None or obj.plain:
        raise ThreeMFError("unsupported_object", "object %s has no parts list to add to" % add.object_id)
    if pkg.has_cut_connectors(obj.id):
        raise ThreeMFError("cut_object", "object %s was cut with connectors" % obj.name)
    matrix = _component_matrix(pkg, add)
    target = obj.parts[0].file
    text = ed.get(target)
    mesh = _mesh_object(new_id, add.verts, add.tris, _prefix(text, PROD_URI))
    if target == pkg.main_name:   # inline meshes: define the new one before the object that references it
        a = _object_span(text, obj.id)[0]
        nl = text.rfind("\n", 0, a)
        at = nl + 1 if text[nl + 1:a].strip() == "" else a
        ed.set(target, text[:at] + mesh + text[at:])
    else:
        ed.set(target, _insert_before(text, (0, len(text)), "</resources>", mesh))
    main = ed.get(pkg.main_name)
    span = _object_span(main, obj.id)
    tag = _component_tag(main[span[0]:span[1]], obj.parts[0].id, new_id, matrix, _prefix(main, PROD_URI))
    ed.set(pkg.main_name, _insert_before(main, span, "</components>", tag))
    cfg = ed.get(SETTINGS)
    ed.set(SETTINGS, _insert_before(cfg, _object_span(cfg, obj.id, True), "</object>",
                                    _part_xml(new_id, add.name, matrix, obj.extruder, len(add.tris))))


def _layer_tag(z, extra):
    return '<layer top_z="%s" type="1" extruder="1" color="" extra=%s gcode=""/>' % (geometry.fmt(z), quoteattr(extra))


def _top_z(tag):
    m = re.search(r'\stop_z="([^"]*)"', tag)
    try:
        return float(m.group(1)) if m else -math.inf
    except ValueError:
        return -math.inf


def _plate_block(plate, kept, pauses, mode):
    """The <plate> block, or "" when nothing is left in it. Entries without a height are kept, first."""
    tags = [(_top_z(t), t) for t in kept] + [(z, _layer_tag(z, extra)) for z, extra in pauses]
    if not tags:
        return ""
    body = "".join(t + "\n" for _, t in sorted(tags, key=lambda x: x[0]))
    return '<plate>\n<plate_info id="%d"/>\n%s%s\n</plate>' % (plate, body, mode)


def mode_tag(filaments):
    """The mode a new plate block gets: one filament prints as SingleExtruder, otherwise MultiExtruder."""
    return '<mode value="%s"/>' % ("SingleExtruder" if filaments == 1 else "MultiExtruder")


def gcode_xml(text, plate, pauses, new_mode='<mode value="MultiExtruder"/>'):
    """custom_gcode_per_layer.xml with every Embedder entry of `plate` replaced by `pauses`; all else kept.
    A plate block left empty is dropped; None when there is no file and nothing to write."""
    if not text:
        if not pauses:
            return None
        text = '<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n</custom_gcodes_per_layer>\n'
    for m in re.finditer(r"<plate>(.*?)</plate>\s*", text, re.S):
        info = re.search(r'<plate_info id="(\d+)"', m.group(1))
        if info and int(info.group(1)) == plate:
            layers = re.findall(r"<layer\b[^>]*/>", m.group(1))
            kept = [t for t in layers if not _attr_extra(t).startswith(PAUSE_PREFIX)]
            mode = re.search(r"<mode\b[^>]*/>", m.group(1))
            block = _plate_block(plate, kept, pauses, mode.group(0) if mode else new_mode)
            return text[:m.start()] + (block + "\n" if block else "") + text[m.end():]
    if not pauses:
        return text
    end = text.rfind("</custom_gcodes_per_layer>")
    if end < 0:
        raise ThreeMFError("xml_layout", "custom_gcode_per_layer.xml has no root")
    return text[:end] + _plate_block(plate, [], pauses, new_mode) + "\n" + text[end:]


def _filaments(pkg):
    colours = pkg.project.get("filament_colour", pkg.fallback.get("filament_colour"))
    return len(colours) if isinstance(colours, list) else None


def _publish(tmp, out):
    """Move the finished temporary file to `out` without ever replacing an existing file: a hard link fails
    when `out` exists; where links are not supported, an exclusive create does the same job."""
    try:
        os.link(tmp, out)
        return
    except FileExistsError:
        raise ThreeMFError("exists", out) from None
    except OSError:
        pass
    try:
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
    except FileExistsError:
        raise ThreeMFError("exists", out) from None
    try:
        with os.fdopen(fd, "wb") as dst, open(tmp, "rb") as src:
            shutil.copyfileobj(src, dst)
    except BaseException:
        os.remove(out)
        raise


def _attr_extra(tag):
    m = re.search(r'\sextra="([^"]*)"', tag)
    return html.unescape(m.group(1)) if m else ""


def write(pkg, out, plate, additions=(), removals=(), pauses=()):
    """Write a copy of pkg to `out` (never overwritten) through a temporary file next to it."""
    out = str(out)
    if os.path.exists(out):
        raise ThreeMFError("exists", out)
    tmp = "%s.%s.tmp" % (out, uuid.uuid4().hex[:8])
    try:
        with zipfile.ZipFile(pkg.path) as zin:
            ed = _Edit(zin)
            for pid in removals:
                _remove_part(pkg, ed, pid)
            if additions:
                models = {pkg.main_name, SETTINGS, *(p.file for o in pkg.objects.values() for p in o.parts)}
                next_id = _max_id([ed.get(n) for n in sorted(models) if n in zin.namelist()]) + 1
                for k, add in enumerate(additions):
                    _add_part(pkg, ed, add, str(next_id + k))
            names = zin.namelist()
            gcodes = gcode_xml(ed.get(GCODES) if GCODES in names else "", plate, pauses, mode_tag(_filaments(pkg)))
            if gcodes is not None:
                ed.set(GCODES, gcodes)
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                for info in zin.infolist():
                    data = ed.texts[info.filename].encode("utf-8") if info.filename in ed.texts else zin.read(info)
                    zout.writestr(info, data)
                if GCODES not in names and GCODES in ed.texts:
                    new = zipfile.ZipInfo(GCODES, date_time=zin.getinfo(pkg.main_name).date_time)
                    new.compress_type = zipfile.ZIP_DEFLATED
                    zout.writestr(new, ed.texts[GCODES].encode("utf-8"))
        _publish(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

