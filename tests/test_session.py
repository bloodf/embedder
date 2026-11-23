import base64
import os
import shutil
import sys
import tempfile
import time
import unittest
from array import array
from dataclasses import replace as replace_job
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder"), os.path.join(ROOT, "tests")]
import fixtures  # noqa: E402
import geometry  # noqa: E402
import pocket  # noqa: E402
import session  # noqa: E402
import settings  # noqa: E402
import threemf  # noqa: E402

TOP_TRI = 2   # fixtures.box: triangles 2 and 3 are the top face (+Z)
SIDE_TRI = 10  # x = max face (+X)


class Base(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.storage, ignore_errors=True)
        self.store = settings.Store()
        self.s = session.Session(self.storage, self.store.effective)

    def load(self, builder=fixtures.cube, live=None, plate=1, project="/projects/My Part.3mf", **kw):
        job_id, source = self.s.new_job()
        builder(source, **kw)
        return self.s.load(job_id, project, plate, live or {})

    def plan(self, job, **kw):
        args = {"job": job, "object": 0, "part": 0, "tri": TOP_TRI, "point": [110, 110, 20], "preset": "magnet-disc-6x3",
                "mode": "embedded", "spin": 0}
        args.update(kw)
        return self.s.plan(args)

    def error(self, fn, *a, **kw):
        with self.assertRaises(session.SessionError) as cm:
            fn(*a, **kw)
        return cm.exception.code


class Load(Base):
    def test_load_lists_objects_parts_and_settings(self):
        r = self.load()
        self.assertEqual((r["name"], r["plate"], r["plates"], r["config_source"]), ("My Part", 1, 1, "project"))
        self.assertEqual(r["settings"], {"layer_height": 0.2, "first_layer_height": 0.2, "pause_gcode": True,
                                         "print_sequence": "by layer", "raft_layers": 0})
        self.assertEqual(r["blocks"], [])
        (obj,) = r["objects"]
        self.assertEqual((obj["object"], obj["id"], obj["name"], obj["instance"], obj["embedded_block"]), (0, "2", "cube", 0, None))
        (part,) = obj["parts"]
        self.assertEqual((part["part"], part["subtype"], part["vertices"], part["triangles"], part["embedder"]),
                         (0, "normal_part", 8, 12, False))
        self.assertEqual((part["pos_bytes"], part["idx_bytes"], part["pos_chunks"], part["idx_chunks"]), (96, 144, 1, 1))
        self.assertEqual(r["chunk_bytes"], session.CHUNK_BYTES)
        self.assertEqual(r["existing"], [])
        self.assertEqual(r["pauses"], [])
        self.assertTrue(os.path.isfile(os.path.join(self.storage, "jobs", r["job"], "source.3mf")))

    def test_mesh_chunks_round_trip(self):
        r = self.load()
        got = {}
        for kind, code in (("pos", "f"), ("idx", "I")):
            c = self.s.mesh_chunk({"job": r["job"], "object": 0, "part": 0, "kind": kind, "i": 0})
            self.assertEqual((c["i"], c["chunks"]), (0, 1))
            got[kind] = array(code, base64.b64decode(c["data"]))
        self.assertEqual(len(got["pos"]), 24)
        self.assertEqual(max(got["pos"][0::3]), 120)
        self.assertEqual(len(got["idx"]), 36)
        for bad in ({"kind": "nope"}, {"i": 1}, {"part": 5}, {"object": -1}, {"i": "0"}):
            args = {"job": r["job"], "object": 0, "part": 0, "kind": "pos", "i": 0, **bad}
            self.assertEqual(self.error(self.s.mesh_chunk, args), "bad_request", bad)

    def test_chunks_copy_only_their_slice(self):
        r = self.load()
        (part,) = r["objects"][0]["parts"]
        with mock.patch.object(session, "CHUNK_BYTES", 40):
            got = [self.s.mesh_chunk({"job": r["job"], "object": 0, "part": 0, "kind": "idx", "i": i}) for i in range(4)]
        self.assertEqual([c["chunks"] for c in got], [4] * 4)
        self.assertEqual(b"".join(base64.b64decode(c["data"]) for c in got), session._bytes(self.s.job.entries[0].meshes[0][1]))
        self.assertEqual(part["idx_bytes"], 144)

    def test_big_meshes_are_chunked(self):
        old = session.CHUNK_BYTES
        session.CHUNK_BYTES = 64
        self.addCleanup(setattr, session, "CHUNK_BYTES", old)
        r = self.load()
        part = r["objects"][0]["parts"][0]
        self.assertEqual(part["pos_chunks"], 2)
        data = b"".join(base64.b64decode(self.s.mesh_chunk({"job": r["job"], "object": 0, "part": 0, "kind": "pos", "i": i})["data"])
                        for i in range(2))
        self.assertEqual(len(data), 96)

    def test_stale_job(self):
        first = self.load()
        self.load()
        self.assertEqual(self.error(self.plan, first["job"]), "stale_job")
        old = os.path.join(self.storage, "jobs", first["job"])
        for _ in range(200):   # removed on a worker thread
            if not os.path.exists(old):
                break
            time.sleep(0.01)
        self.assertFalse(os.path.exists(old), "older job folder removed")

    def test_loading_a_replaced_job_is_stale(self):
        first, source = self.s.new_job()
        fixtures.cube(source)
        self.s.new_job()
        self.assertEqual(self.error(self.s.load, first, "", 1, {}), "stale_job")

    def test_a_failed_load_keeps_the_loaded_project(self):
        """The export or the parse of a new load fails: the project on screen keeps working."""
        first = self.load()
        self.s.new_job()                                      # export failed: nothing written
        job_id, source = self.s.new_job()
        with open(source, "wb") as f:
            f.write(b"junk")
        self.assertEqual(self.error(self.s.load, job_id, "", 1, {}), "bad_package")
        self.assertIsNone(self.plan(first["job"])["blocked"])
        self.assertTrue(os.path.isdir(os.path.join(self.storage, "jobs", first["job"])))

    def test_empty_project_settings_use_live_values(self):
        live = {"layer_height": "0.12", "initial_layer_print_height": "0.2", "machine_pause_gcode": "",
                "print_sequence": "by object", "raft_layers": "2"}
        r = self.load(fixtures.empty_settings, live=live)
        self.assertEqual(r["config_source"], "preset")
        self.assertEqual(r["settings"]["layer_height"], 0.12)
        self.assertEqual(r["blocks"], ["by_object", "no_pause_gcode", "raft"])
        self.assertEqual(r["objects"][0]["embedded_block"], "by_object")

    def test_only_the_current_plate(self):
        r = self.load(fixtures.two_plates, plate=2)
        self.assertEqual([o["item"] for o in r["objects"]], [1])
        self.assertEqual(r["plates"], 2)

    def test_instances_on_another_plate_block_embedded(self):
        r = self.load(fixtures.two_plates, plate=1)
        self.assertEqual(r["objects"][0]["embedded_block"], "instances_other_plate")
        self.assertEqual(self.plan(r["job"])["blocked"]["code"], "instances_other_plate")
        self.assertIsNone(self.plan(r["job"], mode="open")["blocked"])

    def test_another_plate_without_a_printable_area_is_refused(self):
        """Every plate at the origin would put plate 2 objects (and their pockets) in the wrong place."""
        no_bed = {k: v for k, v in fixtures.SETTINGS.items() if k != "printable_area"}
        self.assertEqual(self.error(self.load, fixtures.two_plates, plate=2, settings=no_bed), "no_bed")
        self.assertEqual([o["item"] for o in self.load(fixtures.two_plates, plate=1, settings=no_bed)["objects"]], [0])

    def test_kept_cavity_tops_read_back_from_float32_stay_on_their_layer(self):
        """8.6 is 8.6000004 as float32: snapped up it was the next layer, and the pause came one layer late."""
        for first, height in ((0.2, 0.2), (0.3, 0.2), (0.2, 0.12), (0.24, 0.08)):
            grid = pocket.Grid(first, height)
            for k in range(2000):
                z = array("f", [grid.top(k)])[0]
                self.assertEqual(grid.snap_up(z - session.READ_SLACK), grid.top(k), (first, height, k))

    def test_two_instances_are_listed(self):
        r = self.load(fixtures.two_instances)
        self.assertEqual([(o["item"], o["instance"]) for o in r["objects"]], [(0, 0), (1, 1)])

    def test_bad_project(self):
        job_id, source = self.s.new_job()
        with open(source, "wb") as f:
            f.write(b"junk")
        self.assertEqual(self.error(self.s.load, job_id, "", 1, {}), "bad_package")

    def test_long_names_fit_a_file_name(self):
        """A file name is at most 255 bytes on Linux: the stem leaves room for the suffix and the temporary name."""
        for name in ("日" * 200, "a" * 300, "🧲" * 90):
            stem = session._stem("/p/%s.3mf" % name)
            self.assertLessEqual(len(stem.encode("utf-8")), 150, name[:3])
            self.assertTrue(stem and name.startswith(stem))


class Plan(Base):
    def test_embedded_on_top(self):
        r = self.load()
        p = self.plan(r["job"])
        self.assertEqual((p["mode"], p["face"], p["shape"], p["label"], p["kind"]), ("embedded", "top", "hexagon", "6x3 magnet", "magnet"))
        self.assertEqual(p["size"], [6.4, 6.4, 3.2])
        self.assertEqual(p["outer"], [7.390083, 6.4])      # corner to corner, flat to flat
        self.assertAlmostEqual(p["floor"], 15.8)
        self.assertAlmostEqual(p["top"], 19.0)
        self.assertAlmostEqual(p["pause_z"], 19.2)
        self.assertEqual(len(p["transform"]), 16)
        self.assertEqual(len(p["preview"]["indices"]), 24 * 3)
        self.assertEqual(p["warnings"], [])
        self.assertIsNone(p["blocked"])

    def test_normal_comes_from_the_triangle_not_the_page(self):
        r = self.load()
        p = self.plan(r["job"], tri=SIDE_TRI, point=[120, 110, 10], normal=[0, 0, 1])
        self.assertEqual(p["face"], "side")

    def test_a_block_and_a_slot_report_their_vents(self):
        r = self.load()
        box = self.plan(r["job"], preset="magnet-block-10x5x2")
        self.assertEqual((box["shape"], box["size"][:2], box["outer"]), ("rectangle", [10.4, 5.4], [11.4, 6.4]))
        slot = self.plan(r["job"], tri=SIDE_TRI, point=[120, 110, 10])
        self.assertEqual((slot["shape"], slot["size"][:2], slot["outer"]), ("slot", [6.4, 3.4], [7.4, 3.9]))
        self.assertEqual((slot["cover"], slot["warnings"]), (1.0, []))

    def test_the_picked_pocket_shape_is_planned_and_an_unknown_one_blocked(self):
        r = self.load()
        circle = self.plan(r["job"], pocket_shape="circle")
        self.assertEqual((circle["shape"], circle["size"]), ("circle", [6.4, 6.4, 3.2]))
        self.assertEqual(len(circle["preview"]["indices"]), 4 * 64 * 3)
        square = self.plan(r["job"], preset="magnet-block-10x5x2", pocket_shape="square", mode="open")
        self.assertEqual((square["shape"], square["size"][:2]), ("square", [10.4, 10.4]))
        self.assertEqual(self.plan(r["job"], pocket_shape="oval")["blocked"]["code"], "bad_shape")
        with self.assertRaises(session.SessionError) as cm:
            self.s.apply({"job": r["job"], "pockets": [{"object": 0, "part": 0, "tri": TOP_TRI, "point": [110, 110, 20],
                                                        "preset": "magnet-disc-6x3", "mode": "open", "pocket_shape": "oval"}]})
        self.assertEqual((cm.exception.code, cm.exception.detail), ("pocket_blocked", "pocket 1: bad_shape"))

    def test_open_and_custom(self):
        r = self.load()
        p = self.plan(r["job"], mode="open", preset=None, custom={"kind": "nfc", "shape": "disc", "d": 25, "t": 1})
        self.assertEqual((p["mode"], p["pause_z"], p["label"]), ("open", None, "25x1 NFC"))

    def test_cover_comes_from_settings_by_kind(self):
        r = self.load()
        nfc = self.plan(r["job"], preset="nfc-sticker-25")
        self.assertGreaterEqual(nfc["cover"], 0.6 - 1e-9)
        self.store.update({"cover_magnet": 2.0})
        self.assertAlmostEqual(self.plan(r["job"])["cover"], 2.0)
        self.assertAlmostEqual(self.plan(r["job"], cover=0.4)["cover"], 0.4)

    def test_blocked_is_a_result(self):
        r = self.load(fixtures.build, settings=dict(fixtures.SETTINGS, print_sequence="by object"))
        p = self.plan(r["job"])
        self.assertEqual(p["blocked"]["code"], "by_object")
        self.assertIsNone(p["preview"])
        self.assertIsNone(self.plan(r["job"], mode="open")["blocked"])

    def test_bad_requests(self):
        r = self.load()
        cases = [({"tri": 99}, "bad_request"), ({"point": [110, 110, 25]}, "bad_point"), ({"point": "x"}, "bad_request"),
                 ({"preset": "nope"}, "unknown_preset"), ({"object": 3}, "bad_request"), ({"spin": "a"}, "bad_request"),
                 ({"others": 5}, "bad_request")]
        for kw, code in cases:
            self.assertEqual(self.error(self.plan, r["job"], **kw), code, kw)

    def test_projects_that_cannot_take_a_pocket_say_why_before_apply(self):
        r = self.load(fixtures.no_model_settings)
        self.assertEqual(self.error(self.plan, r["job"]), "no_model_settings")
        r = self.load(fixtures.plain_mesh)
        self.assertEqual(self.error(self.plan, r["job"], point=[110, 110, 20]), "unsupported_object")

    def test_centre_on_the_face(self):
        r = self.load()
        clicked = self.plan(r["job"], point=[105, 104, 20])
        self.assertEqual(clicked["transform"][3::4][:2], [105, 104])
        centred = self.plan(r["job"], point=[105, 104, 20], center=True)
        self.assertEqual(centred["transform"][3::4][:2], [110, 110])
        self.assertEqual((clicked["point"], centred["point"]), ([105, 104, 20], [110, 110, 20]), "where the pocket was planned")
        self.assertEqual(self.plan(r["job"], point=[105, 104, 20], center=True, mode="open")["transform"][3::4][:2], [110, 110])
        side = self.plan(r["job"], tri=SIDE_TRI, point=[120, 103, 5], center=True, mode="open")
        self.assertEqual([round(v, 6) for v in side["transform"][3::4][1:3]], [110, 10])
        self.assertEqual(self.error(self.plan, r["job"], center="yes"), "bad_request")

    def test_a_pause_on_someone_elses_gcode_warns_while_planning(self):
        r = self.load(fixtures.user_pause, z=19.2)
        self.assertIn("existing_gcode_at_layer", self.plan(r["job"])["warnings"])
        self.assertNotIn("existing_gcode_at_layer", self.plan(r["job"], mode="open")["warnings"])

    def test_negative_part_cannot_be_picked(self):
        r = self.load(fixtures.multipart_with_negative)
        self.assertEqual(self.error(self.plan, r["job"], part=1), "bad_part")

    def test_cut_object(self):
        cut = '<?xml version="1.0"?>\n<objects>\n <object id="1">\n  <cut_id id="5" check_sum="1" connectors_cnt="1"/>\n </object>\n</objects>\n'
        r = self.load(extra={"Metadata/cut_information.xml": cut})
        self.assertEqual(self.error(self.plan, r["job"]), "cut_object")
        with self.assertRaises(session.SessionError) as cm:
            self.plan(r["job"])
        self.assertEqual(cm.exception.detail, r["objects"][0]["name"])   # the page names the object; the sentence is its own

    def test_breaking_through_warns(self):
        r = self.load()
        self.assertEqual(self.plan(r["job"])["warnings"], [])
        self.assertIn("breaks_surface", self.plan(r["job"], point=[101, 110, 20])["warnings"])

    def test_copies_are_reported(self):
        r = self.load(fixtures.two_instances)
        self.assertEqual(self.plan(r["job"], point=[70, 110, 20])["copies"], 2)

    def test_others_bring_proximity_warnings(self):
        r = self.load(fixtures.build, objects=[fixtures.cube_object(size=60)])
        near = {"object": 0, "part": 0, "tri": TOP_TRI, "point": [120, 110, 60], "preset": "nfc-sticker-25", "mode": "embedded"}
        p = self.plan(r["job"], point=[110, 110, 60], others=[near])
        self.assertIn("nfc_near_magnet", p["warnings"])

    def test_polarity_note_in_plan_and_apply_pauses(self):
        r = self.load()
        p_n = self.plan(r["job"], polarity="N")
        self.assertEqual(p_n["polarity"], "N")
        self.assertEqual(self.error(self.plan, r["job"], polarity="E"), "bad_request")
        self.assertEqual(self.error(self.plan, r["job"], preset="nfc-sticker-25", polarity="N"), "bad_request")
        applied = self.s.apply({
            "job": r["job"],
            "pockets": [
                {"object": 0, "part": 0, "tri": TOP_TRI, "point": [105, 110, 20], "preset": "magnet-disc-6x3", "mode": "embedded", "polarity": "N"},
                {"object": 0, "part": 0, "tri": TOP_TRI, "point": [115, 110, 20], "preset": "magnet-disc-6x3", "mode": "embedded", "polarity": "S"},
            ],
            "remove": [],
        })
        self.assertEqual(applied["pauses"], [
            {"top_z": 19.2, "extra": "Embedder: insert 1 x 6x3 magnet (N up), 1 x 6x3 magnet (S up)"}
        ])

    def test_auto_fridge_places_symmetric_bottom_pockets(self):
        r = self.load(fixtures.build, objects=[fixtures.cube_object(size=60)])
        one = self.s.auto_fridge({"job": r["job"], "object": 0, "count": 1, "preset": "magnet-disc-6x2", "mode": "embedded"})
        self.assertEqual(one["count"], 1)
        self.assertEqual(one["items"][0]["plan"]["face"], "bottom")
        self.assertEqual(one["items"][0]["plan"]["point"], [130.0, 130.0, 0.0])

        two = self.s.auto_fridge({"job": r["job"], "object": 0, "count": 2, "preset": "magnet-disc-6x2", "mode": "embedded"})
        self.assertEqual(two["count"], 2)
        xs2 = [it["plan"]["point"][0] for it in two["items"]]
        self.assertAlmostEqual(sum(xs2) / 2.0, 130.0)
        self.assertGreater(xs2[1] - xs2[0], 30.0)

        three_x = self.s.auto_fridge({"job": r["job"], "object": 0, "count": 3})
        self.assertEqual(three_x["count"], 3)

        four = self.s.auto_fridge({"job": r["job"], "object": 0, "count": "auto", "preset": "magnet-disc-6x2", "mode": "embedded"})
        self.assertEqual(four["count"], 4)
        pts4 = [it["plan"]["point"] for it in four["items"]]
        self.assertAlmostEqual(sum(p[0] for p in pts4) / 4.0, 130.0)
        self.assertAlmostEqual(sum(p[1] for p in pts4) / 4.0, 130.0)
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r["job"], "object": 0, "count": 99}), "bad_request")
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r["job"], "object": 0, "count": True}), "bad_request")
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r["job"], "object": 0, "preset": "nope"}), "unknown_preset")

    def test_auto_fridge_sizing_orientations_and_fallbacks(self):
        # Small 20x20 cube -> auto picks 1 magnet
        r_small = self.load(fixtures.build, objects=[fixtures.cube_object(size=20)])
        auto_1 = self.s.auto_fridge({"job": r_small["job"], "object": 0, "count": "auto"})
        self.assertEqual(auto_1["count"], 1)

        # Y-dominant 20x50x20 bar -> auto picks 2 magnets along Y; count=3 also uses Y-dominant layout
        y_bar = {"name": "ybar", "parts": [fixtures.part("ybar", fixtures.box(20, 50, 20))]}
        r_y = self.load(fixtures.build, objects=[y_bar])
        auto_2y = self.s.auto_fridge({"job": r_y["job"], "object": 0, "count": "auto",
                                      "custom": {"kind": "magnet", "shape": "block", "l": 8, "w": 4, "t": 2},
                                      "spin": 15, "pocket_shape": "rectangle"})
        self.assertEqual(auto_2y["count"], 2)
        ys = [it["plan"]["point"][1] for it in auto_2y["items"]]
        self.assertGreater(ys[1] - ys[0], 20.0)
        self.assertEqual(auto_2y["items"][0]["args"]["spin"], 15)
        self.assertEqual(auto_2y["items"][0]["args"]["pocket_shape"], "rectangle")
        three_y = self.s.auto_fridge({"job": r_y["job"], "object": 0, "count": 3})
        self.assertEqual(three_y["count"], 3)

        # Thin 40x40x2.0 plaque -> embedded 6x2 magnet (2.6mm total) would break surface, so it falls back to open mode
        thin = {"name": "thin", "parts": [fixtures.part("thin", fixtures.box(40, 40, 2.0))]}
        r_thin = self.load(fixtures.build, objects=[thin])
        thin_res = self.s.auto_fridge({"job": r_thin["job"], "object": 0, "count": 2, "preset": "magnet-disc-6x2"})
        self.assertEqual(thin_res["count"], 2)
        self.assertTrue(all(it["args"]["mode"] == "open" for it in thin_res["items"]))

        # Object-blocked project (print_sequence="by object") -> automatically switches to open mode
        r_blk = self.load(fixtures.build, settings=dict(fixtures.SETTINGS, print_sequence="by object"))
        blk_res = self.s.auto_fridge({"job": r_blk["job"], "object": 0, "count": 1})
        self.assertEqual(blk_res["count"], 1)
        self.assertEqual(blk_res["items"][0]["args"]["mode"], "open")

    def test_auto_fridge_non_convex_beveled_and_error_guards(self):
        # L-shaped bottom where a corner target falls outside the bottom triangles and snaps to the nearest triangle edge
        l_verts = [(0, 0, 0), (50, 0, 0), (50, 20, 0), (20, 20, 0), (20, 50, 0), (0, 50, 0),
                   (0, 0, 15), (50, 0, 15), (50, 20, 15), (20, 20, 15), (20, 50, 15), (0, 50, 15)]
        l_tris = [
            (0, 2, 1), (0, 3, 2), (0, 4, 3), (0, 5, 4),   # bottom face (L-shape, missing top-right [20..50]x[20..50])
            (6, 7, 8), (6, 8, 9), (6, 9, 10), (6, 10, 11),
            (0, 1, 7), (0, 7, 6), (0, 6, 11), (0, 11, 5),
        ]
        r_l = self.load(fixtures.build, objects=[{"name": "L", "parts": [fixtures.part("L", (l_verts, l_tris))]}])
        res_l = self.s.auto_fridge({"job": r_l["job"], "object": 0, "count": 4})
        self.assertEqual(res_l["count"], 4)

        # Beveled bottom where the lowest vertex is at z=0 but the flat-ish bottom facet sits at z=0.5..0.8 (exercising fallback)
        bev_verts = [(0, 0, 0), (40, 0, 0.5), (40, 40, 0.5), (0, 40, 0.5),
                     (0, 0, 20), (40, 0, 20), (40, 40, 20), (0, 40, 20)]
        bev_tris = [(1, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5)]
        r_bev = self.load(fixtures.build, objects=[{"name": "bev", "parts": [fixtures.part("bev", (bev_verts, bev_tris))]}])
        res_bev = self.s.auto_fridge({"job": r_bev["job"], "object": 0, "count": 1})
        self.assertEqual(res_bev["count"], 1)

        # Hollow rectangular frame: centre (125, 125) is an open cutout, so count=1 snaps onto a solid arm without breaks_surface
        # Outer: 0..50 x 0..50, inner cutout: 15..35 x 15..35, height: 12
        ov = [(0, 0, 0), (50, 0, 0), (50, 50, 0), (0, 50, 0), (15, 15, 0), (35, 15, 0), (35, 35, 0), (15, 35, 0)]
        fv = ov + [(x, y, 12) for x, y, _ in ov]
        ft = [
            # bottom ring (4 quads -> 8 tris, normal -Z)
            (0, 4, 1), (1, 4, 5), (1, 5, 2), (2, 5, 6), (2, 6, 3), (3, 6, 7), (3, 7, 0), (0, 7, 4),
            # top ring (normal +Z)
            (8, 9, 12), (9, 13, 12), (9, 10, 13), (10, 14, 13), (10, 11, 14), (11, 15, 14), (11, 8, 15), (8, 12, 15),
            # outer walls
            (0, 1, 8), (1, 9, 8), (1, 2, 9), (2, 10, 9), (2, 3, 10), (3, 11, 10), (3, 0, 11), (0, 8, 11),
            # inner cutout walls
            (4, 12, 5), (5, 12, 13), (5, 13, 6), (6, 13, 14), (6, 14, 7), (7, 14, 15), (7, 15, 4), (4, 15, 12),
        ]
        r_frame = self.load(fixtures.build, objects=[{"name": "frame", "parts": [fixtures.part("frame", (fv, ft))]}])
        res_frame = self.s.auto_fridge({"job": r_frame["job"], "object": 0, "count": 1, "preset": "magnet-disc-6x2"})
        self.assertEqual(res_frame["count"], 1)
        self.assertEqual(res_frame["items"][0]["args"]["mode"], "embedded")
        self.assertNotIn("breaks_surface", res_frame["items"][0]["plan"]["warnings"])

        # Object with only upward-facing triangles (no bottom face) -> bad_part
        up_verts = [(0, 0, 0), (20, 0, 0), (0, 20, 0)]
        up_tris = [(0, 1, 2)]
        r_up = self.load(fixtures.build, objects=[{"name": "up", "parts": [fixtures.part("up", (up_verts, up_tris))]}])
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r_up["job"], "object": 0}), "bad_part")

        # Object with only negative_part -> bad_part
        neg_only = {"name": "neg", "parts": [fixtures.part("neg", fixtures.box(20, 20, 20), "negative_part")]}
        r_neg = self.load(fixtures.build, objects=[neg_only])
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r_neg["job"], "object": 0}), "bad_part")

        # Project/object error guards
        cut = '<?xml version="1.0"?>\n<objects>\n <object id="1">\n  <cut_id id="5" check_sum="1" connectors_cnt="1"/>\n </object>\n</objects>\n'
        r_cut = self.load(extra={"Metadata/cut_information.xml": cut})
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r_cut["job"], "object": 0}), "cut_object")
        r_no_ms = self.load(fixtures.no_model_settings)
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r_no_ms["job"], "object": 0}), "no_model_settings")
        r_plain = self.load(fixtures.plain_mesh)
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r_plain["job"], "object": 0}), "unsupported_object")

    def test_auto_fridge_all_objects(self):
        r = self.load(fixtures.build,
                      objects=[fixtures.cube_object("a", size=20), fixtures.cube_object("b", size=60)],
                      items=[(0, "1 0 0 0 1 0 0 0 1 50 100 0"), (1, "1 0 0 0 1 0 0 0 1 150 100 0")])
        res = self.s.auto_fridge({"job": r["job"], "object": "all", "count": "auto"})
        self.assertEqual(res["count"], 5)   # 1 on small 20mm object + 4 on 60mm object
        self.assertEqual([it["args"]["object"] for it in res["items"]], [0, 1, 1, 1, 1])
        # If one object is cut/invalid and another is valid, "all" skips the invalid one and stages the valid one
        cut = '<?xml version="1.0"?>\n<objects>\n <object id="1">\n  <cut_id id="5" check_sum="1" connectors_cnt="1"/>\n </object>\n</objects>\n'
        r2 = self.load(fixtures.build,
                       objects=[fixtures.cube_object("cut_obj", size=20), fixtures.cube_object("ok_obj", size=20)],
                       items=[(0, "1 0 0 0 1 0 0 0 1 50 100 0"), (1, "1 0 0 0 1 0 0 0 1 150 100 0")],
                       extra={"Metadata/cut_information.xml": cut})
        res2 = self.s.auto_fridge({"job": r2["job"], "object": "all", "count": "auto"})
        self.assertEqual(res2["count"], 1)
        self.assertEqual(res2["items"][0]["args"]["object"], 1)

    def test_auto_fridge_physics_sizing_and_weak_hold_warning(self):
        # Moderate tall column (45x45x60 mm, 15% infill) -> scales up to 2x2 = 4 magnets
        mid = {"name": "mid", "parts": [fixtures.part("mid", fixtures.box(45, 45, 60))]}
        r_mid = self.load(fixtures.build, objects=[mid], settings=dict(fixtures.SETTINGS, sparse_infill_density="15%"))
        res_mid = self.s.auto_fridge({"job": r_mid["job"], "object": 0, "count": "auto", "preset": "magnet-disc-6x2"})
        self.assertEqual(res_mid["count"], 4)

        # Heavy tall column (45x45x120 mm, 25% infill) -> scales beyond 4 into a 3x3 = 9 grid
        tall = {"name": "tall", "parts": [fixtures.part("tall", fixtures.box(45, 45, 120))]}
        r_tall = self.load(fixtures.build, objects=[tall], settings=dict(fixtures.SETTINGS, sparse_infill_density="25%"))
        res_tall = self.s.auto_fridge({"job": r_tall["job"], "object": 0, "count": "auto", "preset": "magnet-disc-6x2"})
        self.assertEqual(res_tall["count"], 9)

        # On a ferrite/stainless setting with a heavy block where even the full grid cannot meet the 2.5x safety factor, warn!
        self.store.update({"magnet_grade": "ferrite", "fridge_surface": "stainless"})
        res_weak = self.s.auto_fridge({"job": r_tall["job"], "object": 0, "count": "auto", "preset": "magnet-disc-6x2"})
        self.assertIn("weak_magnet_hold", res_weak["items"][0]["plan"]["warnings"])

        # Large heavy plate (100x80x100) needing >4 magnets (and odd/prime -> n+1) scales up to a symmetric grid!
        self.store.update({"magnet_grade": "N35", "fridge_surface": "steel"})
        heavy = {"name": "heavy", "parts": [fixtures.part("heavy", fixtures.box(100, 80, 100))]}
        r_heavy = self.load(fixtures.build, objects=[heavy], settings=dict(fixtures.SETTINGS, sparse_infill_density="40%"))
        res_heavy = self.s.auto_fridge({"job": r_heavy["job"], "object": 0, "count": "auto", "preset": "magnet-disc-6x2"})
        self.assertGreater(res_heavy["count"], 4)

        # Filament density lookup: explicit filament_density and fallback by filament_type (ABS/ASA/PC/TPU/PLA)
        self.assertAlmostEqual(pocket.filament_density(["1.35"], ["PLA"]), 1.35)
        self.assertAlmostEqual(pocket.filament_density(None, ["ABS"]), 1.04)
        self.assertAlmostEqual(pocket.filament_density(None, ["ASA"]), 1.07)
        self.assertAlmostEqual(pocket.filament_density(None, ["PC"]), 1.20)
        self.assertAlmostEqual(pocket.filament_density(None, ["TPU"]), 1.21)
        self.assertAlmostEqual(pocket.filament_density(None, ["UNKNOWN"]), 1.24)

        # Excessive pull warning when strong N52 block magnets are used on a steel door
        self.store.update({"magnet_grade": "N52", "fridge_surface": "steel"})
        big_plate = {"name": "big", "parts": [fixtures.part("big", fixtures.box(80, 80, 15))]}
        r_big = self.load(fixtures.build, objects=[big_plate])
        res_excess = self.s.auto_fridge({"job": r_big["job"], "object": 0, "count": 4, "preset": "magnet-block-20x10x5"})
        self.assertIn("excessive_magnet_hold", res_excess["items"][0]["plan"]["warnings"])
        # Invalid density string falls back to PLA, and invalid non-dict pocket plan arg raises bad_request
        self.assertAlmostEqual(pocket.filament_density("not-a-number", "PLA"), 1.24)
        self.assertEqual(self.error(self.s._plan_at, self.s._current(r_big["job"]), "not-a-dict"), "bad_request")
        # All-objects mode when all objects are cut/unsupported raises the underlying SessionError, and empty entries -> bad_request
        cut = '<?xml version="1.0"?>\n<objects>\n <object id="1">\n  <cut_id id="5" check_sum="1" connectors_cnt="1"/>\n </object>\n</objects>\n'
        r_all_cut = self.load(extra={"Metadata/cut_information.xml": cut})
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r_all_cut["job"], "object": "all"}), "cut_object")
        from dataclasses import replace
        cur = self.s._current(r_all_cut["job"])
        self.s.job = replace(cur, entries=())
        self.assertEqual(self.error(self.s.auto_fridge, {"job": r_all_cut["job"], "object": "all"}), "bad_request")
        self.assertFalse(pocket._is_prime(1))
        # _bytes big-endian path, load progress callback, no_layer_height, and _delete OSError handling
        from unittest import mock
        import array as _arr
        with mock.patch("sys.byteorder", "big"):
            self.assertEqual(len(session._bytes(_arr.array("f", [1.0, 2.0]))), 8)
        ticks = []
        jid, src = self.s.new_job()
        fixtures.cube(src)
        self.s.load(jid, "/work/cube.3mf", 1, {}, progress=lambda d, t: ticks.append((d, t)))
        self.assertTrue(ticks)
        r_no_lh = self.load(fixtures.build, settings={k: v for k, v in fixtures.SETTINGS.items() if k != "layer_height"})
        self.assertEqual(self.plan(r_no_lh["job"])["blocked"]["code"], "no_layer_height")
        with mock.patch("os.remove", side_effect=OSError("locked")):
            self.assertEqual(self.s._delete([(os.path.join(self.storage, "x.3mf"), 0, 100)]), (0, 0, 1))
        # Two instances of one object share its pockets: "all" plans that object once, not once per instance
        r3 = self.load(fixtures.two_instances)
        one = self.s.auto_fridge({"job": r3["job"], "object": 0, "count": 2})
        both = self.s.auto_fridge({"job": r3["job"], "object": "all", "count": 2})
        self.assertEqual(both["count"], one["count"])
        self.assertEqual({it["args"]["object"] for it in both["items"]}, {0})


class Apply(Base):
    def apply(self, job, pockets=(), remove=()):
        return self.s.apply({"job": job, "pockets": list(pockets), "remove": list(remove)})

    def pocket(self, **kw):
        args = {"object": 0, "part": 0, "tri": TOP_TRI, "point": [110, 110, 20], "preset": "magnet-disc-6x3", "mode": "embedded"}
        args.update(kw)
        return args

    def test_apply_writes_a_named_copy_with_parts_and_pauses(self):
        r = self.load()
        out = self.apply(r["job"], [self.pocket(), self.pocket(point=[105, 105, 20]), self.pocket(mode="open", point=[115, 115, 20])])
        self.assertRegex(out["name"], r"^My Part-embedder-\d{8}-\d{6}-[0-9a-f]{6}\.3mf$")
        self.assertEqual(os.path.dirname(out["path"]), self.storage)
        self.assertEqual(out["pauses"], [{"top_z": 19.2, "extra": "Embedder: insert 2 x 6x3 magnet"}])
        pkg = threemf.read(out["path"])
        self.assertEqual([e.name for e in pkg.embedder_parts()],
                         ["Embedder 6x3 magnet (embedded)"] * 2 + ["Embedder 6x3 magnet (open)"])
        self.assertEqual(out["pockets"], 3)

    def test_pause_counts_every_instance(self):
        r = self.load(fixtures.two_instances)
        out = self.apply(r["job"], [self.pocket(point=[70, 110, 20])])
        self.assertEqual(out["pauses"], [{"top_z": 19.2, "extra": "Embedder: insert 2 x 6x3 magnet"}])

    def test_an_empty_embedded_pocket_is_skipped(self):
        """An Embedder pocket with no vertices left in the project has no top: it gets no pause, not a crash."""
        first = self.apply(self.load()["job"], [self.pocket()])
        job_id, source = self.s.new_job()
        shutil.copyfile(first["path"], source)
        self.s.load(job_id, first["path"], 1, {})
        e = self.s.job.entries[0]
        empty = tuple(m if p.subtype == "normal_part" else (array("f"), array("I")) for p, m in zip(e.obj.parts, e.meshes))
        self.s.job = replace_job(self.s.job, entries=(replace_job(e, meshes=empty),))
        self.assertEqual(self.apply(job_id)["pauses"], [])

    def test_an_applied_job_is_finished(self):
        r = self.load()
        self.apply(r["job"], [self.pocket()])
        self.assertEqual(self.error(self.plan, r["job"]), "stale_job")
        self.assertEqual(self.error(self.apply, r["job"], [self.pocket()]), "stale_job")

    def test_reapply_keeps_and_removes(self):
        r = self.load()
        first = self.apply(r["job"], [self.pocket(), self.pocket(preset="magnet-disc-5x3", point=[105, 105, 20])])
        job_id, source = self.s.new_job()
        shutil.copyfile(first["path"], source)
        r2 = self.s.load(job_id, first["path"], 1, {})
        existing = {e["label"]: e["id"] for e in r2["existing"]}
        self.assertEqual(set(existing), {"6x3 magnet", "5x3 magnet"})
        self.assertEqual([p["embedder"] for p in r2["pauses"]], [True])
        self.assertEqual(self.error(self.apply, r2["job"], (), ["1"]), "not_embedder_part")
        second = self.apply(r2["job"], remove=[existing["6x3 magnet"]])
        pkg = threemf.read(second["path"])
        self.assertEqual([e.label for e in pkg.embedder_parts()], ["5x3 magnet"])
        self.assertEqual([(l.top_z, l.extra) for l in pkg.layers], [(19.2, "Embedder: insert 1 x 5x3 magnet")])

    def test_round_pockets_from_an_older_version_stay_as_they_are(self):
        """Up to 0.2.0 a disc got a 64-sided cylinder. Its mesh lives in the project, so it is kept, paused for and
        removable like any other pocket; only new pockets are hexagons."""
        r = self.load()
        with mock.patch.object(pocket.Pocket, "mesh", lambda p: geometry.cylinder_mesh(p.size[0], p.size[2])):
            old = self.apply(r["job"], [self.pocket()])
        job_id, source = self.s.new_job()
        shutil.copyfile(old["path"], source)
        r2 = self.s.load(job_id, old["path"], 1, {})
        self.assertEqual([(e["label"], e["mode"]) for e in r2["existing"]], [("6x3 magnet", "embedded")])
        out = self.apply(r2["job"], [self.pocket(point=[105, 105, 20])])
        self.assertEqual([p["top_z"] for p in out["pauses"]], [19.2])
        job_id, source = self.s.new_job()
        shutil.copyfile(out["path"], source)
        parts = self.s.load(job_id, out["path"], 1, {})["objects"][0]["parts"]
        self.assertEqual([(p["embedder"], p["vertices"]) for p in parts], [(False, 8), (True, 130), (True, 14)])
        self.assertEqual(out["pauses"][0]["extra"], "Embedder: insert 2 x 6x3 magnet")

    def test_projects_saved_by_orca_2_5_1_and_other_writers(self):
        for builder in (fixtures.orca_251, fixtures.odd_attributes):
            r = self.load(builder)
            out = self.apply(r["job"], [self.pocket()])
            self.assertEqual(out["pauses"], [{"top_z": 19.2, "extra": "Embedder: insert 1 x 6x3 magnet"}], builder)
            self.assertEqual([e.label for e in threemf.read(out["path"]).embedder_parts()], ["6x3 magnet"])
            job_id, source = self.s.new_job()
            shutil.copyfile(out["path"], source)
            (existing,) = self.s.load(job_id, out["path"], 1, {})["existing"]
            again = self.apply(job_id, remove=[existing["id"]])
            pkg = threemf.read(again["path"])
            self.assertEqual((pkg.embedder_parts(), pkg.layers), ((), ()), builder)

    def test_existing_user_gcode_at_the_same_layer(self):
        r = self.load(fixtures.user_pause, z=19.2)
        out = self.apply(r["job"], [self.pocket()])
        self.assertEqual(out["pauses"], [])
        self.assertIn("existing_gcode_at_layer", out["warnings"])

    def test_blocked_pocket_refuses_the_whole_apply(self):
        r = self.load(fixtures.build, settings=dict(fixtures.SETTINGS, machine_pause_gcode=""))
        self.assertEqual(self.error(self.apply, r["job"], [self.pocket()]), "pocket_blocked")
        self.assertEqual([n for n in os.listdir(self.storage) if n.endswith(".3mf")], [])

    def copy(self, name, days_old=0, size=10):
        path = os.path.join(self.storage, name)
        with open(path, "wb") as f:
            f.write(b"x" * size)
        t = time.time() - days_old * 86400
        os.utime(path, (t, t))
        return path

    def names(self):
        return sorted(n for n in os.listdir(self.storage) if n.endswith(".3mf"))

    def test_old_copies_are_pruned_after_apply(self):
        newest = self.copy("Old-embedder-20260101-000000-aaaaaa.3mf", days_old=40)
        stale = self.copy("Old-embedder-20250101-000000-bbbbbb.3mf", days_old=50)
        chain = self.copy("Old-embedder-20250101-000000-bbbbbb-embedder-20250102-000000-cccccc-2.3mf", days_old=45)
        many = [self.copy("Many-embedder-20261101-0000%02d-dddddd.3mf" % n, days_old=1 + n / 100) for n in range(14)]
        mine = self.copy("notes.3mf", days_old=400)
        r = self.load()
        out = self.apply(r["job"], [self.pocket()])
        left = set(self.names())
        self.assertIn(os.path.basename(newest), left)                 # the newest copy of a project stays, however old
        self.assertNotIn(os.path.basename(stale), left)               # older than KEEP_DAYS
        self.assertNotIn(os.path.basename(chain), left)               # a copy of a copy counts as the same project
        self.assertIn(os.path.basename(many[0]), left)
        self.assertEqual(sum(os.path.basename(m) in left for m in many), 1 + session.KEEP_COPIES)
        self.assertIn(os.path.basename(mine), left)                   # not an Embedder copy: never touched
        self.assertIn(out["name"], left)
        self.assertEqual(out["pruned"], 2 + 14 - 1 - session.KEEP_COPIES)

    def test_clear_old_copies_keeps_what_orca_may_have_open(self):
        r = self.load()
        first = self.apply(r["job"], [self.pocket()])
        r = self.load()
        second = self.apply(r["job"], [self.pocket()])
        older = self.copy("My Part-embedder-20250101-000000-eeeeee.3mf", size=1000)
        other = self.copy("Other-embedder-20250101-000000-ffffff.3mf", size=7)
        os.utime(older, (1, 1))
        status = self.s.copies_status()
        self.assertEqual((status["count"], status["bytes"]), (1, 1000))
        self.assertEqual(status["kept"], 3)
        cleared = self.s.clear_copies()
        self.assertEqual((cleared["removed"], cleared["freed"], cleared["failed"], cleared["count"]), (1, 1000, 0, 0))
        self.assertEqual(self.names(), sorted([first["name"], second["name"], os.path.basename(other)]))
        fresh = session.Session(self.storage, self.store.effective)   # a new OrcaSlicer session
        self.assertEqual(fresh.copies_status()["count"], 1)
        fresh.clear_copies()
        self.assertEqual(self.names(), sorted([second["name"], os.path.basename(other)]))

    def test_bad_apply_args(self):
        r = self.load()
        self.assertEqual(self.error(self.s.apply, {"job": r["job"], "pockets": "x"}), "bad_request")
        self.assertEqual(self.error(self.s.apply, {"job": r["job"], "pockets": [], "remove": [1]}), "bad_request")


if __name__ == "__main__":
    unittest.main()
