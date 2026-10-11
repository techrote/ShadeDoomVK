"""Host-only authored-content checks; no native or GPU claim."""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
import tempfile
import unittest

from tools.renderer_oracle import prepare, sdvk008_fixtures as fixtures
from tools.renderer_oracle.tests.test_corpus import unpack_png, unpack_wad, parse_udmf
from tools.pf_oracle import fixture_runner


class PhysicalFixtureTests(unittest.TestCase):
    def setUp(self):
        self.catalog = prepare.load_catalog()
        self.scenes = {s["id"]:s for s in self.catalog["scenes"]}

    def test_declared_finite_variants_and_queries(self):
        prepare.validate_catalog(self.catalog)
        self.assertEqual(len(fixtures.TIMING_VARIANTS),11)
        for variant,name in fixtures.TIMING_VARIANTS.items():
            settings=self.scenes[name]["native"]["settings"]
            self.assertEqual(settings["gl_sprite_relief_depth"],0 if variant.endswith("0") else .012)
            self.assertEqual(settings["gl_sprite_relief_quality"],1 if variant.endswith("L") else 3 if variant.endswith("H") else 2)
            self.assertEqual(self.scenes[name]["native"]["console_queries"],sorted(settings))

    def test_matched_packages_identical_and_only_relief_controls_differ(self):
        for pair in fixtures.CORRECTNESS_PAIRS:
            off,on=(self.scenes[pair[key]] for key in ("off","on"))
            a,_,_=prepare.scene_assets(off);b,_,_=prepare.scene_assets(on)
            self.assertEqual(a,b,pair["id"])
            x,y=(dict(s["native"]["settings"]) for s in (off,on))
            for key in ("gl_sprite_relief_depth","gl_sprite_relief_quality"):
                x.pop(key,None);y.pop(key,None)
            self.assertEqual(x,y)

    def test_bam_revision_preserves_all_original_authored_pk3_bytes(self):
        # Package identities at 44923b9bd, retained before separating
        # expected view angles from authored UDMF integers. This fixes a pose
        # expectation only; any content change needs a separate fixture revision.
        original = {
            'single':'e538c47ce0c625099c25ab2817ad3a16181df5fe69f3c503a5e54029bb5f1114',
            'multiple':'38016134a7d31f7ebdb4c43bcb20fd256bd004536a51c39d6eab9816c57faacd',
            'grazing':'3878cdca16b5e83d64f76d41384978b869955478b15dcf40c525e57656f0bb44',
            'pbr':'91b31bf7d579149cc7d5c3409951f1f0f4172eb2415a633970a471200d9850d2',
            'heightless':'9c1e8d025b01c6b7f09b1aaa212bab6588b45cfb98850d3b239640539636b3f3',
            'alpha':'d385408a1e7691c2ee85c215e8a66b238983fff84ccb935262bdf0c29eb0f5b7',
            'mirror':'621d2df42e84b6e6c16b8ab9bdf87bdf69873ac2d440edab5f0a1ad471a68063',
            'alpha-background':'b9fc66c4628e732fd2e18e2859cdde4046d4796d9e09c5204dffa53dffe624f2',
            'grazing-fallback':'3abc07559960be77decdb8987b70e235d6dcd27d5088dcae9a25109d677bdf14',
            'flipx':'8c8ea6e889b538f160daa3887ac6410a3510cc24b50815e30d9bc7b50484974c',
            'flipy':'f1a2bb3179b1263595ee025e8b3b80f92c73a16634f69bb134963840988fdcd0',
        }
        self.assertEqual(set(original),fixtures.FAMILIES)
        scenes=[s for s in self.scenes.values() if s['native']['generator']=='sprite_relief']
        self.assertEqual(len(scenes),25)
        for scene in scenes:
            pk3,_,_=prepare.scene_assets(scene)
            self.assertEqual(hashlib.sha256(pk3).hexdigest(),original[scene['native']['relief_family']],scene['id'])

    def test_default_omits_depth_assignment_and_queries_it(self):
        scene=self.scenes["sdvk008-default-off"]
        self.assertNotIn("gl_sprite_relief_depth",scene["native"]["settings"])
        self.assertNotIn(b"gl_sprite_relief_depth=",prepare.configuration(scene))
        self.assertIn(b"; gl_sprite_relief_depth;",prepare.capture_script(scene))

    def test_height_is_asymmetric_and_nonflat(self):
        h=fixtures.pixels("height")
        values=h[::4]
        self.assertGreater(len(set(values)),64)
        self.assertNotEqual(values,bytes(v for row in range(128) for v in values[row*128:(row+1)*128][::-1]))
        self.assertTrue(all(h[i]==h[i+1]==h[i+2] and h[i+3]==255 for i in range(0,len(h),4)))

    def test_camera_content_and_overlapping_count(self):
        for suffix,count in (("s0",1),("m0",8),("g0",5),("p0",1)):
            scene=self.scenes["sdvk008-"+suffix]
            _,members,metadata=prepare.scene_assets(scene)
            rows=parse_udmf(unpack_wad(members['maps/'+scene['native']['map']+'.wad'])["TEXTMAP"])["thing"]
            cards=[r for r in rows if r["type"]==32218]
            self.assertEqual(len(cards),count)
            camera=next(r for r in rows if r["id"]==2002)
            self.assertEqual([camera["x"],camera["y"],camera["height"]],scene['native']['camera']['position'])
            self.assertEqual(camera['angle'],scene['native']['authored_camera_angles']['yaw'])
            self.assertFalse(metadata['directional_native_qualified'])

    def test_alpha_has_hole_edges_and_filtered_height_pbr_semantics(self):
        for suffix in ("alpha-on","pm"):
            _,members,_=prepare.scene_assets(self.scenes['sdvk008-'+suffix])
            header,pixels=unpack_png(members['sprites/SDVEA0.png'])
            self.assertEqual((header['width'],header['height']),(128,128))
            if suffix=='alpha-on':
                self.assertEqual(pixels[(50*128+50)*4+3],0)
                self.assertEqual(pixels[3],0)
                self.assertEqual(pixels[(30*128+30)*4+3],255)
            else:
                for semantic in (b'normal',b'metallic',b'roughness',b'ao',b'height'):
                    self.assertIn(semantic,members['GLDEFS'])
                self.assertEqual(members['GLDEFS'].count(b'filter linear'),5)

    def test_bad_family_and_false_completeness_fail(self):
        altered=copy.deepcopy(self.catalog)
        altered['scenes'][-1]['native']['relief_family']='unknown'
        with self.assertRaisesRegex(ValueError,'Unknown SDVK-008'):
            prepare.validate_catalog(altered)
        self.assertTrue(fixtures.MISSING_GATES)
        self.assertTrue(set(fixtures.MISSING_GATES).isdisjoint(fixtures.AVAILABLE_GATES))
        self.assertEqual(set(fixtures.REQUIRED_GATES),set(fixtures.MISSING_GATES)|set(fixtures.AVAILABLE_GATES))

    def test_direction_oracle_rejects_wrong_stationary_and_unavailable_markers(self):
        def image(dx=0,dy=0):
            data=bytearray(bytes((20,30,40))*400)
            for y in range(8+dy,12+dy):
                for x in range(8+dx,12+dx):
                    at=(y*20+x)*3
                    data[at:at+3]=bytes((220,40,60))
            return bytes(data)
        self.assertEqual(fixtures.red_marker_direction(image(),image(1,-1),20,20)['status'],'PASS')
        for moved in (image(),image(-1,1),image(1,1),image(-1,-1)):
            self.assertEqual(fixtures.red_marker_direction(image(),moved,20,20)['status'],'FAIL')
        self.assertEqual(fixtures.red_marker_direction(bytes(1200),bytes(1200),20,20)['status'],'UNAVAILABLE')
        with self.assertRaises(ValueError):
            fixtures.red_marker_direction(b'bad',b'bad',20,20)

    def test_background_matte_changes_only_card_placement_in_content(self):
        _,off,_=prepare.scene_assets(self.scenes['sdvk008-alpha-off'])
        _,bg,_=prepare.scene_assets(self.scenes['sdvk008-alpha-background'])
        self.assertEqual(set(off),set(bg))
        differences=[key for key in off if off[key]!=bg[key]]
        self.assertEqual(differences,['maps/SRLALPHA.wad'])
        for members,count in ((off,1),(bg,0)):
            rows=parse_udmf(unpack_wad(members['maps/SRLALPHA.wad'])['TEXTMAP'])['thing']
            self.assertEqual(len([t for t in rows if t['type']==32218]),count)

    def test_hard_grazing_whole_quad_stays_below_point_two(self):
        scene=self.scenes['sdvk008-grazing-fallback-on']
        cx,cy,cz=scene['native']['camera']['position']
        # Card angle180 lies x=0; even the nearest possible point of its
        # continuous y[-64,64], z[0,128] rectangle has Vz <0.20.
        nearest_y=max(-64,min(64,cy))
        nearest_z=max(0,min(128,cz))
        maximum_vz=-cx/math.sqrt(cx*cx+(cy-nearest_y)**2+(cz-nearest_z)**2)
        self.assertLess(maximum_vz,.20)
        self.assertGreater(maximum_vz,0)

    def test_fractional_camera_angle_rejected_before_native_parse(self):
        scene=copy.deepcopy(self.scenes['sdvk008-s0'])
        scene['native']['authored_camera_angles']['yaw']=26.5
        with self.assertRaisesRegex(ValueError,'authored integers'):
            prepare.scene_assets(scene)

    def test_expected_pose_is_exact_canonical_conversion_and_fails_closed(self):
        self.assertEqual(fixtures.canonical_view_angle(27),26.999999983236194)
        self.assertEqual(fixtures.canonical_view_angle(87),87.00000001117587)
        for scene in self.scenes.values():
            if scene['native']['generator'] != 'sprite_relief':
                continue
            native=scene['native']
            fixtures.validate_camera(native)
            for key,value in native['authored_camera_angles'].items():
                self.assertEqual(native['camera'][key],fixtures.canonical_view_angle(value))
        scene=copy.deepcopy(self.scenes['sdvk008-s0'])
        scene['native']['camera']['yaw']=27
        with self.assertRaisesRegex(ValueError,'canonical BAM'):
            prepare.scene_assets(scene)
        altered=copy.deepcopy(self.catalog)
        next(s for s in altered['scenes'] if s['id']=='sdvk008-s0')['native']['camera']['yaw']=27
        with self.assertRaisesRegex(ValueError,'canonical BAM'):
            prepare.validate_catalog(altered)

    def test_canonical_conversion_matches_compiled_production_header(self):
        root=Path(__file__).resolve().parents[3]
        result=fixture_runner.run_fixture(
            'tools/renderer_oracle/tests/sdvk008_camera_angle_fixture.cpp', root=root,
            includes=['src/common/utility','src/common/thirdparty'],capture_output=True)
        rows=[line.split() for line in result.stdout.splitlines()]
        self.assertEqual(len(rows),361)
        for authored,observed in rows:
            self.assertEqual(fixtures.canonical_view_angle(int(authored)),float(observed))
        # Retain the actual normalization path, rather than merely reproducing
        # header arithmetic which could become unused by view construction.
        view=(root/'src/rendering/r_utility.cpp').read_text()
        for key in ('Yaw','Pitch','Roll'):
            self.assertIn('viewPoint.Angles.'+key+' = viewPoint.Angles.'+key+'.Normalized180();',view)

    def test_signed_uv_actor_flags_are_independently_authored(self):
        for family,flag in (('flipx',b'+XFLIP'),('flipy',b'+YFLIP')):
            _,members,_=prepare.scene_assets(self.scenes['sdvk008-'+family+'-on'])
            card=members['ZSCRIPT'].split(b'class SDVKReliefCard')[1]
            self.assertIn(flag,card)
            self.assertIn(b'+WALLSPRITE',card)

    def test_preparation_authenticates_generated_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'prepared'
            prepare.prepare(out,['sdvk008-s0','sdvk008-sm'])
            manifest=prepare.verify_prepared(out)
            self.assertFalse(manifest['native_executed'])
            package=out/'scenes/sdvk008-sm/scene.pk3'
            package.write_bytes(package.read_bytes()+b'tamper')
            with self.assertRaisesRegex(ValueError,'asset changed'):
                prepare.verify_prepared(out)


if __name__=='__main__':
    unittest.main()
