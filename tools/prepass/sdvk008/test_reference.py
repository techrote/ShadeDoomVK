#!/usr/bin/env python3
"""Pure host prepass tests and reproducible parameter-grid receipt generator.
Run: python3 -m unittest discover -s tools/prepass/sdvk008 -p test_reference.py -v
     python3 tools/prepass/sdvk008/test_reference.py --receipt RESULTS.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from tools.prepass.sdvk008 import reference as r, fixtures
else:
    from . import reference as r, fixtures


class ReferenceTests(unittest.TestCase):
    def assert_bounded(self, out, uv, *, rect=(0.,0.,1.,1.)):
        self.assertTrue(all(math.isfinite(x) for x in out.uv))
        self.assertLessEqual(out.height_samples, r.MAX_HEIGHT_SAMPLES)
        self.assertLessEqual(out.actual_steps, max(n for n,_ in r.POLICIES.values()))
        self.assertLessEqual(out.max_excursion, r.MAX_UV_EXCURSION + 1e-12)
        if rect[0] <= uv[0] <= rect[2] and rect[1] <= uv[1] <= rect[3]:
            self.assertTrue(rect[0]-1e-12 <= out.uv[0] <= rect[2]+1e-12)
            self.assertTrue(rect[1]-1e-12 <= out.uv[1] <= rect[3]+1e-12)
        if out.fallback_reason != "NONE":
            self.assertEqual(out.uv, uv)
            self.assertFalse(out.relief_applied)

    def test_height_constants_exact_depth(self):
        uv=(.5,.5); view=(.6,0.,.8); scale=.012
        for name in ("constant_0","constant_05","constant_1"):
            h=fixtures.height_grid(name)
            out=r.resolve(h,uv,view,scale)
            expected=1-h[0][0]
            self.assertAlmostEqual(out.uv[0], uv[0]-scale*(view[0]/view[2])*expected, places=10)
            self.assertAlmostEqual(out.intersection_depth,expected,places=10)
            self.assert_bounded(out,uv)
        self.assertEqual(r.resolve(fixtures.height_grid("constant_1"),uv,view,scale).height_samples,1)

    def test_exact_optout_and_height_missing(self):
        h=fixtures.height_grid("mound")
        for kw, reason in (({"policy":"off"},"DISABLED"),
                           ({"height":None},"NO_HEIGHT"),
                           ({"scale":0},"ZERO_SCALE"),
                           ({"scale":-1},"NEGATIVE_SCALE"),
                           ({"basis_supported":False},"UNSUPPORTED_BASIS")):
            opts={"height":h,"uv":(.3,.6),"view":(.5,.2,.9),"scale":.01}
            opts.update(kw)
            out=r.resolve(**opts)
            self.assertEqual(out.fallback_reason,reason)
            self.assertEqual(out.height_samples,0)
            self.assertEqual(out.uv,(.3,.6))

    def test_grazing_backside_and_front(self):
        h=fixtures.height_grid("ramp")
        for view,reason in (((0,0,1),"FRONT_ON"),((1,0,0),"GRAZING_OR_BACKFACE"),
                            ((1,0,.19),"GRAZING_OR_BACKFACE"),((.2,.2,-1),"GRAZING_OR_BACKFACE")):
            out=r.resolve(h,(.5,.5),view,.02)
            self.assertEqual(out.fallback_reason,reason)
            self.assertEqual(out.height_samples,0)
        front_near=r.resolve(h,(.5,.5),(.99,0,.22),.02)
        self.assert_bounded(front_near,(.5,.5))

    def test_mirror_reflection_symmetry(self):
        h=fixtures.height_grid("asymmetric_wedge")
        uv=(.49,.57); v=(.36,-.18,.91)
        base=r.resolve(h,uv,v,.015,"high")
        mirrored=[list(reversed(row)) for row in h]
        flip=r.resolve(mirrored,(1-uv[0],uv[1]),(-v[0],v[1],v[2]),.015,"high")
        self.assertEqual(base.fallback_reason, "NONE")
        self.assertEqual(flip.fallback_reason, "NONE")
        self.assertAlmostEqual(base.uv[0], 1-flip.uv[0], places=10)
        self.assertAlmostEqual(base.uv[1], flip.uv[1], places=10)
        self.assertEqual(base.height_samples,flip.height_samples)
        self.assertEqual(base.refined,flip.refined)

    def test_silhouette_no_new_cutout(self):
        h=fixtures.height_grid("constant_0")
        a=fixtures.alpha_grid()
        for uv in ((.01,.01),(.49,.49)):
            out=r.resolve(h,uv,(.7,0,.7),.02,alpha=a)
            self.assertEqual(out.fallback_reason,"BASE_TRANSPARENT")
            self.assertEqual(out.height_samples,0)
        # Opaque original texel walks into transparent left neighbour.
        m=[[1.0]*16 for _ in range(16)]
        for row in m: row[7]=0.0
        out=r.resolve(h,(.52,.53),(.8,0,.6),.02,"high",alpha=m)
        self.assertEqual(out.fallback_reason,"ALPHA_ESCAPE")
        self.assertEqual(out.uv,(.52,.53))
        self.assert_bounded(out,(.52,.53))

    def test_frame_escape_rejects_not_wraps(self):
        h=fixtures.height_grid("constant_0")
        out=r.resolve(h,(.003,.5),(.8,0,.6),.02)
        self.assertEqual(out.fallback_reason,"FRAME_ESCAPE")
        self.assertEqual(out.uv,(.003,.5))
        self.assert_bounded(out,(.003,.5))
        out=r.resolve(h,(.215,.5),(.8,0,.6),.02,rect=(.2,.1,.8,.9))
        self.assertEqual(out.fallback_reason,"FRAME_ESCAPE")
        self.assert_bounded(out,(.215,.5),rect=(.2,.1,.8,.9))

    def test_adversarial_numeric_inputs(self):
        h=fixtures.height_grid("ramp")
        base={"height":h,"uv":(.5,.5),"view":(.4,.3,.8),"scale":.01}
        for override,reason in (({"height":[[0.0],[float("nan")]]},"INVALID_HEIGHT"),
                                ({"height":[[float("inf")]]},"INVALID_HEIGHT"),
                                ({"height":[[1.2]]},"INVALID_HEIGHT"),
                                ({"height":[[.5],[.1,.2]]},"INVALID_HEIGHT"),
                                ({"scale":float("nan")},"INVALID_SCALE"),
                                ({"scale":float("inf")},"INVALID_SCALE"),
                                ({"scale":1e9},"SCALE_LIMIT"),
                                ({"view":(0.,0.,0.)},"ZERO_VIEW"),
                                ({"view":(float("nan"),0.,1.)},"INVALID_VIEW"),
                                ({"lod":float("inf")},"INVALID_LOD"),
                                ({"policy":"adaptive-infinite"},"INVALID_POLICY"),
                                ({"rect":(0.,1.,0.,1.)},"INVALID_RECT")):
            opts=dict(base);opts.update(override)
            out=r.resolve(**opts)
            self.assertEqual(out.fallback_reason,reason)
            self.assertEqual(out.height_samples,0)
        bad=r.resolve(h,(float("nan"),.4),(.4,0,1),.01)
        self.assertTrue(bad.numerical_anomaly)
        self.assertEqual(bad.uv,(.5,.5))
        self.assertEqual(bad.fallback_reason,"INVALID_UV")

    def test_mip_lod_clamp_and_1x1(self):
        h=fixtures.height_grid("checker")
        out=r.resolve(h,(.51,.51),(.3,.2,.95),.012,lod=99)
        self.assertEqual(out.derived_lod, r.MAX_HEIGHT_LOD)
        self.assert_bounded(out,(.51,.51))
        one=r.resolve([[.5]],(.5,.5),(.6,0,.8),.012,policy="low")
        self.assertAlmostEqual(one.intersection_depth,.5,places=10)
        self.assert_bounded(one,(.5,.5))

    def test_size_fade_bound(self):
        h=fixtures.height_grid("constant_0")
        inputs={"height":h,"uv":(.5,.5),"view":(.6,0,.8),"scale":.02}
        self.assertEqual(r.resolve(**inputs,projected_pixels=16).fallback_reason,"TOO_SMALL")
        near=r.resolve(**inputs,projected_pixels=24)
        full=r.resolve(**inputs,projected_pixels=32)
        self.assertGreater(abs(full.uv[0]-.5),abs(near.uv[0]-.5))
        for out in (near,full):self.assert_bounded(out,(.5,.5))

    def test_sample_ceiling_not_cpu_perf(self):
        h=fixtures.height_grid("thin_feature")
        for policy,(steps,refines) in r.POLICIES.items():
            out=r.resolve(h,(.5,.5),(.7,.3,.7),.015,policy)
            self.assertLessEqual(out.height_samples, 1+steps+refines)
            self.assert_bounded(out,(.5,.5))

    def test_deterministic_grid(self):
        report=grid_receipt()
        self.assertEqual(report["status"],"PASS_CPU_REFERENCE_ONLY")
        self.assertEqual(report["cases"],1620)
        self.assertEqual(sum(report["fallback_counts"].values())+report["resolved_count"],report["cases"])
        self.assertEqual(report["numerical_anomalies"],0)
        self.assertLessEqual(report["max_height_samples"],r.MAX_HEIGHT_SAMPLES)
        self.assertEqual(report["sha256"],grid_receipt()["sha256"])


def grid_receipt():
    views={"front":(0.,0.,1.),"modest":(.3,.2,1.),"oblique":(.8,.6,.45),
           "grazing":(.98,.1,.1),"back":(.3,.2,-1.)}
    points=((.5,.5),(.27,.4),(.93,.45))
    mirror_signs=((1,1),(-1,1),(1,-1),(-1,-1))
    cases=[]; reasons=Counter(); maximum=0; anomalies=0; resolved=0
    anchors=[]
    for name in fixtures.NAMES:
        h=fixtures.height_grid(name)
        for view_name,base_view in views.items():
            for mu,mv in mirror_signs:
                view=(base_view[0]*mu,base_view[1]*mv,base_view[2])
                for uv in points:
                    for policy in ("low","medium","high"):
                        out=r.resolve(h,uv,view,.015,policy,lod=0.)
                        if not all(math.isfinite(x) for x in out.uv):
                            raise AssertionError("nonfinite output")
                        if out.height_samples > r.MAX_HEIGHT_SAMPLES or out.max_excursion > r.MAX_UV_EXCURSION+1e-12:
                            raise AssertionError("sample/excursion bound exceeded")
                        if out.fallback_reason != "NONE" and out.uv != uv:
                            raise AssertionError("fallback changed source UV")
                        maximum=max(maximum,out.height_samples)
                        anomalies+=int(out.numerical_anomaly)
                        resolved+=int(out.fallback_reason=="NONE")
                        reasons.update([out.fallback_reason] if out.fallback_reason!="NONE" else [])
                        record={"height":name,"view":view_name,"mirror_uv_axes":[mu,mv],
                                "uv":list(uv),"policy":policy,"result":out.as_dict()}
                        cases.append(record)
                        if uv==points[0] and (mu,mv)==(1,1) and policy=="medium" and view_name=="modest":anchors.append(record)
    packed=json.dumps(cases,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
    return {"schema":"sdvk008-host-grid/v1","status":"PASS_CPU_REFERENCE_ONLY",
            "fixture_source":"tools/prepass/sdvk008/fixtures.py", "case_order":"height/view/mirror/UV/policy",
            "cases":len(cases),"max_height_samples":maximum,
            "height_sample_ceiling":r.MAX_HEIGHT_SAMPLES,"excursion_ceiling":r.MAX_UV_EXCURSION,
            "numerical_anomalies":anomalies,"resolved_count":resolved,
            "fallback_counts":dict(sorted(reasons.items())),
            "sha256":hashlib.sha256(packed).hexdigest(),
            "hash_input":"canonical JSON full ordered result grid; payload regenerated rather than checked in",
            "anchors":anchors,
            "physical_gpu_evidence":False,"renderer_implementation":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt",type=Path,required=True)
    a=parser.parse_args()
    a.receipt.write_text(json.dumps(grid_receipt(),sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(f"wrote {a.receipt}")

if __name__=="__main__":main()
