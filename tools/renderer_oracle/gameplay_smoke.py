"""One bounded ordinary-input gameplay room; preparation is never play evidence."""
from __future__ import annotations

import copy
import math
import re
import struct

from .common import finite, integer, require, pin, sha256
from . import images, sdvk011_viewmodel

SCENE = "gameplay-smoke"
MAP_A, MAP_B = "SDVGPA", "SDVGPB"
FRAMES, WARMUP = 128, 32
CHECKPOINTS = (8, 24, 40, 56, 80, 96, 120)
SCHEDULE = (
    (8, MAP_A, "+forward; wait 6; -forward; sdvk_gameplay_pending false"),
    (24, MAP_A, "+right; wait 4; -right; sdvk_gameplay_pending false"),
    (40, MAP_A, "+attack; wait 8; -attack; sdvk_gameplay_pending false"),
    (56, MAP_A, "map " + MAP_B),
    (80, MAP_B, "+attack; wait 8; -attack; sdvk_gameplay_pending false"),
    (96, MAP_B, "map " + MAP_A),
)
WEAPON = {"requested_mode": 2, "effective_mode": 2, "fallback_reason": 0,
          "material": "SDVUA0", "shader": 4, "probe_required": True,
          "dynamic_lights_required": True}
PBR_SEMANTICS = ["albedo", "normal", "metallic", "roughness", "ambient-occlusion"]


def validate_input_log(text):
    rows = re.findall(r"SDVK_GAMEPLAY_INPUT frame=(\d+) map=([A-Z0-9]+) command=([^\r\n]*)", text)
    require([(int(frame), map_name, command) for frame, map_name, command in rows] == list(SCHEDULE),
            "Actual gameplay input log differs from its fixed ordinary-command schedule")


def validate_recipe(scene):
    native = scene.get("native", {})
    require(scene.get("id") == SCENE and native.get("generator") == "gameplay_smoke"
            and native.get("map") == MAP_A and native.get("gameplay_smoke") == {
                "contract": "ordinary-gameplay/v1", "frames": FRAMES, "warmup": WARMUP,
                "maps": [MAP_A, MAP_B, MAP_A], "checkpoints": list(CHECKPOINTS),
                "muzzle_images": ["native.gameplay-fire-a.png", "native.gameplay-fire-b.png"]},
            "Unknown ordinary-gameplay recipe")
    settings = native.get("settings", {})
    require(settings.get("cl_capfps") is True and settings.get("vid_maxfps") == 0
            and settings.get("vid_vsync") is False and settings.get("r_drawplayersprites") is True
            and settings.get("gl_viewmodel_lighting") == 2 and settings.get("gl_spritelight") == 2,
            "Gameplay smoke input/lighting settings differ")
    require(native.get("camera", {}).get("policy") == "ordinary-player-input-observed"
            and native.get("clock", {}).get("timing") == "ordinary_engine_clock",
            "Gameplay smoke cannot use a fixed camera or simulation override")


def authored_members(scene, api):
    validate_recipe(scene)
    reference = copy.deepcopy(scene)
    reference["native"]["state_assertions"]["viewmodel"] = WEAPON
    members, metadata = sdvk011_viewmodel.authored_members(reference, api)
    script = members["ZSCRIPT"].decode()
    script = script.replace("Weapon.Kickback 0;", 'Weapon.Kickback 0; Weapon.AmmoType "Clip"; Weapon.AmmoUse 1;')
    script = script.replace("Fire: SDVU B 3 A_FireBullets(0, 0, 1, 5); SDVU A 3; Goto Ready;",
        "Fire: SDVU B 0 A_Light1; SDVU B 12 A_FireBullets(0, 0, 1, 5); "
        "SDVU A 0 A_Light0; SDVU A 3; Goto Ready;")
    script = script.replace('Player.StartItem "SDVKVMWeapon";',
                            'Player.StartItem "SDVKVMWeapon"; Player.StartItem "Clip", 40;')
    script += '\nclass SDVKClassicMarker : SDVKMarker { States { Spawn: SDVL A -1; Stop; } }\n'
    members["ZSCRIPT"] = script.encode()
    # Firing is an actual enhanced draw too, rather than a material-less flash.
    members["GLDEFS"] += api._pbr("SDVUB0", "sprite").encode()
    members["sprites/SDVLA0.png"] = api._texture(32, 48, (190, 128, 70, 255), (60, 100, 180, 255))
    original = members.pop(f"maps/{MAP_A}.wad")
    _, _, directory = struct.unpack_from("<4sII", original)
    offset, size, name = struct.unpack_from("<II8s", original, directory + 16)
    require(name.rstrip(b"\0") == b"TEXTMAP", "Unexpected authored room WAD")
    text = original[offset:offset+size].decode()
    text += '\nthing { x=96; y=-40; type=32220; id=1121; angle=0; skill1=true; skill2=true; skill3=true; skill4=true; skill5=true; single=true; }\n'
    for map_name in (MAP_A, MAP_B):
        members[f"maps/{map_name}.wad"] = api.pf_indexed.wad(
            [(map_name, b""), ("TEXTMAP", text.encode()), ("ENDMAP", b"")])
    members["MAPINFO"] = ('GameInfo { PlayerClasses = "SDVKVMPlayer" }\n' +
        ''.join(f'map {name} "SDVK ordinary gameplay" {{ nointermission sky1 = "SDVSKY", 0 }}\n'
                for name in (MAP_A, MAP_B)) +
        'DoomEdNums {\n32203 = SDVKMarker\n32220 = SDVKClassicMarker\n}\n').encode()
    metadata.update(ordinary_player_input=True, maps=[MAP_A, MAP_B],
        weapon_fire_evidence="actual Clip.Amount decrease; A_FireBullets consumes ammo",
        muzzle_light="ordinary A_Light1/A_Light0; actual player extralight observed",
        classic_sprite_material="SDVLA0", dynamic_image_repeatability="not claimed")
    return members, metadata


def validate_gameplay(value):
    require(value.get("contract") == "ordinary-gameplay/v1"
            and value.get("producer") == "actual-player-inventory-after-main-view",
            "Unknown gameplay observation")
    require(value.get("map") in (MAP_A, MAP_B), "Gameplay observation has foreign map")
    position = value.get("position")
    require(isinstance(position, list) and len(position) == 3, "Gameplay player position absent")
    finite(position)
    require(all(-240 <= value <= 240 for value in position[:2]) and 0 <= position[2] <= 160,
            "Gameplay player left the authored room")
    require(type(value.get("yaw")) in (int, float), "Gameplay yaw absent")
    finite(value["yaw"])
    integer(value.get("gametic"), "gameplay gametic")
    integer(value.get("ammo"), "actual Clip ammo", maximum=200)
    integer(value.get("extra_light"), "actual weapon light", maximum=20)
    require(value.get("weapon") == "SDVKVMWeapon" and type(value.get("cheats")) is int and value["cheats"] == 0,
            "Gameplay weapon/cheat policy differs")
    for key in ("forward", "right", "attack", "pending_input"):
        require(type(value.get(key)) is bool, "Gameplay input state absent: " + key)


def validate_records(raw, native):
    validate_recipe({"id": SCENE, "native": native})
    require(raw.get("warmup_frames") == WARMUP and raw.get("observed_frames") == FRAMES
            and raw.get("gpu_timing_requested") is False, "Gameplay frame budget differs")
    frames, gameplay, resources = {}, {}, {}
    for row in raw["records"]:
        if row["kind"] == "frame": frames[row["frame"]] = row["data"]
        elif row["kind"] == "gameplay":
            validate_gameplay(row["data"])
            require(row["frame"] not in gameplay, "Duplicate gameplay state")
            gameplay[row["frame"]] = row["data"]
        elif row["kind"] == "resource": resources[row["frame"]] = row["data"]
    require(set(frames) == set(gameplay) == set(resources) == set(range(1, FRAMES+1)),
            "Gameplay lacks actual frame/player/resource coverage")
    for frame, value in gameplay.items():
        require(value["map"] == frames[frame]["map"], "Gameplay player/frame map differs")
        camera = frames[frame]["camera"]
        require(math.dist(camera["position"], value["position"]) < 56,
                "Gameplay camera is not the ordinary player camera")
        selected = [row for row in raw["records"] if row["frame"] == frame]
        draws = [row["data"] for row in selected if row["kind"] == "viewmodel"
                 and row["data"].get("material") in ("SDVUA0", "SDVUB0")]
        require(draws, "Gameplay weapon was not actually drawn")
        actual_camera = dict(position=camera["position"], yaw=camera["angles"][0], pitch=camera["angles"][1])
        for draw in draws:
            from .run import _material_semantics_match
            bound = [row["data"] for row in selected if row["kind"] == "material"
                     and row["data"].get("name") == draw["material"]]
            require(bound and all(_material_semantics_match(value, PBR_SEMANTICS) for value in bound),
                    "Actual ready/firing weapon lacks authored normal/PBR material layers")
            # Map entry can legitimately have no published environment yet.
            # Checkpoints must prove the new owner's current published pair.
            spec = {**WEAPON, "material": draw["material"], "probe_required": frame in CHECKPOINTS or value["extra_light"] > 0}
            sdvk011_viewmodel.validate_frame(selected, spec, actual_camera)
    require(any(row["kind"] == "viewmodel" and row["data"].get("material") == "SDVUB0" for row in raw["records"]),
            "Firing frame never reached the actual authored PBR weapon draw")
    samples = {frame: gameplay[frame] for frame in CHECKPOINTS}
    for frame in (8, 80, 120):
        camera = frames[frame]["camera"]
        require(math.dist(camera["position"], native["camera"]["position"]) < 1e-4
                and abs((camera["angles"][0]-native["camera"]["yaw"]+180) % 360-180) < 1e-6,
                "Initial/rebuilt gameplay camera differs from its authored player start")
    for frame, map_name in ((8, MAP_A), (24, MAP_A), (40, MAP_A), (56, MAP_A), (80, MAP_B), (96, MAP_B), (120, MAP_A)):
        require(samples[frame]["map"] == map_name and not any(samples[frame][key]
            for key in ("forward", "right", "attack", "pending_input")),
            "Gameplay checkpoint reached with wrong map or pending input")
    require(math.dist(samples[8]["position"], samples[24]["position"]) > 8,
            "Ordinary forward input did not move the actual player")
    require(math.dist(frames[8]["camera"]["position"], frames[24]["camera"]["position"]) > 8,
            "Ordinary movement did not move the rendered player camera")
    yaw_delta = (samples[40]["yaw"]-samples[24]["yaw"]+180) % 360-180
    view_delta = (frames[40]["camera"]["angles"][0]-frames[24]["camera"]["angles"][0]+180) % 360-180
    require(abs(yaw_delta) > 1 and abs(view_delta) > 1, "Ordinary turn input did not rotate the actual player/camera")
    require(samples[8]["ammo"] > samples[56]["ammo"] >= 0
            and samples[80]["ammo"] > samples[96]["ammo"] >= 0,
            "Ordinary weapon attack did not consume actual ammo in both maps")
    require(samples[8]["ammo"] == samples[80]["ammo"] == samples[120]["ammo"],
            "Ordinary new-map inventory was not rebuilt")
    owners = [resources[frame]["levelmesh"]["owner"] for frame in (8, 80, 120)]
    require(all(type(owner) is int and owner > 0 for owner in owners) and len(set(owners)) == 3,
            "Ordinary map/resource transitions reused an old LevelMesh owner")
    require(all(any(value["extra_light"] > 0 and value["map"] == map_name for value in gameplay.values()) for map_name in (MAP_A, MAP_B))
            and all(samples[frame]["extra_light"] == 0 for frame in CHECKPOINTS),
            "Actual muzzle light was not observed or did not reset")
    return {"status": "PASS", "movement": True, "turn": True, "ammo_depletion_both_maps": True,
            "fresh_levelmesh_owners": owners, "muzzle_light_reset": True,
            "dynamic_exact_rgb_repeatability": False}


def validate_checkpoints(directory, raw):
    from pathlib import Path
    directory = Path(directory)
    rows = [row for row in raw["records"] if row["kind"] == "gameplay-checkpoint"]
    fixed = [row for row in rows if row["data"].get("phase") == "fixed"]
    muzzle = [row for row in rows if row["data"].get("phase") == "muzzle"]
    maps = {row["frame"]: row["data"]["map"] for row in raw["records"] if row["kind"] == "frame"}
    games = {row["frame"]: row["data"] for row in raw["records"] if row["kind"] == "gameplay"}
    require(len(rows) == 9 and [row["frame"] for row in fixed] == list(CHECKPOINTS)
            and [row["data"].get("map") for row in muzzle] == [MAP_A, MAP_B], "Gameplay checkpoint sequence differs")
    expected = checkpoint_names()
    require({path.name for path in directory.glob("native.gameplay-*.png")} == expected,
            "Gameplay checkpoint image set differs")
    reports = []
    for row in rows:
        value = row["data"]
        name = (f'native.gameplay-{row["frame"]}.png' if value.get("phase") == "fixed" else
                "native.gameplay-fire-a.png" if value.get("map") == MAP_A else "native.gameplay-fire-b.png")
        require(value.get("producer") == "completed-main-view-screenshot" and value.get("image") == name
                and value.get("map") == maps.get(row["frame"]),
                "Gameplay checkpoint was not emitted from its completed view")
        if value.get("phase") == "muzzle":
            game = games[row["frame"]]
            baseline = 8 if value["map"] == MAP_A else 80
            require((40 < row["frame"] < 56 if value["map"] == MAP_A else 80 < row["frame"] < 96)
                    and game["extra_light"] > 0 and game["ammo"] < games[baseline]["ammo"]
                    and any(item["kind"] == "viewmodel" and item["frame"] == row["frame"]
                            and item["data"].get("material") == "SDVUB0" and item["data"].get("shader") == 4
                            for item in raw["records"]), "Muzzle image lacks an actual firing PBR draw/light/ammo decrease")
        path = directory / name
        require(path.is_file() and not path.is_symlink(), "Gameplay checkpoint image absent or linked")
        extent, pixels = images.decode(path)
        require(list(extent) == [640, 480], "Gameplay checkpoint image extent differs")
        reports.append({"frame": row["frame"], "image": pin(path, relative_to=directory),
                        "extent": list(extent), "rgb_sha256": sha256(pixels)})
    changed = images.compare(directory/"native.gameplay-8.png", directory/"native.gameplay-24.png", {"metric": "exact-rgb8"})
    require(changed["passed"] is False, "Moved gameplay checkpoint retained the initial identical image")
    for before, firing in (("native.gameplay-40.png", "native.gameplay-fire-a.png"),
                           ("native.gameplay-80.png", "native.gameplay-fire-b.png")):
        require(images.compare(directory/before, directory/firing, {"metric": "exact-rgb8"})["passed"] is False,
                "Firing/muzzle view retained its identical ready image")
    return {"status": "PASS", "checkpoints": reports, "dynamic_exact_rgb_repeatability": False}


def validate_checkpoint_artifacts(artifacts):
    require({name for name in artifacts if name.startswith("native.gameplay-")} ==
            checkpoint_names(),
            "Original run manifest lacks the exact gameplay checkpoint image pins")


def checkpoint_names():
    return {f"native.gameplay-{frame}.png" for frame in CHECKPOINTS} | {"native.gameplay-fire-a.png", "native.gameplay-fire-b.png"}
