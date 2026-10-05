"""Authoring/source checks only; these never execute or compile a renderer."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

PATH = Path(__file__).resolve().parents[1]/"prepare_freeze_view_fixture.py"
SPEC = importlib.util.spec_from_file_location("pf020_freeze_view_inputs", PATH)
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def source(name):
    return (fixture.ROOT/name).read_text(encoding="utf-8")


def synthetic_iwad():
    """Small format service for malformed-input tests, never native content."""
    definitions = [name.encode().ljust(8, b"\0")+struct.pack("<IHHIH", 0, *(fixture.USER_EXTENT if name == fixture.USER_STOCK else (64, 64)), 0, 0)
                   for name in fixture.WALLS]
    texture = bytearray(struct.pack("<I", len(definitions))+b"\0"*(4*len(definitions)))
    for i, definition in enumerate(definitions):
        struct.pack_into("<I", texture, 4+4*i, len(texture))
        texture.extend(definition)
    lumps = [("TEXTURE1", bytes(texture))]+[(name, bytes(4096)) for name in fixture.FLATS]
    lumps += [(name, struct.pack("<HHhh", 16, 32, 8, 32)+bytes(64)) for name in sorted(set(fixture.ROTATIONS))]
    return b"IWAD"+fixture.wad(lumps)[4:]


class FreezeViewInputs(unittest.TestCase):
    def setUp(self):
        self.scene = fixture.fixture()

    def reject(self, mutate, match):
        scene = copy.deepcopy(self.scene)
        mutate(scene)
        with self.assertRaisesRegex(ValueError, match):
            fixture.validate_scene(scene)

    def test_deterministic_package_has_only_authored_control_lumps(self):
        first = fixture.archive_bytes(fixture.members())
        self.assertEqual(first, fixture.archive_bytes(fixture.members()))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertEqual(archive.namelist(), sorted(fixture.members()))
            self.assertEqual(len(archive.namelist()), 7)
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(archive.read(info), fixture.members()[info.filename])
            raw = archive.read("maps/PFVTEST.wad")
        magic, count, at = struct.unpack_from("<4sII", raw)
        self.assertEqual((magic, count), (b"PWAD", 3))
        entries = [struct.unpack_from("<II8s", raw, at+16*i) for i in range(count)]
        self.assertEqual([e[2].rstrip(b"\0") for e in entries], [b"PFVTEST", b"TEXTMAP", b"ENDMAP"])
        text_at, size, _ = entries[1]
        self.assertEqual(raw[text_at:text_at+size].decode(), fixture.textmap(self.scene))
        self.assertEqual(set(fixture.members()), {"ZSCRIPT", "MAPINFO", "ANIMDEFS", "TEXTURES", "GLDEFS", fixture.USER_SHADER_MEMBER, "maps/PFVTEST.wad"})
        self.assertFalse(any(name.lower().endswith((".png", ".lmp")) for name in fixture.members()))
        with self.assertRaisesRegex(ValueError, "unapproved"):
            fixture.archive_bytes({**fixture.members(), "LIGHTMAP": b"pretend baked"})

    def test_four_closed_clockwise_sectors_and_actual_two_sided_links(self):
        fixture.validate_scene(self.scene)
        self.assertEqual(len(self.scene["sectors"]), 4)
        portals = {line["id"]: line for line in self.scene["lines"] if line.get("special") == 156}
        self.assertEqual(set(portals), {101, 102})
        for identity, target in ((101, 102), (102, 101)):
            line = portals[identity]
            self.assertEqual([line[f"arg{i}"] for i in range(4)], [target, 0, 3, 0])
            self.assertTrue(line["twosided"])
            self.assertFalse(line["blocking"])
            self.assertNotEqual(self.scene["sides"][line["sidefront"]]["sector"],
                                self.scene["sides"][line["sideback"]]["sector"])
        portal_source = source("src/playsim/portal.cpp")
        self.assertIn("port->mOrigin->backsector == nullptr", portal_source)
        self.assertIn("port->mDestination->getPortalDestination() != port->mOrigin", portal_source)
        self.assertIn("port->mDestination->v2->fPos() - port->mOrigin->v1->fPos()", portal_source)

    def test_missing_backsector_and_unmatched_reverse_are_rejected(self):
        def remove_back(s):
            line = next(l for l in s["lines"] if l.get("id") == 101)
            del line["sideback"]
        self.reject(remove_back, "Two-sided")
        self.reject(lambda s: next(l for l in s["lines"] if l.get("id") == 102).update(arg0=999), "backlink")
        self.reject(lambda s: next(l for l in s["lines"] if l.get("id") == 101).update(arg2=0), "type")

    def test_closed_but_wrong_displacement_is_rejected(self):
        def shift_b(s):
            s["vertices"] = [(x+1 if x >= 1184 else x, y) for x, y in s["vertices"]]
        self.reject(shift_b, "displacement")
        self.reject(lambda s: next(l for l in s["lines"] if l.get("id") == 101).update(blocking=True), "backlink")

    def test_open_or_disconnected_sector_and_bad_indices_fail(self):
        self.reject(lambda s: s["lines"][0].update(v1=999), "vertex")
        self.reject(lambda s: s["lines"][0].update(sidefront=999), "sidedef")
        self.reject(lambda s: s["lines"][0].update(v2=s["lines"][2]["v2"]), "boundary")
        self.reject(lambda s: s["vertices"].__setitem__(0, (float("nan"), 0)), "finite")

    def test_mirror_is_in_linked_destination_and_not_a_second_portal(self):
        mirror = next(l for l in self.scene["lines"] if l.get("special") == 182)
        self.assertEqual(self.scene["sides"][mirror["sidefront"]]["sector"], 2)
        self.assertEqual(tuple(self.scene["vertices"][mirror[k]] for k in ("v1", "v2")), ((1472, 128), (1472, -128)))
        self.reject(lambda s: next(l for l in s["lines"] if l.get("special") == 182).update(special=0), "Nested mirror")
        self.assertIn("special == Line_Mirror", source("src/rendering/hwrenderer/scene/hw_walls.cpp"))
        context = source("src/rendering/hwrenderer/scene/hw_portal.cpp")
        self.assertIn("r_mirror_recursions", context)

    def test_camera_registered_through_actual_api_and_has_real_material_demand(self):
        script = fixture.zscript()
        self.assertIn('TexMan.SetCameraToTexture(self, "PFVCAM", 90);', script)
        self.assertLess(script.index("Super.PostBeginPlay();"), script.index("TexMan.SetCameraToTexture"))
        self.assertIn("CameraHeight 0", script)
        self.assertEqual(fixture.members()["ANIMDEFS"], b"cameratexture PFVCAM 128 128 fit 128 128\n")
        self.assertIn("native static void SetCameraToTexture(Actor viewpoint, String texture, double fov)", source("wadsrc/static/zscript/doombase.zs"))
        canvas = source("src/r_data/r_canvastexture.cpp")
        self.assertIn("viewpoint->Level->canvasTextureInfo.Add", canvas)
        self.assertIn("probe.Texture->bNeedsUpdate", canvas)
        self.assertIn("RenderTextureView", source("src/rendering/hwrenderer/hw_entrypoint.cpp"))
        def remove_demand(s):
            for side in s["sides"]:
                if side["texturemiddle"] == fixture.CAMERA:
                    side["texturemiddle"] = "STARTAN3"
        self.reject(remove_demand, "material demand")
        self.reject(lambda s: next(t for t in s["things"] if t["role"] == "camera").update(height=129), "bounded")

    def test_one_non_pbr_probe_and_six_faces_remain_unexecuted(self):
        probe = [t for t in self.scene["things"] if t["type"] == 9892]
        self.assertEqual([(t["x"], t["y"], t["height"]) for t in probe], [(0, -64, 64)])
        parser = source("src/maploader/udmf.cpp")
        self.assertIn("th->EdNum == 9892", parser)
        self.assertIn("Level->lightProbes.Push(probe)", parser)
        entry = source("src/rendering/hwrenderer/hw_entrypoint.cpp")
        self.assertIn("r_NoInterpolate = true", entry)
        self.assertIn("RenderLightProbe", entry)
        self.reject(lambda s: next(t for t in s["things"] if t["role"] == "probe").update(type=9890), "thing type")
        contract = fixture.observation_contract(self.scene)
        self.assertFalse(contract["executed"])
        self.assertFalse(contract["accepted"])
        self.assertEqual(contract["interpolation"]["probeFractionMustRemain"], 1)
        self.assertIn("probe-faces-0-through-5", contract["requiredRoutes"])

    def test_identity_user_shader_keeps_default_math_and_uses_actual_authoring_producers(self):
        files = fixture.members()
        self.assertEqual(files[fixture.USER_SHADER_MEMBER], source("wadsrc/static/shaders/scene/material_default.glsl").encode())
        self.assertEqual(files["TEXTURES"], b"WallTexture PFVUSR, 128, 128 { Patch STARTAN3, 0, 0 }\n")
        self.assertEqual(files["GLDEFS"], b'material texture PFVUSR\n{\n    shader "shaders/pf020_identity.glsl"\n}\n')
        textures = source("src/common/textures/texturemanager.cpp")
        self.assertIn('LoadTextureDefs(wadnum, "TEXTURES", build)', textures)
        self.assertIn('sc.Compare("walltexture")', textures)
        self.assertIn('build.ParseTexture(sc, ETextureType::Wall, lump)', textures)
        lookup = source("src/common/textures/texturemanager.h")
        self.assertIn('BITFIELD flags=TEXMAN_TryAny', lookup)
        builder = source("src/common/textures/multipatchtexturebuilder.cpp")
        self.assertIn('sc.Compare("Patch")', builder)
        self.assertIn('TexMan.CheckForTexture(buildinfo.Inits[i].TexName.GetChars(), buildinfo.Inits[i].UseType)', builder)
        self.assertIn('buildinfo.Parts[0].TexImage->GetWidth() == buildinfo.Width', builder)
        self.assertIn('AddImageToTexture(buildinfo.Parts[0].TexImage, buildinfo)', builder)
        parser = source("src/r_data/gldefs.cpp")
        self.assertIn('case TAG_MATERIAL:', parser)
        self.assertIn('ParseMaterial(false)', parser)
        self.assertIn('if (sc.Compare("texture")) type = ETextureType::Wall', parser)
        self.assertIn('usershader.shader = sc.String', parser)
        self.assertIn('usershader.shaderType = SHADER_Default', parser)
        self.assertIn('SetShaderIndex(tex, usershaders.Push(usershader) + FIRST_USER_SHADER)', parser)
        material = source("src/common/textures/hw_material.cpp")
        self.assertIn('CVAR(Bool, gl_customshader, true, 0)', material)
        self.assertIn('usershaders[index - FIRST_USER_SHADER].shaderType == mShaderIndex', material)
        self.assertTrue(fixture.SETTINGS["gl_customshader"])
        self.assertIn("FIRST_USER_SHADER = NUM_BUILTIN_SHADERS", source("src/common/textures/textures.h"))
        vk = source("src/common/rendering/vulkan/shaders/vk_shader.cpp")
        self.assertIn('materialBlock = LoadPublicShaderLump(material_lump)', vk)
        self.assertIn('materialBlock.IndexOf("SetupMaterial") < 0', vk)
        canonical = source("wadsrc/static/shaders/scene/material.glsl")
        self.assertIn('material.Base = getTexel(texCoord.st)', canonical)
        self.assertIn('material.Normal = ApplyNormalMap(texCoord.st)', canonical)
        self.assertNotIn("ProcessMaterialLight", files[fixture.USER_SHADER_MEMBER].decode())

    def test_user_material_requires_single_declared_visible_wall_not_authored_presence_only(self):
        wall = next(line for line in self.scene["lines"] if line.get("id") == 104)
        self.assertEqual(self.scene["lines"].index(wall), 3)
        self.assertEqual(tuple(self.scene["vertices"][wall[k]] for k in ("v1", "v2")), ((128, 128), (192, 128)))
        self.assertEqual(self.scene["sides"][wall["sidefront"]], {"sector": 0, "texturemiddle": "PFVUSR"})
        contract = fixture.observation_contract(self.scene)
        self.assertIn("identity-user-material-PFVUSR", contract["requiredRoutes"])
        witness = contract["userShader"]
        self.assertEqual(witness["sourceSha256"], fixture.sha(fixture.members()[fixture.USER_SHADER_MEMBER]))
        self.assertTrue(witness["actualUserShaderDrawRequired"])
        self.assertFalse(witness["executed"])
        self.assertIn("FIRST_USER_SHADER", witness["classification"])
        self.reject(lambda s: s["sides"][wall["sidefront"]].update(texturemiddle="STARTAN3"), "wall demand")
        self.reject(lambda s: next(line for line in s["lines"] if line.get("id") == 104).update(id=105), "wall demand")
        self.reject(lambda s: s["sides"][0].update(texturemiddle="PFVUSR"), "wall demand")

    def test_user_shader_binding_nonidentity_math_missing_source_and_alias_crop_fail(self):
        files = fixture.members()
        changes = ((fixture.USER_SHADER_MEMBER, b"void SetupMaterial(inout Material m) { m.Base = vec4(0); }\n"),
                   ("GLDEFS", files["GLDEFS"].replace(b"PFVUSR", b"STARTAN3")),
                   ("GLDEFS", files["GLDEFS"].replace(b"pf020_identity.glsl", b"absent.glsl")),
                   ("TEXTURES", files["TEXTURES"].replace(b"128, 128", b"64, 128")),
                   ("TEXTURES", files["TEXTURES"].replace(b"STARTAN3, 0, 0", b"STARTAN3, 1, 0")))
        for name, replacement in changes:
            with self.subTest(member=name, payload=replacement), self.assertRaisesRegex(ValueError, "Identity user material"):
                fixture.archive_bytes({**files, name: replacement})
        missing = dict(files)
        del missing[fixture.USER_SHADER_MEMBER]
        with self.assertRaisesRegex(ValueError, "unapproved"):
            fixture.archive_bytes(missing)
        raw = synthetic_iwad().replace(b"STARTAN3", b"ABSENT00")
        with self.assertRaisesRegex(ValueError, "wall texture missing"):
            fixture.stock_assets(raw)
        raw = synthetic_iwad()
        wrong_size = bytearray(raw)
        struct.pack_into("<H", wrong_size, raw.index(b"STARTAN3")+12, 64)
        self.assertNotEqual(fixture.sha(raw), fixture.sha(wrong_size))
        with self.assertRaisesRegex(ValueError, "stock texture extent"):
            fixture.stock_assets(wrong_size)

    def test_eight_main_rotations_pin_stock_paired_frames_not_copied_pixels(self):
        roles = {t["role"]: t for t in self.scene["things"]}
        self.assertEqual([roles[f"rotation-{k}"]["id"] for k in range(1, 9)], list(range(4201, 4209)))
        self.assertEqual(fixture.ROTATIONS[-3:], ("POSSA4A6", "POSSA3A7", "POSSA2A8"))
        sprites = source("src/r_data/sprites.cpp")
        self.assertIn("45.0 / 2 * 9", sprites)
        self.assertIn("rotation = (rotation - 1) * 2", sprites)
        self.assertIn("sprtemp[frame].Texture[rot*2+1] = sprtemp[frame].Texture[rot*2]", sprites)
        actor = source("src/playsim/actor.h")
        self.assertIn("return viewangle - (thisang + SpriteRotation)", actor)
        self.reject(lambda s: next(t for t in s["things"] if t["role"] == "rotation-3").update(angle=0), "rotation witness")

    def test_udmf_rotation_angles_use_actual_integer_parser_not_float_authoring(self):
        parser = source("src/maploader/udmf.cpp")
        self.assertIn("th->angle = (short)CheckInt(key)", parser)
        self.assertTrue(all(type(t["angle"]) is int for t in self.scene["things"]))
        self.reject(lambda s: next(t for t in s["things"] if t["role"] == "rotation-1").update(angle=22.5), "integer degree")

    def test_public_wall_flat_and_explicit_flip_flags_are_real_and_bounded(self):
        script, flags = fixture.zscript(), source("src/scripting/thingdef_data.cpp")
        for flag in ("WALLSPRITE", "FLATSPRITE", "XFLIP", "YFLIP", "INTERPOLATEANGLES"):
            self.assertIn(f"+{flag}", script)
            self.assertIn(f"DEFINE_FLAG(RF, {flag}, AActor, renderflags)", flags)
        self.assertNotIn("+SOLID", script)
        self.assertNotIn("+SHOOTABLE", script)
        self.assertIn("Scale 0.5", script)
        self.reject(lambda s: next(t for t in s["things"] if t["role"] == "wall").update(type=32101), "presentation type")

    def test_interpolation_uses_actual_snapshot_then_moving_api_every_tick(self):
        script = fixture.zscript()
        body = script.split("void PinEndpoints()", 1)[1].split("override void PostBeginPlay", 1)[0]
        sequence = ["angle = 0", "SetOrigin((-32, -48, 8), false)", "SetOrigin((-24, -40, 8), true)", "angle = 22.5"]
        self.assertEqual(sorted(body.index(s) for s in sequence), [body.index(s) for s in sequence])
        self.assertIn("override void Tick() { Super.Tick(); PinEndpoints(); }", script)
        self.assertNotIn("DONTINTERPOLATE", script)
        self.assertNotRegex(script, r"\bPrev\s*=")
        movement = source("src/playsim/p_maputl.cpp")
        method = movement.split("void AActor::SetOrigin", 1)[1].split("\n}", 1)[0]
        self.assertIn("if (!moving) ClearInterpolation();", method)
        snapshot = source("src/playsim/actorinlines.h")
        self.assertIn("Prev = Pos();", snapshot)
        self.assertIn("PrevAngles = Angles;", snapshot)
        actor = source("src/playsim/actor.h")
        self.assertIn("Prev + (ticFrac * (Pos() - Prev))", actor)
        contract = fixture.observation_contract(self.scene)
        self.assertEqual(contract["requestedRenderFraction"], .5)
        self.assertFalse(contract["fractionRequestIsEngineCVar"])
        self.assertTrue(contract["actualStateRequiredForBothBaselineAndCandidate"])
        self.assertEqual(contract["interpolation"]["expectedAtRequestedFraction"], [-28, -44, 8])
        self.assertEqual(contract["interpolation"]["positiveActorDrawContext"], "MainView")

    def test_script_version_and_actual_declared_abi_are_source_linked_not_compiled(self):
        self.assertTrue(fixture.zscript().startswith('version "4.15.1"\n'))
        self.assertTrue(source("wadsrc/static/zscript.txt").startswith('version "4.15.1"'))
        actor = source("wadsrc/static/zscript/actors/actor.zs")
        self.assertIn("native void SetOrigin(vector3 newpos, bool moving)", actor)
        self.assertIn("CameraHeight", actor)
        self.assertIn("override void PostBeginPlay", source("wadsrc/static/zscript/actors/shared/camera.zs"))
        info = fixture.members()["MAPINFO"].decode()
        for number, name in fixture.CLASSES.items():
            self.assertIn(f"{number} = {name}", info)
            self.assertIn(f"class {name} :", fixture.zscript())

    def test_stock_directory_service_checks_missing_and_truncated_inputs(self):
        raw = synthetic_iwad()
        assets = fixture.stock_assets(raw)
        self.assertFalse(assets["copiedIntoPackage"])
        self.assertEqual(assets["pairedFrameFlip"], [False]*5+[True]*3)
        self.assertEqual(set(assets["lumps"]), set(fixture.FLATS+fixture.ROTATIONS))
        self.assertEqual(assets["wallDefinitions"][fixture.USER_STOCK]["extent"], [128, 128])
        for bad in (b"", raw[:11], raw.replace(b"POSSA5", b"BADAA5"), raw.replace(b"STARTAN3", b"BADTEX00")):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                fixture.stock_assets(bad)
        damaged = bytearray(raw)
        struct.pack_into("<I", damaged, 8, len(raw)-1)
        with self.assertRaisesRegex(ValueError, "directory"):
            fixture.stock_assets(bytes(damaged))

    def test_unapproved_assets_nonfinite_things_duplicate_ids_and_injection_fail(self):
        self.reject(lambda s: s["sides"][0].update(texturemiddle="PF113W"), "undeclared")
        self.reject(lambda s: s["things"][1].update(id=4000), "Duplicate")
        self.reject(lambda s: s["things"][1].update(id=4999), "Stable observer")
        self.reject(lambda s: s["things"][1].update(x=float("inf")), "bounded")
        self.reject(lambda s: s["things"][2].update(x=2048), "outside")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            fixture.value_text('A"; thing {')

    def test_preparation_is_fresh_build_only_and_manifest_has_no_native_success(self):
        raw = synthetic_iwad()
        # Temporary build is an isolated authoring service, not a
        # native executable/sibling checkout. No engine, compiler or GPU starts.
        with tempfile.TemporaryDirectory(prefix="pf-view-input-test-") as temp:
            root = Path(temp)
            inputs = root/"inputs"
            inputs.mkdir()
            iwad = inputs/"doom2.wad"
            iwad.write_bytes(raw)
            out = root/"build"/"prepared"
            with patch.object(fixture, "IWAD_SHA256", fixture.sha(raw)), patch.object(fixture, "source_identity", return_value={"test-only": {"rawSha256": "00"}}):
                result = fixture.prepare(out, iwad, root=root)
                self.assertEqual(result["status"], "prepared-unaccepted")
                self.assertFalse(result["gpuExecuted"])
                self.assertEqual(result["mod"]["sha256"], fixture.sha(fixture.archive_bytes(fixture.members())))
                saved = json.loads((out/"manifest.json").read_text())
                self.assertEqual(saved, json.loads(json.dumps(result)))
                fixture.validate_scene(saved["scene"])
                self.assertEqual(saved["preMapCommands"], [f"{k} {str(v).lower()}" for k, v in fixture.SETTINGS.items()])
                with self.assertRaisesRegex(ValueError, "fresh child"):
                    fixture.prepare(out, iwad, root=root)
                with self.assertRaisesRegex(ValueError, "fresh child"):
                    fixture.prepare(root/"elsewhere", iwad, root=root)
                (inputs/"extras.wad").write_bytes(b"unlisted")
                with self.assertRaisesRegex(ValueError, "Adjacent"):
                    fixture.prepare(root/"build"/"second", iwad, root=root)

    def test_resolved_build_junction_cannot_escape_the_source_repository(self):
        # Simulate only OS path resolution, not the generator's own policy.
        # This avoids requiring symlink privileges in Windows hosted CI.
        with tempfile.TemporaryDirectory(prefix="pf-view-junction-test-") as temp:
            base = Path(temp)
            root, outside = base/"source", base/"elsewhere"
            root.mkdir()
            outside.mkdir()
            original = Path.resolve
            def resolve(path, *args, **kwargs):
                return original(outside, *args, **kwargs) if path == root/"build" else original(path, *args, **kwargs)
            with patch.object(Path, "resolve", resolve), self.assertRaisesRegex(ValueError, "escapes"):
                fixture.prepare(outside/"output", base/"unused.wad", root=root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_unpinned_iwad_and_source_changes_fail_before_output_creation(self):
        with tempfile.TemporaryDirectory(prefix="pf-view-source-test-") as temp:
            root = Path(temp)
            (root/"build").mkdir()
            iwad = root/"doom2.wad"
            iwad.write_bytes(synthetic_iwad())
            out = root/"build"/"prepared"
            with self.assertRaisesRegex(ValueError, "pinned"):
                fixture.prepare(out, iwad, root=root)
            self.assertFalse(out.exists())
            with patch.object(fixture, "IWAD_SHA256", fixture.sha(iwad.read_bytes())), patch.object(fixture, "source_identity", side_effect=[{"old": 1}, {"new": 2}]):
                with self.assertRaisesRegex(ValueError, "changed"):
                    fixture.prepare(out, iwad, root=root)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
