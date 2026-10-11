"""Host-only authored-content checks; no native or GPU claim."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from tools.renderer_oracle import prepare, sdvk008_fixtures as fixtures
from tools.renderer_oracle.tests.test_corpus import unpack_png, unpack_wad, parse_udmf


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
            self.assertEqual(camera['angle'],scene['native']['camera']['yaw'])
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
