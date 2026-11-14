import base64
import os
import shutil
import sys
import tempfile
import time
import unittest
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src", "embedder"), os.path.join(ROOT, "tests")]
import fixtures  # noqa: E402
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

    def test_two_instances_are_listed(self):
        r = self.load(fixtures.two_instances)
        self.assertEqual([(o["item"], o["instance"]) for o in r["objects"]], [(0, 0), (1, 1)])

    def test_bad_project(self):
        job_id, source = self.s.new_job()
        with open(source, "wb") as f:
            f.write(b"junk")
        self.assertEqual(self.error(self.s.load, job_id, "", 1, {}), "bad_package")


class Plan(Base):
    def test_embedded_on_top(self):
        r = self.load()
        p = self.plan(r["job"])
        self.assertEqual((p["mode"], p["face"], p["shape"], p["label"], p["kind"]), ("embedded", "top", "cylinder", "6x3 magnet", "magnet"))
        self.assertAlmostEqual(p["floor"], 15.8)
        self.assertAlmostEqual(p["top"], 19.0)
        self.assertAlmostEqual(p["pause_z"], 19.2)
        self.assertEqual(len(p["transform"]), 16)
        self.assertEqual(len(p["preview"]["indices"]), 256 * 3)
        self.assertEqual(p["warnings"], [])
        self.assertIsNone(p["blocked"])

    def test_normal_comes_from_the_triangle_not_the_page(self):
        r = self.load()
        p = self.plan(r["job"], tri=SIDE_TRI, point=[120, 110, 10], normal=[0, 0, 1])
        self.assertEqual(p["face"], "side")

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
                 ({"preset": "nope"}, "unknown_preset"), ({"object": 3}, "bad_request"), ({"spin": "a"}, "bad_request")]
        for kw, code in cases:
            self.assertEqual(self.error(self.plan, r["job"], **kw), code, kw)

    def test_negative_part_cannot_be_picked(self):
        r = self.load(fixtures.multipart_with_negative)
        self.assertEqual(self.error(self.plan, r["job"], part=1), "bad_part")

    def test_cut_object(self):
        cut = '<?xml version="1.0"?>\n<objects>\n <object id="1">\n  <cut_id id="5" check_sum="1" connectors_cnt="1"/>\n </object>\n</objects>\n'
        r = self.load(extra={"Metadata/cut_information.xml": cut})
        self.assertEqual(self.error(self.plan, r["job"]), "cut_object")

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

    def test_existing_user_gcode_at_the_same_layer(self):
        r = self.load(fixtures.user_pause, z=19.2)
        out = self.apply(r["job"], [self.pocket()])
        self.assertEqual(out["pauses"], [])
        self.assertIn("existing_gcode_at_layer", out["warnings"])

    def test_blocked_pocket_refuses_the_whole_apply(self):
        r = self.load(fixtures.build, settings=dict(fixtures.SETTINGS, machine_pause_gcode=""))
        self.assertEqual(self.error(self.apply, r["job"], [self.pocket()]), "pocket_blocked")
        self.assertEqual([n for n in os.listdir(self.storage) if n.endswith(".3mf")], [])

    def test_bad_apply_args(self):
        r = self.load()
        self.assertEqual(self.error(self.s.apply, {"job": r["job"], "pockets": "x"}), "bad_request")
        self.assertEqual(self.error(self.s.apply, {"job": r["job"], "pockets": [], "remove": [1]}), "bad_request")


if __name__ == "__main__":
    unittest.main()
