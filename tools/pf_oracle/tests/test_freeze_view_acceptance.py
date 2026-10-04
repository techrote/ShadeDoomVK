"""CPU-only parser/ownership controls; fabricated interface packets are not GPU evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

HERE = Path(__file__).resolve()
RUNNER = HERE.with_name("run_freeze_view_acceptance.py")
if not RUNNER.is_file():
    RUNNER = HERE.parents[1] / "run_freeze_view_acceptance.py"
SPEC = importlib.util.spec_from_file_location("pf020_view_acceptance_under_test", RUNNER)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def png_rgb_service(path, pixels, width=640, height=480):
    """CPU format service; never presented/rendered GPU pixels."""
    def chunk(kind, body):
        return struct.pack(">I", len(body))+kind+body+struct.pack(">I", zlib.crc32(kind+body)&0xffffffff)
    rows = b"".join(b"\0"+pixels[y*width*3:(y+1)*width*3] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     +chunk(b"IDAT", zlib.compress(rows))+chunk(b"IEND", b""))


def scene_packet(variant="current"):
    rows = []
    def scene(root="main", phase="warmup", depth=0, face=-1, mirror=False):
        key = f"{root}:{face}:0:root" + ("/LineToLine" if depth else "") + ("/Mirror" if depth == 2 else "") + ":group0"
        invocation = rows[-1]["diagnosticRoot"] if depth else len(rows)+1
        parent = rows[-1]["diagnosticIdentity"] if depth else 0
        row = {"phase": phase, "event": "scene", "semanticKey": key, "rootType": root, "face": face, "eye": 0,
               "drawmode": 0, "diagnosticRoot": invocation, "diagnosticIdentity": len(rows)+1,
               "diagnosticParent": parent, "depth": depth, "tic": 1,
               "fraction": 1 if root == "light-probe" else .5, "position": [0, 0, 0], "hardwareAngles": [0, 0, 0],
               "viewpointIndex": 0, "sectorGroup": 0, "lineMirrorFlag": int(mirror), "planeMirrorFlag": 0, "mirrored": mirror,
               "viewMatrix": [1]*16, "projectionMatrix": [1]*16, "cameraPositionUniform": [0]*4,
               "productionContextAvailable": variant == "current", "linePortalAvailable": depth == 1}
        if variant == "current":
            row["productionContext"] = {"identity": len(rows)+1, "depth": depth, "mirrored": mirror,
                                        "epoch": invocation, "rootType": root, "type": "portal" if depth else root, "face": face, "eye": 0,
                                        "parentIdentity": rows[-1]["productionContext"]["identity"] if depth else 0, "lineMirror": mirror, "planeMirror": False,
                                        "postprocessEligible": root == "main" and depth == 0,
                                        "historyEligible": root == "main" and depth == 0}
        if depth == 1:
            row["linePortalSpan"] = [{"linked": True, "destinationLinksBack": True, "originLineIndex": 4, "destinationLineIndex": 9,
                                      "sourceGroup": 0, "destinationGroup": 1, "displacementXY": [1024, 0], "angleDifference": 0}]
        rows.append(row)
        return key
    scene(phase="startup")
    main = scene()
    scene(depth=1)
    scene(depth=2, mirror=True)
    scene("camera-texture")
    for face in range(6): scene("light-probe", "startup", face=face)
    rows += [{"phase": "warmup", "event": "restored", "semanticKey": main, "mirrored": False, "lineMirrorFlag": 0},
             {"phase": "warmup", "event": "postprocess-completed", "semanticKey": main, "rootType": "main", "face": -1}]
    tids = list(range(4201, 4209)) + [4301, 4302, 4303, 4304, 4400]
    for tid in tids:
        row = {"phase": "warmup", "event": "sprite-vertices", "semanticKey": main, "tid": tid,
               "texture": runner.fixture.ROTATIONS[tid-4201] if tid in range(4201, 4209) else "POSSA1",
               "productionSurfaceAvailable": variant == "current", "fraction": .5,
               "verticesXYZUV": [[0, 0, 0, 0, 0], [1, 0, 0, 1, 0], [1, 0, 1, 1, 1], [0, 0, 1, 0, 1]],
               "previousPosition": [-32, -48, 8], "actorPosition": [-24, -40, 8], "interpolatedPosition": [-28, -44, 8],
               "previousAngles": [0, 0, 0], "actorAngles": [22.5, 0, 0], "interpolatedAngles": [11.25, 0, 0], "effectiveSpriteAngles": [11.25, 0, 0]}
        if variant == "current":
            row["productionSurface"] = {"frameMirrored": 4206 <= tid <= 4208, "presentation": 3 if tid == 4301 else 4 if tid == 4302 else 0,
                                         "uvMirrorX": tid == 4303, "uvMirrorY": tid == 4304}
        rows.append(row)
    return {"schema": "pf020-native-scene-observation/v1", "status": "COLLECTED_STATE_ONLY", "error": "", "freezeAccepted": False,
            "imagesCapturedByThisObserver": False, "fixedActorFractionRequested": True, "sceneCalls": 11, "spriteVertexCalls": 13,
            "restorationCalls": 1, "postprocessSceneCalls": 1, "records": rows}


def key_packet(variant="current"):
    scene = {"phase": "warmup", "semanticKey": "main:-1:0:root:group0", "rootType": "main", "face": -1, "eye": 0, "path": ":root", "sectorGroup": 0}
    shader = {key: 0 for key in runner.SHADER_FIELDS if key != "layout"}
    shader.update(EffectState=12, layout={key: 0 for key in runner.LAYOUT_FIELDS})
    pipeline = {key: 0 for key in runner.PIPELINE_FIELDS if key not in ("shader", "style")}
    pipeline.update(shader=shader, style={key: 0 for key in ("BlendOp", "SrcAlpha", "DestAlpha", "Flags")})
    observations = [{"kind": "pipeline", "route": "specialized-main-lookup", "hit": True, "ready": True,
                     "pipeline": pipeline, "pass": {key: 0 for key in runner.PASS_FIELDS}, "workerThread": False, "scene": scene},
                    {"kind": "shader", "route": "specialized-find", "hit": True, "generalized": False, "actualGeneralizedKey": None,
                     "shader": copy.deepcopy(shader), "workerThread": False, "scene": copy.deepcopy(scene)},
                    {"kind": "shader-binary-cache", "actualSourceChecksum": "a"*40, "hit": True, "workerThread": True, "scene": None}]
    return {"schema": "shadedoomvk-pf020-vulkan-observation/v1", "status": "COLLECTED_PENDING_VALIDATION", "error": "", "freezeAccepted": False,
            "performanceMeasured": False, "sourceBranch": "current-named-seams" if variant == "current" else "source-derived-original-seams",
            "productionNamedKeysAvailable": variant == "current", "shaderClassification": {"firstUserShader": 12, "builtinShaderCount": 12},
            "workerState": {"queued": 0, "active": 0, "pendingMainPublications": 0, "failed": 0, "scheduledPrecache": 1,
                            "scheduledPriority": 0, "completedWorkers": 1, "completedMainPublications": 0, "allObservedTasksCompleted": True},
            "keyLookups": [{"count": 1, "observation": row} for row in observations]}


class ViewAcceptanceControls(unittest.TestCase):
    def setUp(self):
        # Inject only the query interface for fake children. These tests do not
        # claim to observe the executing host or a real native renderer token.
        token = lambda pid=None: {"pid": 789 if pid is None else pid, "integrityRid": 8192, "elevated": False, "queryOnly": True}
        self.token_patch = patch.object(runner, "windows_token_info", side_effect=token)
        self.token_patch.start(); self.addCleanup(self.token_patch.stop)

    def reject_scene(self, mutation, text):
        data = scene_packet(); mutation(data)
        with self.assertRaisesRegex(ValueError, text): runner.scene_evidence(data, "current")

    def reject_key(self, mutation, text):
        data = key_packet(); mutation(data)
        with self.assertRaisesRegex(ValueError, text): runner.key_evidence(data, "current")

    def test_current_and_legacy_state_are_validated_without_inventing_metadata(self):
        for variant in ("current", "original-seams"):
            result = runner.scene_evidence(scene_packet(variant), variant)
            self.assertTrue(result["stateOnly"])
            self.assertFalse(result["generalizedAccepted"])
            self.assertEqual(result["legacyMetadataUnavailable"], variant == "original-seams")

    def test_missing_startup_face_and_fraction_sideeffects_fail(self):
        self.reject_scene(lambda d: d["records"].pop(10), "Six natural")
        self.reject_scene(lambda d: d["records"][5].update(fraction=.5), "fraction")
        self.reject_scene(lambda d: d["records"][4].update(fraction=1), "fraction")

    def test_actual_history_ownership_is_main_root_only(self):
        source = (runner.ROOT/"src/rendering/hwrenderer/scene/hw_rendercontext.h").read_text()
        self.assertIn("context.historyEligible = type == HWRenderContextType::MainView;", source)
        self.assertIn("context.historyEligible = false;", source)
        for index, value in ((0, False), (2, True), (4, True), (5, True)):
            self.reject_scene(lambda d: d["records"][index]["productionContext"].update(historyEligible=value), "history")
        self.reject_scene(lambda d: d["records"][0]["productionContext"].pop("historyEligible"), "history")

    def test_context_tokens_epochs_and_retained_parent_ownership_are_actual(self):
        def duplicate_camera_token(data):
            camera = data["records"][4]["productionContext"]
            data["records"][5]["productionContext"].update(epoch=camera["epoch"], identity=camera["identity"])
        self.reject_scene(duplicate_camera_token, "reused.*token")
        self.reject_scene(lambda d: d["records"][2]["productionContext"].update(epoch=99), "same-invocation.*epoch")
        self.reject_scene(lambda d: d["records"][3]["productionContext"].update(parentIdentity=1), "retained parent")
        omitted = scene_packet()
        omitted["records"][3]["diagnosticParent"] = 1  # A deduplicated parent from this invocation is not retained.
        runner.scene_evidence(omitted, "current")

    def test_linked_downgrade_backlink_displacement_and_nested_mirror_fail(self):
        for field, value in (("linked", False), ("destinationLinksBack", False), ("displacementXY", [0, 0]), ("destinationLineIndex", 8)):
            self.reject_scene(lambda d: d["records"][2]["linePortalSpan"][0].update({field: value}), "linked")
        def remove_mirror(data):
            data["records"][3].update(mirrored=False)
            data["records"][3]["productionContext"].update(mirrored=False)
        self.reject_scene(remove_mirror, "depth2")

    def test_nonfinite_degenerate_uv_and_missing_positive_actor_fail(self):
        self.reject_scene(lambda d: d["records"][-1]["verticesXYZUV"][0].__setitem__(0, float("nan")), "Nonfinite")
        self.reject_scene(lambda d: d["records"][-1]["verticesXYZUV"].__setitem__(0, [1, 0, 0, 1, 0]), "Degenerate")
        self.reject_scene(lambda d: d["records"][-1]["verticesXYZUV"][0].__setitem__(3, 2), "out-of-range")
        self.reject_scene(lambda d: d["records"][-1].update(interpolatedPosition=[-24, -40, 8]), "Positive interpolation")
        self.reject_scene(lambda d: d["records"][-1].update(effectiveSpriteAngles=[22.5, 0, 0]), "Effective emitted")
        self.reject_scene(lambda d: d["records"].pop(), "sprite witness")

    def test_rotation_flip_wall_flat_and_main_only_postprocess_are_positive_gates(self):
        self.reject_scene(lambda d: d["records"][13].update(texture="POSSA5"), "eight-rotation")
        self.reject_scene(lambda d: d["records"][18]["productionSurface"].update(frameMirrored=False), "Flip")
        self.reject_scene(lambda d: d["records"][21]["productionSurface"].update(presentation=0), "wall/flat")
        self.reject_scene(lambda d: d["records"][23]["productionSurface"].update(uvMirrorX=False), "X/Y")
        self.reject_scene(lambda d: d["records"][12].update(rootType="camera-texture"), "exclusively")

    def test_actual_ready_user_keys_and_worker_accounting_are_required(self):
        result = runner.key_evidence(key_packet(), "current")
        self.assertEqual(result["readyUserKeys"], 1)
        self.assertFalse(result["generalizedAccepted"])
        self.reject_key(lambda d: d["keyLookups"][0]["observation"].update(ready=False), "ready main")
        self.reject_key(lambda d: d["keyLookups"][1]["observation"].update(hit=False), "matching user ShaderProgram")
        self.reject_key(lambda d: d["keyLookups"][1]["observation"]["shader"].update(FogBeforeLights=1), "matching user ShaderProgram")
        startup = key_packet(); startup["keyLookups"][1]["observation"].update(route="publish-existing-or-insert", hit=False)
        startup["keyLookups"][1]["observation"]["scene"].update(phase="startup", rootType="light-probe", face=0, semanticKey="light-probe:0:0:root:group0")
        runner.key_evidence(startup, "current")
        self.reject_key(lambda d: d["keyLookups"][0]["observation"]["pipeline"]["shader"].update(EffectState=11), "user-material")
        for field in ("queued", "active", "pendingMainPublications", "failed"):
            self.reject_key(lambda d: d["workerState"].update({field: 1}), "not ready")
        self.reject_key(lambda d: d["workerState"].update(completedWorkers=0), "accounting")
        self.reject_key(lambda d: d["workerState"].update(active=False), "types")
        self.reject_key(lambda d: d["keyLookups"][-1]["observation"].update(scene={}), "unsynchronized")
        self.reject_key(lambda d: d["keyLookups"][0]["observation"]["scene"].update(diagnosticIdentity=1), "stable semantic")

    def test_script_is_one_physical_wait_chain_and_dump_order_is_source_grounded(self):
        out = runner.ROOT / "build/parser-service"
        text = runner.script(out)
        self.assertEqual(text.count("\n"), 1)
        self.assertIn("map PFVTEST; wait 350; vid_setsize 640 480; wait 35; pf020view_begin warmup; wait 140", text)
        self.assertLess(text.index("pf020vk_dump"), text.index("pf020view_dump"))
        self.assertTrue(text.endswith("wait 35; quit\n"))
        dispatch = (runner.ROOT / "src/common/console/c_dispatch.cpp").read_text()
        self.assertIn("FExecList::ExecCommands", dispatch)
        frontend = (runner.ROOT / "src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.cpp").read_text()
        self.assertIn('Observer.CompletedKey.clear()', frontend)
        self.assertNotIn("Observer.Records.clear()", frontend)

    def test_prep_path_rejects_overwrite_parent_escape_and_alias(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); (root/"build").mkdir()
            (root/"build/retained").mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"): runner.safe_build(root/"build/retained", fresh=True)
            with self.assertRaisesRegex(ValueError, "Parent traversal"): runner.safe_build(root/"build/../escape")
            with self.assertRaisesRegex(ValueError, "child"): runner.safe_build(root/"source")
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaisesRegex(ValueError, "link"): runner.safe_build(root/"build/new")

    def test_cold_and_warm_only_two_actual_cache_files(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            path = Path(temporary)/"build/isolated"; path.mkdir(parents=True)
            self.assertEqual(runner.cache_inventory(path, cold=True), {})
            for leaf in runner.CACHE_FILES: (path/leaf).write_bytes(leaf.encode())
            self.assertEqual(set(runner.cache_inventory(path)), set(runner.CACHE_FILES))
            with self.assertRaisesRegex(ValueError, "Cold cache"): runner.cache_inventory(path, cold=True)
            (path/"shared-cache.bin").write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "Only the two"): runner.cache_inventory(path)

    def image_service(self, out, variant="current"):
        data = key_packet(variant); data["images"] = []
        for number, semantic in enumerate([f"probe-face-{i}" for i in range(6)] + ["camera-PFVCAM-demanded"]):
            probe = number < 6; width, height = (4, 2) if probe else (128, 128)
            suffix = ".rgba16f" if probe else ".rgba8"
            stem = out/("native-"+semantic)
            pixel = struct.pack("<4e", .1, .2, .3, 1) if probe else bytes([10, 20, 30, 255])
            other = struct.pack("<4e", .4, .2, .3, 1) if probe else bytes([40, 20, 30, 255])
            raw = pixel + other + pixel*(width*height-2); Path(str(stem)+suffix).write_bytes(raw)
            root, face = ("light-probe", number) if probe else ("camera-texture", -1)
            view = {"depth": 0, "tic": 1 if probe else 9, "fraction": 1 if probe else .5,
                    "position": [0, 0, 0], "hardwareAngles": [0, 0, 0], "viewpointIndex": number,
                    "sectorGroup": 0, "lineMirrorFlag": 0, "planeMirrorFlag": 0, "mirrored": False,
                    "viewMatrix": [1]*16, "projectionMatrix": [1]*16, "cameraPositionUniform": [0]*4,
                    "productionContextAvailable": variant == "current"}
            if variant == "current":
                view["productionContext"] = {"type": root, "rootType": root, "epoch": 100+number, "identity": 1,
                                             "parentIdentity": 0, "depth": 0, "face": face, "eye": 0, "lineMirror": False,
                                             "planeMirror": False, "mirrored": False, "postprocessEligible": False, "historyEligible": False}
            scene = {"phase": "startup", "rootType": root, "face": face, "eye": 0,
                     "diagnosticRoot": 100+number, "diagnosticIdentity": 200+number, "diagnosticParent": 0,
                     "path": ":root", "sectorGroup": 0, "semanticKey": f"{root}:{face}:0:root:group0", "completedView": view}
            producer = {"actualRenderAttachmentLayer": number, "actualRenderAttachmentFormat": 97, "actualRenderAttachmentView": number+1} if probe else {"firstUpdate": False, "requestedUpdate": True}
            row = {"semantic": semantic, "scene": scene, "producerState": producer, "sourceImage": number+1, "producerView": number+1,
                   "sourceViewType": 3 if probe else 1, "sampledViewType": 1, "sampledBaseLayer": number if probe else 0, "sampledLayerCount": 1,
                   "mip": 0, "format": 97 if probe else 37, "producerMipCount": 1, "producerLayerCount": 6 if probe else 1,
                   "producerViewBaseLayer": 0, "producerViewLayers": 6 if probe else 1, "width": width, "height": height, "bytes": len(raw),
                   "sourceLayoutBefore": 5, "sourceLayoutAfter": 5, "rowBytes": width*len(pixel), "channels": 4,
                   "file": str(stem)+suffix, "producerRerendered": False, "sourceCopied": False, "sameFormatTexelFetch": True,
                   "normalFenceWaited": True, "allocationInvalidated": True,
                   "sampler": {"minFilter": 0, "magFilter": 0, "maxLod": 0, "anisotropyEnable": False}}
            for field, suffix in (("vertexSPIRV", ".vert.spv"), ("fragmentSPIRV", ".frag.spv"), ("vertexGLSL", ".vert.glsl"), ("fragmentGLSL", ".frag.glsl")):
                payload = struct.pack("<5I", 0x07230203, 0, 0, 0, 0) if suffix.endswith("spv") else b"#version 460\nlayout(set=0,binding=0) uniform sampler2D Source;layout(location=0) out vec4 Result;void main(){Result=texelFetch(Source,ivec2(gl_FragCoord.xy),0);}\n" if field == "fragmentGLSL" else b"service vertex"
                Path(str(stem)+suffix).write_bytes(payload); row[field] = str(stem)+suffix
            data["images"].append(row)
        main_scene = copy.deepcopy(data["images"][-1]["scene"])
        main_scene.update(phase="warmup", rootType="main", semanticKey="main:-1:0:root:group0", diagnosticRoot=300, diagnosticIdentity=400)
        main_scene["completedView"]["tic"] = 25
        if variant == "current":
            main_scene["completedView"]["productionContext"].update(type="main", rootType="main", epoch=300, postprocessEligible=True, historyEligible=True)
        pixels = bytes(range(256))*(640*480*3//256)
        path = out/"native-main-presented.rgb8"; path.write_bytes(pixels)
        png_rgb_service(out/"scene.png", pixels)
        data["mainPresentation"] = {"semantic": "main-presented", "scene": main_scene, "width": 640, "height": 480,
                                    "bytes": len(pixels), "rowBytes": 640*3, "channels": 3, "format": "RGB8", "file": str(path),
                                    "basis": "production-GetScreenshotBuffer-RGB"}
        return data

    def test_raw_image_path_format_actual_layer_demand_fence_and_binary_gates(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary); data = self.image_service(out)
            self.assertEqual(len(runner.image_evidence(data, out)), 7)
            changes = ((0, "sourceCopied", True, "Illegal"), (0, "sampledBaseLayer", 5, "representation"),
                       (0, "normalFenceWaited", False, "Illegal"), (0, "file", str(out/"foreign.rgba16f"), "path"),
                       (0, "format", 37, "format"), (0, "bytes", 1, "row size"))
            for index, field, value, message in changes:
                wrong = copy.deepcopy(data); wrong["images"][index][field] = value
                with self.assertRaisesRegex(ValueError, message): runner.image_evidence(wrong, out)
            wrong = copy.deepcopy(data); wrong["images"][-1]["producerState"]["requestedUpdate"] = False
            with self.assertRaisesRegex(ValueError, "material demand"): runner.image_evidence(wrong, out)
            wrong = copy.deepcopy(data); wrong["images"].pop(0)
            with self.assertRaisesRegex(ValueError, "six-face"): runner.image_evidence(wrong, out)
            Path(data["images"][0]["file"]).write_bytes(struct.pack("<4e", float("inf"), 0, 0, 0)*8)
            with self.assertRaisesRegex(ValueError, "nonfinite"): runner.image_evidence(data, out)

    def test_completed_producer_snapshot_is_required_and_source_variant_is_honest(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            for variant in ("current", "original-seams"):
                data = self.image_service(out, variant)
                result = runner.image_evidence(data, out, variant)
                self.assertEqual(len(result), 7)
                self.assertEqual(result["camera-PFVCAM-demanded"]["completedViewState"]["completedView"]["tic"], 9)
                self.assertNotIn("productionContext", result["probe-face-0"]["completedViewState"]["completedView"])
            data = self.image_service(out)
            for field in ("completedView", "diagnosticRoot", "path"):
                wrong = copy.deepcopy(data); wrong["images"][0]["scene"].pop(field)
                with self.assertRaisesRegex(ValueError, "snapshot field closure"): runner.image_evidence(wrong, out)
            wrong = copy.deepcopy(data); wrong["images"][0]["scene"]["completedView"].pop("tic")
            with self.assertRaisesRegex(ValueError, "snapshot field closure"): runner.image_evidence(wrong, out)
            wrong = copy.deepcopy(data); wrong["images"][0]["scene"]["completedView"]["viewMatrix"][0] = float("nan")
            with self.assertRaisesRegex(ValueError, "Nonfinite"): runner.image_evidence(wrong, out)
            wrong = self.image_service(out, "original-seams")
            wrong["images"][0]["scene"]["completedView"]["productionContext"] = {"type": "invented"}
            with self.assertRaisesRegex(ValueError, "snapshot field closure"): runner.image_evidence(wrong, out, "original-seams")

    def test_completed_producer_actual_root_face_ancestry_fraction_and_context_are_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary); data = self.image_service(out)
            scene = data["images"][0]["scene"]
            mutations = [("scene", "rootType", "main"), ("scene", "face", 1), ("scene", "eye", 1),
                         ("scene", "path", ":root/Mirror"), ("scene", "diagnosticParent", 1),
                         ("view", "depth", 1), ("view", "tic", -1), ("view", "fraction", .5),
                         ("view", "sectorGroup", 1), ("view", "mirrored", True), ("view", "viewpointIndex", False),
                         ("context", "type", "main"), ("context", "rootType", "camera-texture"),
                         ("context", "face", 1), ("context", "eye", 1), ("context", "depth", 1),
                         ("context", "parentIdentity", 1), ("context", "epoch", 0), ("context", "identity", 0),
                         ("context", "historyEligible", True)]
            for kind, field, value in mutations:
                wrong = copy.deepcopy(data); row = wrong["images"][0]["scene"]
                target = row if kind == "scene" else row["completedView"] if kind == "view" else row["completedView"]["productionContext"]
                target[field] = value
                with self.subTest(kind=kind, field=field), self.assertRaisesRegex(ValueError, "Completed producer"):
                    runner.image_evidence(wrong, out)
            duplicate = copy.deepcopy(data)
            duplicate["images"][-1]["scene"]["completedView"]["productionContext"]["epoch"] = scene["completedView"]["productionContext"]["epoch"]
            with self.assertRaisesRegex(ValueError, "reused a current context"): runner.image_evidence(duplicate, out)

    def test_opaque_black_cannot_supply_rgb_evidence_and_uniform_faces_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary); data = self.image_service(out)
            for index in (0, 6):
                row = data["images"][index]; path = Path(row["file"]); original = path.read_bytes()
                pixel = struct.pack("<4e", 0, 0, 0, 1) if index == 0 else bytes([0, 0, 0, 255])
                path.write_bytes(pixel*(row["width"]*row["height"]))
                with self.assertRaisesRegex(ValueError, "positive RGB"): runner.image_evidence(data, out)
                path.write_bytes(original)
            camera = data["images"][-1]; camera_path = Path(camera["file"]); camera_original = camera_path.read_bytes()
            camera_path.write_bytes(bytes([10, 20, 30, 255])*(128*128))
            with self.assertRaisesRegex(ValueError, "camera.*spatial RGB"): runner.image_evidence(data, out)
            camera_path.write_bytes(camera_original)
            for number, row in enumerate(data["images"][:6]):
                Path(row["file"]).write_bytes(struct.pack("<4e", .1 + number*.1, .2, .3, 1)*(row["width"]*row["height"]))
            self.assertEqual(len(runner.image_evidence(data, out)), 7)
            for row in data["images"][:6]:
                Path(row["file"]).write_bytes(struct.pack("<4e", .1, .2, .3, 1)*(row["width"]*row["height"]))
            with self.assertRaisesRegex(ValueError, "six-face.*spatial RGB"): runner.image_evidence(data, out)

    def test_pair_ignores_only_invocation_metadata_but_keeps_semantics_and_exact_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            def packet(variant):
                raw = self.image_service(out, variant)
                presentation = runner.main_presentation_evidence(raw, out, variant)
                return {"state": {"scene": runner.scene_evidence(scene_packet(variant), variant), "keys": runner.key_evidence(key_packet(variant), variant),
                                  "rawImages": runner.image_evidence(raw, out, variant), "mainPresentation": presentation}, "presentation": presentation,
                        "nativeDevice": "same", "settings": "same"}
            a, b = packet("current"), packet("original-seams")
            self.assertEqual(runner.paired_compare(a, b)["status"], "PAIRED_EXACT_MATCH")
            b["state"]["scene"]["records"][0]["diagnosticIdentity"] += 100
            runner.paired_compare(a, b)
            b["state"]["scene"]["records"][0]["tic"] += 10
            with self.assertRaisesRegex(ValueError, "scene/sprite"): runner.paired_compare(a, b)
            b["state"]["scene"]["records"][0]["tic"] -= 10
            b["state"]["scene"]["records"][-1]["verticesXYZUV"][0][0] += .01
            with self.assertRaisesRegex(ValueError, "scene/sprite"): runner.paired_compare(a, b)
            b = packet("original-seams"); b["presentation"]["decodedRgbSha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "decoded main RGB"): runner.paired_compare(a, b)
            b = packet("original-seams"); b["state"]["rawImages"]["probe-face-0"]["artifact"]["path"] = str(out/"changed")
            (out/"changed").write_bytes(b"mismatch")
            with self.assertRaisesRegex(ValueError, "sampled image components"): runner.paired_compare(a, b)

    def test_pair_checks_later_completed_camera_state_instead_of_first_deduplicated_row(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            def packet(variant):
                raw = self.image_service(out, variant)
                presentation = runner.main_presentation_evidence(raw, out, variant)
                return {"state": {"scene": runner.scene_evidence(scene_packet(variant), variant), "keys": runner.key_evidence(key_packet(variant), variant),
                                  "rawImages": runner.image_evidence(raw, out, variant), "mainPresentation": presentation}, "presentation": presentation,
                        "nativeDevice": "same", "settings": "same"}
            a, b = packet("current"), packet("original-seams")
            self.assertEqual(a["state"]["scene"]["records"][4]["tic"], 1)
            self.assertEqual(a["state"]["rawImages"]["camera-PFVCAM-demanded"]["metadata"]["scene"]["completedView"]["tic"], 9)
            self.assertEqual(runner.paired_compare(a, b)["status"], "PAIRED_EXACT_MATCH")
            for field, value in (("tic", 10), ("position", [0, 1, 0]), ("hardwareAngles", [1, 0, 0]),
                                 ("viewMatrix", [2]*16), ("projectionMatrix", [3]*16), ("cameraPositionUniform", [1]*4)):
                changed = copy.deepcopy(b)
                changed["state"]["rawImages"]["camera-PFVCAM-demanded"]["metadata"]["scene"]["completedView"][field] = value
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "completed producer tic/fraction/view state"):
                    runner.paired_compare(a, changed)
            changed = copy.deepcopy(b)
            changed["state"]["rawImages"]["camera-PFVCAM-demanded"]["metadata"]["scene"]["completedView"]["fraction"] = 1
            with self.assertRaisesRegex(ValueError, "actual fraction"): runner.paired_compare(a, changed)
            for image in b["state"]["rawImages"].values():
                image["metadata"]["scene"]["diagnosticIdentity"] += 10000
                image["metadata"]["scene"]["diagnosticRoot"] += 10000
            runner.paired_compare(a, b)  # Structural invocation IDs do not become semantic state.

    def test_actual_main_presented_snapshot_raw_rgb_and_decoded_png_are_one_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            for variant in ("current", "original-seams"):
                raw = self.image_service(out, variant)
                result = runner.main_presentation_evidence(raw, out, variant)
                self.assertEqual(result["decodedBytes"], 640*480*3)
                self.assertEqual(result["completedViewState"]["completedView"]["tic"], 25)
            raw = self.image_service(out)
            mutations = [lambda d: d.pop("mainPresentation"),
                         lambda d: d["mainPresentation"]["scene"].pop("completedView"),
                         lambda d: d["mainPresentation"]["scene"].update(rootType="camera-texture"),
                         lambda d: d["mainPresentation"]["scene"].update(phase="startup"),
                         lambda d: d["mainPresentation"]["scene"]["completedView"]["productionContext"].update(historyEligible=False),
                         lambda d: d["mainPresentation"].update(basis="assumed-next-frame"),
                         lambda d: d["mainPresentation"].update(rowBytes=1)]
            for mutation in mutations:
                wrong = copy.deepcopy(raw); mutation(wrong)
                with self.assertRaises(ValueError): runner.main_presentation_evidence(wrong, out, "current")
            path = Path(raw["mainPresentation"]["file"]); original = path.read_bytes()
            changed = bytearray(original); changed[0] ^= 1; path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "PNG differs.*presented RGB"): runner.main_presentation_evidence(raw, out, "current")
            path.write_bytes(original)
            png_rgb_service(out/"scene.png", bytes(changed))
            with self.assertRaisesRegex(ValueError, "PNG differs.*presented RGB"): runner.main_presentation_evidence(raw, out, "current")

    def test_pair_keeps_actual_main_presented_tic_matrix_and_missing_snapshot_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            def packet(variant):
                raw = self.image_service(out, variant); presentation = runner.main_presentation_evidence(raw, out, variant)
                return {"state": {"scene": runner.scene_evidence(scene_packet(variant), variant), "keys": runner.key_evidence(key_packet(variant), variant),
                                  "rawImages": runner.image_evidence(raw, out, variant), "mainPresentation": presentation},
                        "presentation": presentation, "nativeDevice": "same", "settings": "same"}
            a, b = packet("current"), packet("original-seams")
            runner.paired_compare(a, b)
            for field, value in (("tic", 26), ("viewMatrix", [2]*16)):
                changed = copy.deepcopy(b)
                changed["state"]["mainPresentation"]["metadata"]["scene"]["completedView"][field] = value
                with self.assertRaisesRegex(ValueError, "actual main presented tic/fraction/view state"):
                    runner.paired_compare(a, changed)
            changed = copy.deepcopy(b); changed["state"].pop("mainPresentation")
            with self.assertRaisesRegex(ValueError, "main presentation snapshot missing"): runner.paired_compare(a, changed)

    def test_real_generator_manifest_json_roundtrip_preserves_strict_authored_values(self):
        # Run the actual preparation/JSON writer on the existing bounded stock
        # directory service. This is authored filesystem evidence, never native content.
        path = runner.ROOT/"tools/pf_oracle/tests/test_freeze_view_fixture.py"
        spec = importlib.util.spec_from_file_location("view_authoring_asset_service", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        raw = module.synthetic_iwad()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs = root/"inputs"; inputs.mkdir()
            iwad = inputs/"doom2.wad"; iwad.write_bytes(raw)
            output = root/"build/prepared"
            with patch.object(runner.fixture, "IWAD_SHA256", runner.fixture.sha(raw)), patch.object(runner.fixture, "source_identity", return_value={"test-only": {"rawSha256": "00"}}):
                authored = runner.fixture.prepare(output, iwad, root=root)
                manifest = output/"manifest.json"
                saved = runner.read_json(manifest)
                self.assertNotEqual(saved["scene"], authored["scene"])
                self.assertEqual(saved["scene"], runner.json_projection(authored["scene"]))
                data, _ = runner.fixture_identity(manifest)
                self.assertEqual(data, saved)
                saved["scene"]["vertices"][0][0] += 1
                runner.save(manifest, saved)
                with self.assertRaisesRegex(ValueError, "Authored settings/scene/observation contract"):
                    runner.fixture_identity(manifest)
        with self.assertRaises(ValueError): runner.json_projection({"invalid": float("nan")})

    def test_silent_static_seed_arguments_match_actual_source_and_cannot_be_mutated(self):
        source = (runner.ROOT/"src/d_main.cpp").read_text()
        self.assertIn('Args->CheckValue("-rngseed")', source)
        self.assertIn('rngseed = staticrngseed = atoi(v);', source)
        self.assertIn('D_DoomInit: Static RNGseed %d set.', source)
        for flag, path in (("-nosound", "src/sound/s_doomsound.cpp"), ("-nojoy", "src/common/platform/win32/i_xinput.cpp")):
            self.assertIn(f'Args->CheckParm("{flag}")', (runner.ROOT/path).read_text())
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); receipt, snapshot = self.prepared_service(root)
            receipt["children"][0]["argv"][receipt["children"][0]["argv"].index("-rngseed")+1] = "54321"
            with patch.object(runner, "snapshot", return_value=snapshot), patch.object(runner.subprocess, "Popen") as process:
                with self.assertRaisesRegex(ValueError, "paths/argv"): runner.launch(receipt)
                process.assert_not_called()

    def test_partial_output_hash_failure_retains_fail_and_other_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary); (out/"a").write_bytes(b"a"); (out/"b").write_bytes(b"b")
            original = runner.identity
            def bad(path):
                if Path(path).name == "b": raise PermissionError("injected")
                return original(path)
            receipt = {"status": "PASS"}
            with patch.object(runner, "identity", side_effect=bad): runner.retained_inventory(out, receipt)
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(len(receipt["outputs"]), 1)
            self.assertIn("injected", receipt["outputIdentityErrors"][0]["error"])

    def test_actual_cache_shutdown_event_hashes_and_warm_loading_are_required(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); cache = root/"build/cache"; out = root/"build/child"
            cache.mkdir(parents=True); out.mkdir()
            for leaf in runner.CACHE_FILES: (cache/leaf).write_bytes(b"interface cache")
            before = runner.cache_inventory(cache)
            data = key_packet(); rows = []
            for kind, leaf, load_stage in (("shader", runner.CACHE_FILES[0], "after-load-return"), ("pipeline", runner.CACHE_FILES[1], "after-create")):
                for stage in ("before-load", load_stage, "after-save-close"):
                    rows.append({"sequence": len(rows)+1, "cache": kind, "stage": stage, "operationCompleted": stage != "before-load", "count": 3,
                                 "path": str(cache/leaf), "file": {"exists": True, "bytes": before[leaf]["bytes"], "sha1": before[leaf]["sha1"]}})
            path = out/"native.cache-events.jsonl"
            data.update(cacheShutdownEvents=str(path), cacheEventsAtDump=rows[:2])
            path.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
            child = {"directory": str(out), "cache": str(cache), "cacheState": "warm"}
            self.assertTrue(runner.cache_evidence(data, child, before)["actualWarmLoad"])
            rows[-1]["operationCompleted"] = False
            path.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
            with self.assertRaisesRegex(ValueError, "incomplete"): runner.cache_evidence(data, child, before)
            rows[-1]["operationCompleted"] = True; rows[-1]["file"]["sha1"] = "wrong"
            path.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
            with self.assertRaisesRegex(ValueError, "hash differs"): runner.cache_evidence(data, child, before)

    def prepared_service(self, root):
        (root/"build").mkdir()
        cfg = root/"build/config.ini"; cfg.write_text(runner.fixture.configuration())
        snapshot = {"inputs": {"config": runner.identity(cfg), "iwad": {"path": str(root/"Doom2.wad")}, "mod": {"path": str(root/"fixture.pk3")}},
                    "variants": {v: {"build": {"vkdoom.exe": {"path": str(root/v/"vkdoom.exe")}}} for v in ("current", "original-seams")}}
        with patch.object(runner, "snapshot", return_value=snapshot):
            receipt = runner.prepare(root/"fixture.json", root/"derivation.json", {v: root/v/"candidate.json" for v in snapshot["variants"]},
                                     root/"layers", root/"build/packet", "core")
        return receipt, snapshot

    def test_preparation_is_fresh_serial_preregistration_and_never_launches(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)), patch.object(runner.subprocess, "Popen") as child:
            root = Path(temporary); receipt, _ = self.prepared_service(root)
            self.assertEqual(receipt["status"], "PREPARED")
            self.assertEqual([(r["variant"], r["cacheState"]) for r in receipt["children"]], list(runner.ORDER))
            self.assertFalse(receipt["rendererStarted"])
            self.assertFalse(receipt["gpuExecuted"])
            self.assertEqual(receipt["gpuExecutionStatus"], "NOT_STARTED")
            self.assertFalse(receipt["freezeAccepted"])
            self.assertFalse(any(Path(c["cache"]).exists() for c in receipt["children"]))
            for packet in receipt["children"]:
                self.assertEqual(packet["argv"][packet["argv"].index("-pf020viewfraction")+1], "0.5")
                self.assertIn("-noautoload", packet["argv"])
                self.assertIn("-noautoexec", packet["argv"])
                self.assertEqual(packet["argv"].count("-nosound"), 1)
                self.assertEqual(packet["argv"].count("-nojoy"), 1)
                self.assertEqual(packet["argv"].count("-rngseed"), 1)
                self.assertEqual(packet["argv"][packet["argv"].index("-rngseed")+1], "12345")
            child.assert_not_called()

    def test_mutated_child_argv_is_rejected_before_process_even_if_receipt_rehashed(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); receipt, snapshot = self.prepared_service(root)
            receipt["children"][0]["argv"].append("+dangerous")
            with patch.object(runner, "snapshot", return_value=snapshot), patch.object(runner.subprocess, "Popen") as process:
                with self.assertRaisesRegex(ValueError, "paths/argv"): runner.launch(receipt)
                process.assert_not_called()

    def test_post_popen_save_failure_kills_only_owned_child_and_retains_final_fail(self):
        class FakeChild:
            pid = 123
            def __init__(self): self.code = None; self.kills = 0; self.waits = 0
            def poll(self): return self.code
            def kill(self): self.kills += 1; self.code = -1
            def wait(self, timeout): self.waits += 1; return self.code
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); receipt, snapshot = self.prepared_service(root)
            original_save = runner.save; saves = []
            def failing_save(path, data):
                saves.append(data["status"])
                if len(saves) == 3: raise PermissionError("injected after Popen")
                original_save(path, data)
            child = FakeChild()
            with patch.object(runner, "snapshot", return_value=snapshot), patch.object(runner, "save", side_effect=failing_save):
                result = runner.launch(receipt, popen=lambda *a, **k: child)
            self.assertEqual(result, 1)
            self.assertEqual((child.kills, child.waits), (1, 1))
            final = runner.read_json(root/"build/packet/receipt.json")
            self.assertEqual(final["status"], "FAIL")
            self.assertIn("injected after Popen", final["error"])
            self.assertEqual(sum(c.get("rendererStarted", False) for c in final["children"]), 1)

    def test_coordinator_medium_unelevated_proof_is_required_before_any_child(self):
        for rid, elevated in ((8192, True), (4096, False), (12288, False)):
            with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
                root = Path(temporary); receipt, snapshot = self.prepared_service(root)
                token = {"pid": 789, "integrityRid": rid, "elevated": elevated, "queryOnly": True}
                with patch.object(runner, "snapshot", return_value=snapshot), patch.object(runner.subprocess, "Popen") as process:
                    self.assertEqual(runner.launch(receipt, token_query=lambda pid=None: token), 1)
                    process.assert_not_called()
                final = runner.read_json(root/"build/packet/receipt.json")
                self.assertEqual(final["status"], "FAIL")
                self.assertFalse(final["rendererStarted"])
                self.assertIn("Coordinator requires actual medium", final["error"])
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); receipt, snapshot = self.prepared_service(root)
            def denied(pid=None):
                error = PermissionError("injected coordinator token denial"); error.winerror = 5; raise error
            with patch.object(runner, "snapshot", return_value=snapshot), patch.object(runner.subprocess, "Popen") as process:
                self.assertEqual(runner.launch(receipt, token_query=denied), 1)
                process.assert_not_called()
            final = runner.read_json(root/"build/packet/receipt.json")
            self.assertEqual(final["coordinatorTokenQueryError"]["winerror"], 5)
            self.assertFalse(final["rendererStarted"])

    def test_native_elevated_or_failed_query_stays_inside_owned_child_cleanup(self):
        class FakeChild:
            pid = 123
            def __init__(self): self.code = None; self.kills = 0; self.waits = 0
            def poll(self): return self.code
            def kill(self): self.kills += 1; self.code = -1
            def wait(self, timeout): self.waits += 1; return self.code
        for denied in (False, True):
            with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
                root = Path(temporary); receipt, snapshot = self.prepared_service(root)
                child = FakeChild(); queried = []
                def query(pid=None):
                    queried.append(pid)
                    if pid is not None and denied:
                        error = PermissionError("injected own child token denial"); error.winerror = 5; raise error
                    return {"pid": 789 if pid is None else pid, "integrityRid": 8192, "elevated": pid is not None, "queryOnly": True}
                with patch.object(runner, "snapshot", return_value=snapshot):
                    self.assertEqual(runner.launch(receipt, popen=lambda *a, **k: child, token_query=query), 1)
                self.assertEqual(queried, [None, 123])
                self.assertEqual((child.kills, child.waits), (1, 1))
                final = runner.read_json(root/"build/packet/receipt.json")
                self.assertEqual(final["status"], "FAIL")
                self.assertTrue(final["rendererStarted"])
                self.assertFalse(final["gpuExecuted"])
                self.assertEqual(sum(c.get("rendererStarted", False) for c in final["children"]), 1)
                self.assertEqual(final["coordinatorToken"]["integrityRid"], 8192)
                if denied:
                    self.assertEqual(final["children"][0]["nativeTokenQueryError"]["winerror"], 5)
                    self.assertEqual(final["winerror"], 5)
                else:
                    self.assertIn("Own native child requires actual medium", final["error"])
                    self.assertTrue(final["children"][0]["nativeToken"]["elevated"])

    def test_own_child_watchdog_is_bounded_and_stops_serial_chain(self):
        class FakeChild:
            pid = 321
            def __init__(self): self.code = None; self.kills = 0
            def poll(self): return self.code
            def kill(self): self.kills += 1; self.code = -1
            def wait(self, timeout): return self.code
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); receipt, snapshot = self.prepared_service(root)
            child = FakeChild(); calls = []
            def create(*a, **k): calls.append((a, k)); return child
            times = iter([0, runner.WATCHDOG_SECONDS+1])
            with patch.object(runner, "snapshot", return_value=snapshot): result = runner.launch(receipt, popen=create, clock=lambda: next(times))
            self.assertEqual(result, 1)
            self.assertEqual(child.kills, 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1]["cwd"], root)
            self.assertIn("watchdog", receipt["error"])

    def test_launch_rejects_edited_preregistration_without_starting_child(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); (root/"build").mkdir()
            receipt = {"schema": runner.SCHEMA, "status": "PREPARED", "rendererStarted": False,
                       "cwd": str(root), "output": str(root/"build/new"), "paths": {}, "mode": "core", "watchdogSeconds": 90}
            with patch.object(runner.subprocess, "Popen") as process:
                with self.assertRaisesRegex(ValueError, "Preregistered"): runner.launch(receipt)
                process.assert_not_called()

    def build_service(self, root):
        """Filesystem/compiler-receipt service only; no compiler or actual Git/native qualification."""
        export = root/"build/export/current"; export.mkdir(parents=True)
        rows, source_files, entries = [], {}, []
        for index in range(100):
            name = f"src/service{index}.cpp"; raw = f"// source {index}\n".encode()
            for path in (root/name, export/name):
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            blob = runner.derive.git_blob_id(raw)
            rows.append({"path": name, "mode": "100644", "bytes": len(raw), "sha256": runner.sha(raw), "git_blob": blob})
            source_files[name] = {"bytes": len(raw), "raw_sha256": runner.sha(raw), "git_blob": blob}
            entries.append((name, "100644", blob))
        authentic = {"commit": "1"*40, "git_tree": "2"*40, "historical": [], "changed_paths": [], "compile_definitions": {}, "preserved": {}}
        report = {**authentic, "schema": runner.derive.SCHEMA, "status": "PASS", "export_byte_verified": True,
                  "changed_path_allowlist_verified": True, "native_acceptance": False, "native_executed": False,
                  "closure": {"current": {"files": rows, "file_count": len(rows), "sha256": runner.derive.closure_digest(rows)}}}
        derivation = export.parent/"derivation.json"; runner.save(derivation, report)
        logs = root/"build/logs"; logs.mkdir()
        steps = {}
        for step in ("configure", "build"):
            path = logs/(step+".log"); path.write_bytes((step+" service\n").encode())
            steps[step] = {"exit": 0, "log": str(path.relative_to(root)), "sha256": runner.identity(path)["sha256"]}
        stage, built = root/"build/stage", root/"build/built"; stage.mkdir(); built.mkdir()
        artifacts = []
        for name in sorted(runner.ARTIFACT_NAMES):
            source, target = built/name, stage/name
            raw = name.encode(); source.write_bytes(raw); target.write_bytes(raw)
            artifacts.append({**runner.identity(target), "source": str(source)})
        data = {"schema": "pf020-source-derived-view-build/v1", "status": "BUILD_PASS_STAGED", "variant": "current",
                "source_head": authentic["commit"], "source_directory": str(export), "derivation_sha256": runner.identity(derivation)["sha256"],
                "source_files": source_files, "source_unchanged": True, "diagnostic_only": True, "freeze_accepted": False,
                "renderer_started": False, "gpu_executed": False, "steps": steps, "artifacts": artifacts,
                "commands": {"configure": ["cmake-service", "-S", str(export), "-B", str(built), "-G", "Visual Studio 17 2022", "-A", "x64", "-DHAVE_VULKAN=ON", "-DPF020_ORIGINAL_SEAMS=OFF"],
                             "build": ["cmake-service", "--build", str(built), "--config", "RelWithDebInfo"]}}
        candidate, native = stage/"candidate.json", logs/"receipt.json"
        def write(data):
            original = {k: v for k, v in data.items() if k not in ("native_build_receipt", "native_build_receipt_sha256", "limitations")}
            runner.save(native, original)
            data.update(native_build_receipt=str(native), native_build_receipt_sha256=runner.identity(native)["sha256"], limitations=[])
            runner.save(candidate, data)
        write(data)
        return candidate, derivation, data, authentic, entries, write

    def test_build_attestation_rehashes_full_export_committed_membership_and_eight_counterparts(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); candidate, derivation, data, authentic, entries, write = self.build_service(root)
            with patch.object(runner.derive, "derive_plan", return_value=({}, authentic)), patch.object(runner.derive, "tree_entries", return_value=entries):
                result = runner.build_identity(candidate, "current", derivation)
                self.assertEqual(result["sourceFiles"], 100)
                self.assertEqual(len(result["build"]), 8)
                extra = candidate.parent/"unlisted.dll"; extra.write_bytes(b"bad")
                with self.assertRaisesRegex(ValueError, "Unlisted staged"): runner.build_identity(candidate, "current", derivation)
                extra.unlink()
                source = Path(data["artifacts"][0]["source"]); original = source.read_bytes(); source.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "build counterpart"): runner.build_identity(candidate, "current", derivation)
                source.write_bytes(original)
                altered = Path(data["source_directory"])/"src/service0.cpp"; old = altered.read_bytes(); altered.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Export source changed"): runner.build_identity(candidate, "current", derivation)
                altered.write_bytes(old)
                wrong = copy.deepcopy(entries); wrong[0] = (wrong[0][0], wrong[0][1], "a"*40)
                with patch.object(runner.derive, "tree_entries", return_value=wrong):
                    with self.assertRaisesRegex(ValueError, "committed tree"): runner.build_identity(candidate, "current", derivation)
                mutated = copy.deepcopy(data); mutated["artifacts"].pop(); write(mutated)
                with self.assertRaisesRegex(ValueError, "eight native"): runner.build_identity(candidate, "current", derivation)

    def test_prepare_failure_preserves_fail_receipt_and_never_launches(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); (root/"build").mkdir()
            cfg = root/"build/input.ini"; cfg.write_text(runner.fixture.configuration())
            snapshot = {"inputs": {"config": runner.identity(cfg)}}
            with patch.object(runner, "snapshot", return_value=snapshot), patch.object(runner, "script", side_effect=ValueError("injected preparation")), patch.object(runner.subprocess, "Popen") as process:
                with self.assertRaisesRegex(ValueError, "injected preparation"):
                    runner.prepare(root/"fixture", root/"derivation", {}, root/"layer", root/"build/attempt", "core")
                process.assert_not_called()
            receipt = runner.read_json(root/"build/attempt/receipt.json")
            self.assertEqual(receipt["status"], "FAIL")
            self.assertFalse(receipt["rendererStarted"])
            self.assertIn("injected preparation", receipt["preparationError"])


if __name__ == "__main__":
    unittest.main()
