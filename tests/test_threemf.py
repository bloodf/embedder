import os
import re
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder"), os.path.join(ROOT, "tests")]
import fixtures  # noqa: E402
import geometry as g  # noqa: E402
import threemf  # noqa: E402

FALLBACK = {"layer_height": "0.12", "initial_layer_print_height": "0.2", "machine_pause_gcode": "PAUSE"}


def bbox(positions):
    xs, ys, zs = positions[0::3], positions[1::3], positions[2::3]
    return (round(min(xs), 4), round(min(ys), 4), round(min(zs), 4)), (round(max(xs), 4), round(max(ys), 4), round(max(zs), 4))


def signed_volume(pos, idx):
    total = 0.0
    for k in range(0, len(idx), 3):
        a, b, c = (pos[3 * idx[k + i]:3 * idx[k + i] + 3] for i in range(3))
        total += a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
    return total / 6


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def make(self, builder, name="src.3mf", **kw):
        return builder(os.path.join(self.tmp, name), **kw)

    def read(self, builder, **kw):
        return threemf.read(self.make(builder, **kw), FALLBACK)


class Read(Base):
    def test_cube_with_sub_model(self):
        pkg = self.read(fixtures.cube)
        self.assertEqual(pkg.main_name, "3D/3dmodel.model")
        (item,) = pkg.items
        self.assertEqual((item.plate, item.object_id), (1, "2"))
        obj = pkg.objects["2"]
        self.assertEqual((obj.name, obj.index, obj.extruder), ("cube", 1, "1"))
        (p,) = obj.parts
        self.assertEqual((p.id, p.subtype, p.file, p.name), ("1", "normal_part", "3D/Objects/object_1.model", "cube"))
        pos, idx = pkg.plate_mesh(item, p)
        self.assertEqual(bbox(pos), ((100, 100, 0), (120, 120, 20)))
        self.assertEqual(len(idx), 36)
        self.assertGreater(signed_volume(pos, idx), 0)
        self.assertEqual(pkg.setting("layer_height"), "0.2")
        self.assertEqual(pkg.config_source, "project")
        self.assertEqual(pkg.plate_count, 1)
        self.assertEqual(pkg.layers, ())

    def test_sub_model_name_with_spaces(self):
        pkg = self.read(fixtures.spaced_submodel)
        self.assertEqual(pkg.objects["2"].parts[0].file, "3D/Objects/OrcaSlicer Badge Logo_47.model")
        self.assertEqual(len(pkg.plate_mesh(pkg.items[0], pkg.objects["2"].parts[0])[1]), 36)

    def test_inline_meshes(self):
        pkg = self.read(fixtures.inline)
        p = pkg.objects["2"].parts[0]
        self.assertEqual(p.file, "3D/3dmodel.model")
        self.assertFalse(pkg.objects["2"].uses_path)
        self.assertEqual(bbox(pkg.plate_mesh(pkg.items[0], p)[0]), ((100, 100, 0), (120, 120, 20)))

    def test_multi_part_with_negative_part(self):
        pkg = self.read(fixtures.multipart_with_negative)
        obj = pkg.objects["3"]
        self.assertEqual([(p.name, p.subtype) for p in obj.parts], [("body", "normal_part"), ("hole", "negative_part")])
        self.assertEqual(pkg.embedder_parts(), ())
        lo, hi = bbox(pkg.plate_mesh(pkg.items[0], obj.parts[1])[0])
        self.assertEqual((lo[2], hi[2]), (-1, 11))

    def test_rotated_mirrored_item(self):
        pkg = self.read(fixtures.rotated_mirrored)
        item = pkg.items[0]
        self.assertLess(g.det(item.transform), 0)
        pos, idx = pkg.plate_mesh(item, pkg.objects["2"].parts[0])
        self.assertEqual(bbox(pos), ((100, 60, 0), (120, 80, 20)))
        self.assertGreater(signed_volume(pos, idx), 0, "winding flipped back to outward")

    def test_two_instances_and_rigid_check(self):
        pkg = self.read(fixtures.two_instances)
        self.assertEqual([i.plate for i in pkg.items], [1, 1])
        self.assertTrue(pkg.instances_rigid("2"))
        mirrored = threemf.read(self.make(fixtures.build, name="m.3mf", items=[(0, fixtures.IDENT), (0, "-1 0 0 0 1 0 0 0 1 50 0 0")]))
        self.assertFalse(mirrored.instances_rigid("2"))

    def test_two_plates_by_position(self):
        pkg = self.read(fixtures.two_plates)
        self.assertEqual(pkg.plate_count, 2)
        self.assertEqual([i.plate for i in pkg.items], [1, 2])
        part = pkg.objects["2"].parts[0]
        self.assertEqual(bbox(pkg.plate_mesh(pkg.items[1], part)[0]), bbox(pkg.plate_mesh(pkg.items[0], part)[0]))
        self.assertEqual(pkg.plate_origin(2), (307.2, 0.0))

    def test_plate_membership_comes_from_model_settings_first(self):
        items = [(0, "1 0 0 0 1 0 0 0 1 100 100 0"), (0, "1 0 0 0 1 0 0 0 1 407.2 100 0")]
        pkg = self.read(fixtures.build, items=items, plates=2, plate_items=[[1], [0]])   # lists contradict positions
        self.assertEqual([i.plate for i in pkg.items], [2, 1])
        unlisted = self.read(fixtures.build, name="u.3mf", items=items, plates=2, plate_items=[[], []])
        self.assertEqual([i.plate for i in unlisted.items], [1, 2], "by position when the lists are silent")

    def test_item_lookup_by_index(self):
        pkg = self.read(fixtures.two_instances)
        self.assertIs(pkg.item(1), pkg.items[1])
        with self.assertRaises(threemf.ThreeMFError):
            pkg.item(7)

    def test_layer_without_height_is_skipped(self):
        xml = fixtures.user_pause_xml(5.0).replace("<mode", '<layer type="2" extruder="1" color="" extra="" gcode=""/>\n<mode')
        pkg = self.read(fixtures.build, gcode_xml=xml)
        self.assertEqual([l.top_z for l in pkg.layers], [5.0])

    def test_empty_project_settings_fall_back(self):
        pkg = self.read(fixtures.empty_settings)
        self.assertEqual(pkg.config_source, "preset")
        self.assertEqual(pkg.setting("layer_height"), "0.12")
        self.assertEqual(pkg.setting("machine_pause_gcode"), "PAUSE")
        self.assertIsNone(pkg.setting("raft_layers"))

    def test_list_values_take_the_first(self):
        settings = dict(fixtures.SETTINGS, raft_layers=["2", "0"])
        self.assertEqual(self.read(fixtures.build, settings=settings).setting("raft_layers"), "2")

    def test_existing_user_pause(self):
        pkg = self.read(fixtures.user_pause, z=19.2)
        (layer,) = pkg.layers
        self.assertEqual((layer.plate, layer.top_z, layer.type, layer.extra, layer.embedder), (1, 19.2, "2", "", False))

    def test_variable_layers_and_cut(self):
        ranges = ('<?xml version="1.0" encoding="utf-8"?>\n<objects>\n <object id="1">\n  <range min_z="0" max_z="5">\n'
                  '   <option opt_key="layer_height">0.1</option>\n  </range>\n </object>\n</objects>\n')
        pkg = self.read(fixtures.cube, extra={"Metadata/layer_config_ranges.xml": ranges})
        self.assertTrue(pkg.variable_layers("2"))
        self.assertFalse(self.read(fixtures.cube, name="b.3mf").variable_layers("2"))
        profile = self.read(fixtures.cube, name="c.3mf", extra={"Metadata/layer_heights_profile.txt": "object_id=1|0;0.2;10;0.1\n"})
        self.assertTrue(profile.variable_layers("2"))
        cut = ('<?xml version="1.0" encoding="utf-8"?>\n<objects>\n <object id="1">\n  <cut_id id="5" check_sum="1" connectors_cnt="2"/>\n'
               ' </object>\n</objects>\n')
        self.assertTrue(self.read(fixtures.cube, name="d.3mf", extra={"Metadata/cut_information.xml": cut}).has_cut_connectors("2"))
        self.assertFalse(pkg.has_cut_connectors("2"))

    def test_errors(self):
        path = self.make(fixtures.cube)
        with zipfile.ZipFile(path) as z:
            model = z.read("3D/3dmodel.model").decode()
        bad = os.path.join(self.tmp, "inch.3mf")
        fixtures.build(bad, extra={"3D/3dmodel.model": model.replace('unit="millimeter"', 'unit="inch"')})
        for target, code in ((bad, "bad_unit"), (os.path.join(self.tmp, "none.3mf"), "not_found")):
            with self.assertRaises(threemf.ThreeMFError) as cm:
                threemf.read(target)
            self.assertEqual(cm.exception.code, code)
        broken = os.path.join(self.tmp, "broken.3mf")
        with open(broken, "wb") as f:
            f.write(b"not a zip")
        with self.assertRaises(threemf.ThreeMFError) as cm:
            threemf.read(broken)
        self.assertEqual(cm.exception.code, "bad_package")

    def test_no_model_settings(self):
        src = self.make(fixtures.cube)
        bare = os.path.join(self.tmp, "bare.3mf")
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(bare, "w") as zout:
            for info in zin.infolist():
                if info.filename != threemf.SETTINGS:
                    zout.writestr(info, zin.read(info))
        pkg = threemf.read(bare, FALLBACK)
        self.assertEqual(len(pkg.items), 1)
        self.assertEqual(pkg.listed, {})

    def test_malformed_values_are_a_bad_package(self):
        bad_z = '<?xml version="1.0"?>\n<custom_gcodes_per_layer><plate><plate_info id="1"/><layer top_z="abc" type="1"/></plate></custom_gcodes_per_layer>'
        bad_plate = '<?xml version="1.0"?>\n<custom_gcodes_per_layer><plate><plate_info/><layer top_z="1" type="1"/></plate></custom_gcodes_per_layer>'
        for n, xml in enumerate((bad_z, bad_plate)):
            path = fixtures.build(os.path.join(self.tmp, "bad%d.3mf" % n), gcode_xml=xml)
            with self.assertRaises(threemf.ThreeMFError) as cm:
                threemf.read(path)
            self.assertEqual(cm.exception.code, "bad_package")


def cavity(z0=15.8, z1=19.0, x=110.0, y=110.0):
    """A plate-frame pocket: a 6.4 mm cylinder from z0 to z1."""
    verts, tris = g.cylinder_mesh(6.4, z1 - z0)
    return verts, tris, g.translation(x, y, z0)


class Write(Base):
    def apply(self, src, out="out.3mf", plate=1, add=(), remove=(), pauses=()):
        pkg = threemf.read(src)
        path = os.path.join(self.tmp, out)
        threemf.write(pkg, path, plate, add, remove, pauses)
        return path

    def addition(self, pkg_path, item=0, name="Embedder 6x3 magnet (embedded)", **kw):
        pkg = threemf.read(pkg_path)
        verts, tris, t = cavity(**kw)
        return threemf.Addition(pkg.items[item].object_id, item, name, verts, tris, t)

    def test_add_pocket_and_pause(self):
        src = self.make(fixtures.cube)
        out = self.apply(src, add=[self.addition(src)], pauses=[(19.2, "Embedder: insert 1 x 6x3 magnet")])
        pkg = threemf.read(out)
        obj = pkg.objects["2"]
        self.assertEqual([p.subtype for p in obj.parts], ["normal_part", "negative_part"])
        new = obj.parts[-1]
        self.assertEqual(new.id, "3")   # global max id (2) + 1
        self.assertEqual(new.file, "3D/Objects/object_1.model")
        lo, hi = bbox(pkg.plate_mesh(pkg.items[0], new)[0])
        self.assertAlmostEqual(lo[2], 15.8, places=4)
        self.assertAlmostEqual(hi[2], 19.0, places=4)
        self.assertAlmostEqual((lo[0] + hi[0]) / 2, 110, places=4)
        self.assertEqual([(e.name, e.object_id) for e in pkg.embedder_parts()], [("Embedder 6x3 magnet (embedded)", "2")])
        (layer,) = pkg.layers
        self.assertEqual((layer.top_z, layer.type, layer.extra, layer.embedder), (19.2, "1", "Embedder: insert 1 x 6x3 magnet", True))
        with zipfile.ZipFile(out) as z:
            gcode = z.read("Metadata/custom_gcode_per_layer.xml").decode()
            settings = z.read("Metadata/model_settings.config").decode()
            model = z.read("3D/3dmodel.model").decode()
            sub = z.read("3D/Objects/object_1.model").decode()
        self.assertIn('<layer top_z="19.2" type="1" extruder="1" color="" extra="Embedder: insert 1 x 6x3 magnet" gcode=""/>', gcode)
        self.assertIn('<plate_info id="1"/>', gcode)
        self.assertIn('<mode value="MultiExtruder"/>', gcode)
        part = re.search(r'<part id="3" subtype="negative_part">.*?</part>', settings, re.S).group(0)
        self.assertIn('<metadata key="extruder" value="1"/>', part)
        self.assertRegex(part, r'<mesh_stat face_count="256" edges_fixed="0"')
        self.assertTrue(settings.index('<part id="3"') > settings.index('<part id="1"'), "appended last")
        comp = re.findall(r"<component [^>]*>", model)
        self.assertIn('objectid="3"', comp[-1])
        self.assertIn('p:path="/3D/Objects/object_1.model"', comp[-1])
        self.assertRegex(comp[-1], r'p:UUID="[0-9a-f-]{36}"')
        self.assertRegex(sub, r'<object id="3" p:UUID="[0-9a-f-]{36}" type="other">')
        matrix = re.search(r'key="matrix" value="([^"]+)"', part).group(1)
        transform = re.search(r'transform="([^"]+)"', comp[-1]).group(1)
        self.assertTrue(all(abs(a - b) < 1e-6 for a, b in zip(g.from_config(matrix), g.from_3mf(transform))))

    def test_no_model_settings_refuses_additions(self):
        src = self.make(fixtures.no_model_settings)
        with self.assertRaises(threemf.ThreeMFError) as cm:
            self.apply(src, add=[self.addition(src)])
        self.assertEqual(cm.exception.code, "no_model_settings")
        self.assertFalse(threemf.read(src).has_settings)
        self.assertTrue(threemf.read(self.make(fixtures.cube, name="ok.3mf")).has_settings)

    def test_untouched_entries_are_identical(self):
        src = self.make(fixtures.cube)
        out = self.apply(src, add=[self.addition(src)], pauses=[(19.2, "Embedder: x")])
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(out) as b:
            for name in ("[Content_Types].xml", "_rels/.rels", "3D/_rels/3dmodel.model.rels", "Metadata/plate_1.png",
                         "Metadata/slice_info.config", "Metadata/project_settings.config"):
                self.assertEqual(a.read(name), b.read(name), name)
                self.assertEqual(a.getinfo(name).date_time, b.getinfo(name).date_time, name)
            self.assertEqual([n for n in a.namelist()], [n for n in b.namelist() if n != "Metadata/custom_gcode_per_layer.xml"])
        self.assertEqual(sorted(os.listdir(self.tmp)), ["out.3mf", "src.3mf"], "no temp or extracted files left")

    def test_inline_object_gets_its_mesh_in_the_main_model(self):
        src = self.make(fixtures.inline)
        out = self.apply(src, add=[self.addition(src)])
        pkg = threemf.read(out)
        new = pkg.objects["2"].parts[-1]
        self.assertEqual(new.file, "3D/3dmodel.model")
        with zipfile.ZipFile(out) as z:
            model = z.read("3D/3dmodel.model").decode()
        self.assertNotIn("p:path", model)
        self.assertLess(model.index('<object id="3"'), model.index('<object id="2"'), "defined before its parent")
        self.assertEqual(len(pkg.plate_mesh(pkg.items[0], new)[1]), 256 * 3)

    def test_one_line_xml(self):
        src = self.make(fixtures.cube)
        flat = os.path.join(self.tmp, "flat.3mf")
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(flat, "w") as b:
            for info in a.infolist():
                data = a.read(info)
                if info.filename.endswith((".model", ".config")) and "project" not in info.filename:
                    data = data.replace(b"\n", b"")
                b.writestr(info, data)
        out = self.apply(flat, add=[self.addition(flat)], pauses=[(19.2, "Embedder: a")])
        with zipfile.ZipFile(out) as z:
            for name in ("3D/3dmodel.model", "3D/Objects/object_1.model", "Metadata/model_settings.config"):
                self.assertTrue(z.read(name).startswith(b"<?xml"), name)
        self.assertEqual(len(threemf.read(out).embedder_parts()), 1)

    def test_component_path_follows_the_file_of_the_first_part(self):
        src = self.make(fixtures.multipart_with_negative)
        with zipfile.ZipFile(src) as z:
            model = z.read("3D/3dmodel.model").decode()
        first, second = re.findall(r"<component [^>]*>", model)
        self.assertIn('objectid="1"', first)
        # the second (negative) component claims another file; the new part must follow part 1's file
        moved = model.replace(second, second.replace("/3D/Objects/object_1.model", "/3D/Objects/other.model"))
        other = '%s <resources>\n  <object id="2" type="model">\n%s  </object>\n </resources>\n <build/>\n</model>\n' % (
            fixtures.HEAD, fixtures.mesh_xml(fixtures.cylinder(3, 12)))
        alt = self.make(fixtures.multipart_with_negative, name="alt.3mf",
                        extra={"3D/3dmodel.model": moved, "3D/Objects/other.model": other})
        out = self.apply(alt, add=[self.addition(alt)])
        with zipfile.ZipFile(out) as z:
            last = re.findall(r"<component [^>]*>", z.read("3D/3dmodel.model").decode())[-1]
        self.assertIn('p:path="/3D/Objects/object_1.model"', last)

    def test_publish_falls_back_when_hard_links_fail(self):
        src = self.make(fixtures.cube)
        real = os.link

        def no_link(a, b):
            raise OSError(1, "links not supported")
        os.link = no_link
        self.addCleanup(setattr, os, "link", real)
        out = self.apply(src, pauses=[(19.2, "Embedder: a")])
        self.assertEqual(len(threemf.read(out).layers), 1)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["out.3mf", "src.3mf"])

    def test_nothing_to_pause_writes_no_gcode_file(self):
        src = self.make(fixtures.cube)
        out = self.apply(src, add=[self.addition(src)])
        with zipfile.ZipFile(out) as z:
            self.assertNotIn("Metadata/custom_gcode_per_layer.xml", z.namelist())

    def test_mode_follows_the_filament_count_when_created(self):
        single = self.make(fixtures.build, settings=dict(fixtures.SETTINGS, filament_colour=["#FFFFFF"]))
        with zipfile.ZipFile(self.apply(single, pauses=[(19.2, "Embedder: a")])) as z:
            self.assertIn('<mode value="SingleExtruder"/>', z.read("Metadata/custom_gcode_per_layer.xml").decode())

    def test_spaced_sub_model(self):
        src = self.make(fixtures.spaced_submodel)
        pkg = threemf.read(self.apply(src, add=[self.addition(src)]))
        self.assertEqual(pkg.objects["2"].parts[-1].file, "3D/Objects/OrcaSlicer Badge Logo_47.model")

    def test_mirrored_item_writes_a_right_handed_matrix(self):
        src = self.make(fixtures.rotated_mirrored)
        out = self.apply(src, add=[self.addition(src, x=110, y=70)])
        pkg = threemf.read(out)
        new = pkg.objects["2"].parts[-1]
        self.assertGreater(g.det(new.matrix), 0)
        lo, hi = bbox(pkg.plate_mesh(pkg.items[0], new)[0])
        self.assertAlmostEqual((lo[0] + hi[0]) / 2, 110, places=4)
        self.assertAlmostEqual((lo[1] + hi[1]) / 2, 70, places=4)
        self.assertAlmostEqual(lo[2], 15.8, places=4)

    def test_user_pause_is_kept_and_embedder_pauses_are_replaced(self):
        src = self.make(fixtures.user_pause, z=5.0)
        first = self.apply(src, out="1.3mf", add=[self.addition(src)], pauses=[(19.2, "Embedder: a"), (3.0, "Embedder: b")])
        pkg = threemf.read(first)
        self.assertEqual([(l.top_z, l.embedder) for l in pkg.layers], [(3.0, True), (5.0, False), (19.2, True)])
        second = self.apply(first, out="2.3mf", pauses=[(7.0, "Embedder: c")])
        layers = threemf.read(second).layers
        self.assertEqual([(l.top_z, l.extra) for l in layers], [(5.0, ""), (7.0, "Embedder: c")])
        with zipfile.ZipFile(second) as z:
            self.assertIn('<mode value="SingleExtruder"/>', z.read("Metadata/custom_gcode_per_layer.xml").decode())

    def test_pause_on_plate_two_leaves_plate_one(self):
        src = self.make(fixtures.user_pause, z=5.0, items=[(0, "1 0 0 0 1 0 0 0 1 100 100 0"), (0, "1 0 0 0 1 0 0 0 1 407.2 100 0")],
                        plates=2, plate_items=[[0], [1]])
        out = self.apply(src, plate=2, pauses=[(9.0, "Embedder: p2")])
        layers = threemf.read(out).layers
        self.assertEqual([(l.plate, l.top_z) for l in layers], [(1, 5.0), (2, 9.0)])

    def test_layer_without_height_is_kept_on_write(self):
        xml = fixtures.user_pause_xml(5.0).replace("<mode", '<layer type="2" extruder="1" color="" extra="x" gcode=""/>\n<mode')
        src = self.make(fixtures.build, gcode_xml=xml)
        with zipfile.ZipFile(self.apply(src, pauses=[(19.2, "Embedder: a")])) as z:
            self.assertIn('<layer type="2" extruder="1" color="" extra="x" gcode=""/>', z.read("Metadata/custom_gcode_per_layer.xml").decode())

    def test_extra_is_escaped(self):
        src = self.make(fixtures.cube)
        out = self.apply(src, pauses=[(19.2, 'Embedder: <"a" & b>')])
        self.assertEqual(threemf.read(out).layers[0].extra, 'Embedder: <"a" & b>')

    def test_remove_embedder_part(self):
        src = self.make(fixtures.cube)
        first = self.apply(src, out="1.3mf", add=[self.addition(src)], pauses=[(19.2, "Embedder: a")])
        second = self.apply(first, out="2.3mf", remove=["3"])
        pkg = threemf.read(second)
        self.assertEqual([p.id for p in pkg.objects["2"].parts], ["1"])
        self.assertEqual(pkg.layers, ())
        with zipfile.ZipFile(second) as z:
            self.assertNotIn("<plate>", z.read("Metadata/custom_gcode_per_layer.xml").decode(), "no empty plate block")
        with zipfile.ZipFile(second) as a, zipfile.ZipFile(src) as b:
            for name in ("3D/3dmodel.model", "3D/Objects/object_1.model", "Metadata/model_settings.config"):
                self.assertNotIn('id="3"', a.read(name).decode(), name)
                self.assertNotIn('objectid="3"', a.read(name).decode(), name)
            self.assertEqual(len(a.read("3D/Objects/object_1.model")), len(b.read("3D/Objects/object_1.model")))

    def test_remove_refuses_other_parts(self):
        src = self.make(fixtures.multipart_with_negative)
        with self.assertRaises(threemf.ThreeMFError) as cm:
            self.apply(src, remove=["2"])
        self.assertEqual(cm.exception.code, "not_embedder_part")

    def test_cut_object_refused(self):
        cut = '<?xml version="1.0" encoding="utf-8"?>\n<objects>\n <object id="1">\n  <cut_id id="5" check_sum="1" connectors_cnt="1"/>\n </object>\n</objects>\n'
        src = self.make(fixtures.cube, extra={"Metadata/cut_information.xml": cut})
        with self.assertRaises(threemf.ThreeMFError) as cm:
            self.apply(src, add=[self.addition(src)])
        self.assertEqual(cm.exception.code, "cut_object")

    def test_ids_stay_unique_over_several_additions(self):
        src = self.make(fixtures.two_instances)
        out = self.apply(src, add=[self.addition(src, item=0, x=60), self.addition(src, item=1, x=160)])
        with zipfile.ZipFile(out) as z:
            ids = re.findall(r'<object id="(\d+)"', z.read("3D/3dmodel.model").decode() + z.read("3D/Objects/object_1.model").decode())
        self.assertEqual(sorted(ids, key=int), ["1", "2", "3", "4"])

    def test_apply_twice_gives_the_same_project(self):
        src = self.make(fixtures.cube)

        def run(name):
            out = self.apply(src, out=name, add=[self.addition(src)], pauses=[(19.2, "Embedder: a")])
            with zipfile.ZipFile(out) as z:
                return {n: re.sub(r'UUID="[^"]+"', "", z.read(n).decode("utf-8", "replace")) for n in z.namelist()}

        self.assertEqual(run("a.3mf"), run("b.3mf"))

    def test_existing_output_is_not_overwritten(self):
        src = self.make(fixtures.cube)
        out = self.apply(src)
        with self.assertRaises(threemf.ThreeMFError) as cm:
            threemf.write(threemf.read(src), out, 1, (), (), ())
        self.assertEqual(cm.exception.code, "exists")


if __name__ == "__main__":
    unittest.main()
