#!/usr/bin/env python3
"""Offline SDVK-010 synthetic prepass contracts. NOT a renderer qualification."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate as gen
import validate as val


def live_event():
    def identity(idx):
        return {"index":idx,"generation":6,"epoch":3,"span":2,"owner":"synthetic-pair-0001"}
    def resource(idx):
        return {"available":True,"index":idx,"view_type":"cube","identity":identity(idx)}
    return {
        "frame":0,"draw_id":"actor-draw1","pipeline_sha":"synthetic-shader",
        "actor":{"semantic_actor_id":"actor1","surface":"sprite","world_position":[0,0,64],
                 "sector_present":True,"sector_id":10,"authored_probe_index":0,
                 "material_id":"pbr-test","selection_basis":"sector-authored","basis_mode":"deferred-007"},
        "context":{"map":"SDVK10","root_type":"main","view_epoch":1,"view_identity":1,
                   "source_portal_group":0,"render_portal_group":0,"mirror":False,
                   "displacement":[0,0,0]},
        "probe":{"mode":"uniform","runtime_base":713,"fallback":False,"fallback_reason":"none",
                 "irradiance":resource(713),"prefilter":resource(714),"pair_owner":"synthetic-pair-0001",
                 "probe_epoch":2,"lightmap_epoch":2,"levelmesh_epoch":2,
                 "lightmap_probe_epoch":2,"bindless_capacity":4096,"dynamic_start":259,
                 "probe_map_page":None,"probe_map_value":None,"publication_phase":"published"},
        "pbr":{"active":True,"metallic":0,"roughness":0.5,"ao":1,
               "world_normal":[0,0,1],"world_view":[0,0,1],"world_reflection":[0,0,1],
               "prefilter_lod":2,"sampler_direction_space":"shader-world"},
        "sun":{"world_direction":[0,0,1],"shader_direction":[0,1,0],
               "color":[1,1,1],"intensity":1,"attenuation":0.5,
               "visibility_mode":"cpu-tracesky","visibility_result":1.0,"world_query_epoch":2},
    }


def packet(*events):
    return {"schema":val.SCHEMA,"fixture_id":"F01-uniform-neutral",
            "capture_id":"synthetic-capture-A","events":list(events)}


class AuthoredReferenceTests(unittest.TestCase):
    def test_axes_and_sign_and_reflection(self):
        self.assertEqual(list(gen.FACE_RGB),["+X","-X","+Y","-Y","+Z","-Z"])
        for d,face in (([1,0,0],"+X"),([-1,0,0],"-X"),([0,1,0],"+Y"),
                       ([0,-1,0],"-Y"),([0,0,1],"+Z"),([0,0,-1],"-Z")):
            self.assertEqual(gen.face_major_axis(d),face)
        self.assertEqual(gen.reflect_view([0,0,1],[0,0,1]),[0,0,1])
        self.assertAlmostEqual(gen.reflect_view([0,0.6,0.8],[0,0,1])[1],-0.6,places=9)
        with self.assertRaises(ValueError):
            gen.reflect_view([0,0,0],[0,1,0])
        with self.assertRaises(ValueError):
            gen.prefilter_lod(1.01)

    def test_world_probe_index_is_runtime_not_authored(self):
        data=[{"world_position":[-128,0,64],"runtime_irradiance":713},
              {"world_position":[128,0,64],"runtime_irradiance":1201}]
        self.assertEqual(gen.world_texel_nearest_live(data,[-128,0,64]),713)
        self.assertEqual(gen.world_texel_nearest_live(data,[0,0,64]),713)  # first-entry tie
        self.assertEqual(gen.world_texel_nearest_live(list(reversed(data)),[0,0,64]),1201)
        self.assertEqual(gen.world_texel_nearest_live(data,[1,0,64]),1201)
        self.assertEqual(gen.world_texel_nearest_live(data,[640,0,64]),1201)  # inclusive 512
        self.assertEqual(gen.world_texel_nearest_live(data,[640.01,0,64]),0)
        self.assertEqual(gen.world_texel_nearest_live(
            [{"world_position":[0,0,0],"runtime_irradiance":0},
             {"world_position":[1,0,0],"runtime_irradiance":65536}],[0,0,0]),0)

    def test_png_generator_is_deterministic_and_authored(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            one=gen.generate(Path(a))
            two=gen.generate(Path(b))
            self.assertEqual(one,two)
            self.assertEqual(len(one["assets"]),54)
            self.assertEqual((Path(a)/"manifest.json").read_bytes(),(Path(b)/"manifest.json").read_bytes())
            self.assertEqual((Path(a)/"offline_goldens.json").read_bytes(),
                             (Path(b)/"offline_goldens.json").read_bytes())
            for relative,record in one["assets"].items():
                payload=(Path(a)/relative).read_bytes()
                self.assertEqual(payload[:8],b"\x89PNG\r\n\x1a\n")
                self.assertEqual(record["sha256"],hashlib.sha256(payload).hexdigest())
            self.assertEqual(json.loads((Path(a)/"offline_goldens.json").read_text())
                             ["unavailable_result"],0)


class ProposedObservationTests(unittest.TestCase):
    def test_live_ordinal_zero_is_not_runtime_fallback(self):
        self.assertEqual(val.validate(packet(live_event()))["draws_checked"],1)

    def test_missing_pair_and_typed_fallback(self):
        event=live_event()
        probe=event["probe"]
        probe.update(runtime_base=0,fallback=True,fallback_reason="pair-unpublished",
                     irradiance={"available":False,"index":None,"identity":None,"view_type":"none"},
                     prefilter={"available":False,"index":None,"identity":None,"view_type":"none"},
                     pair_owner=None,publication_phase="initial")
        self.assertEqual(val.validate(packet(event))["draws_checked"],1)
        probe["prefilter"]["available"]=True
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(event))

    def test_pair_adjacent_and_same_generation_and_capacity(self):
        original=live_event()
        event=copy.deepcopy(original)
        event["probe"]["prefilter"]["identity"]["generation"]=5
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(event))
        event=copy.deepcopy(original)
        event["probe"]["prefilter"]["index"]=715
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(event))
        event=copy.deepcopy(original)
        event["probe"]["bindless_capacity"]=714
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(event))

    def test_reflection_and_roughness_and_sun_evidence(self):
        event=live_event()
        event["pbr"]["world_reflection"]=[0,0,-1]
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(event))
        event=live_event()
        event["pbr"]["prefilter_lod"]=4.3
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(event))
        event=live_event()
        event["sun"]["visibility_result"]=1.1
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(event))

    def test_lifetime_reset_and_reuse(self):
        a=live_event()
        b=copy.deepcopy(a)
        b["frame"]=1
        b["draw_id"]="actor-draw2"
        b["probe"]["publication_phase"]="cleared"
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(a,b))   # probe content reset must advance
        b["probe"]["probe_epoch"]=3
        self.assertEqual(val.validate(packet(a,b))["draws_checked"],2)
        b=copy.deepcopy(a)
        b["frame"]=1
        b["probe"]["irradiance"]["identity"]["owner"]="new-owner"
        b["probe"]["prefilter"]["identity"]["owner"]="new-owner"
        b["probe"]["pair_owner"]="new-owner"
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(a,b))   # same numeric slot, unchanged generation
        b["probe"]["irradiance"]["identity"]["generation"]=7
        b["probe"]["prefilter"]["identity"]["generation"]=7
        self.assertEqual(val.validate(packet(a,b))["draws_checked"],2)

    def test_source_absent_not_silently_sector_assigned(self):
        evt=live_event()
        evt["actor"]["sector_present"]=False
        evt["actor"]["sector_id"]=None
        with self.assertRaises(val.InvalidEvidence):
            val.validate(packet(evt))
        evt["actor"]["selection_basis"]="unresolved"
        self.assertEqual(val.validate(packet(evt))["draws_checked"],1)

    def test_world_lightmap_uniform_zero_is_not_a_missing_ibl_claim(self):
        evt=live_event()
        p=evt["probe"]
        p.update(mode="lightmap-gather",runtime_base=0,
                 irradiance={"available":False,"index":None,"identity":None,"view_type":"none"},
                 prefilter={"available":False,"index":None,"identity":None,"view_type":"none"},
                 pair_owner=None,probe_map_page=0,probe_map_value=1201)
        self.assertEqual(val.validate(packet(evt))["draws_checked"],1)
        # This event can pass structural checks, but it is not *accepted*:
        # actual four tap identities/weights require native renderer capture.


if __name__=="__main__":
    unittest.main()
