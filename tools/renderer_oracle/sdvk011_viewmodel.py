"""Authored live-player viewmodel fixtures and emitted-draw software contracts.

All pixels and map content are generated here; an external legal Doom-family
IWAD supplies engine gameplay definitions. No fixed camera replaces the player.
"""
from __future__ import annotations

import math

try:
    from .common import finite, integer, number, require
except ImportError:
    from common import finite, integer, number, require

CONTRACT = "sdvk-011-viewmodel/v1"


def validate_draw(value):
    require(value.get("contract") == CONTRACT, "Unknown viewmodel contract")
    requested = value.get("requested_mode")
    require(type(requested) is int, "Viewmodel requested mode must be an integer")
    mode = integer(value.get("effective_mode"), "viewmodel effective mode", maximum=2)
    fallback = integer(value.get("fallback_reason"), "viewmodel fallback", maximum=6)
    require((fallback == 0 and requested == mode) or
            (fallback == 1 and requested not in (0, 1, 2) and mode == 0) or
            (requested == 2 and ((fallback in (2, 3, 5) and mode == 0) or
                                 (fallback in (4, 6) and mode == 1))),
            "Viewmodel requested/effective mode and fallback disagree")
    for key in ("world_sample_enabled", "explicit_basis", "relief_enabled", "indexed"):
        require(type(value.get(key)) is bool, "Viewmodel flag missing: " + key)
    model = value.get("model_geometry", False)
    require(type(model) is bool, "Viewmodel geometry flag must be boolean")
    require(value["world_sample_enabled"] is (mode == 2), "Viewmodel world-sample mode disagrees")
    require(value["explicit_basis"] is (mode == 2 and not model), "Viewmodel basis does not match projection policy")
    require(not value["relief_enabled"], "HUD projection cannot claim world sprite relief")
    for key in ("sample", "tangent", "normal"):
        vector = value.get(key)
        require(isinstance(vector, list) and len(vector) == 3 and
                all(type(item) in (int, float) for item in vector), "Invalid viewmodel " + key)
        finite(vector)
    handedness = number(value.get("handedness"), "viewmodel handedness", minimum=-1)
    if mode == 2 and not model:
        tangent, normal = value["tangent"], value["normal"]
        require(abs(sum(x*x for x in tangent) - 1) < 1e-4 and
                abs(sum(x*x for x in normal) - 1) < 1e-4 and
                abs(sum(a*b for a, b in zip(tangent, normal))) < 1e-4 and
                abs(handedness) == 1, "Invalid enhanced viewmodel tangent basis")
    else:
        require((mode == 2 or value["sample"] == [0, 0, 0]) and value["tangent"] == [0, 0, 0] and
                value["normal"] == [0, 0, 0] and handedness == 0,
                "Fallback viewmodel retains enhanced uniforms")
    if mode == 2 and model:
        matrix = value.get("normal_model_matrix")
        require(value.get("basis_source") == "model-world-normal-matrix-and-derivative-tbn"
                and isinstance(matrix, list) and len(matrix) == 16
                and all(type(item) in (int, float) for item in matrix),
                "HUD model has no actual world normal matrix")
        finite(matrix)
        determinant = (matrix[0] * (matrix[5]*matrix[10] - matrix[6]*matrix[9])
                       - matrix[4] * (matrix[1]*matrix[10] - matrix[2]*matrix[9])
                       + matrix[8] * (matrix[1]*matrix[6] - matrix[2]*matrix[5]))
        require(determinant != 0, "HUD model world normal matrix is singular")
    integer(value.get("authored_probe"), "viewmodel authored probe", minimum=-1)
    integer(value.get("runtime_irradiance_index"), "viewmodel runtime probe")
    integer(value.get("probe_epoch"), "viewmodel probe epoch", minimum=1)
    integer(value.get("shader"), "viewmodel shader", minimum=-1)
    integer(value.get("light_index"), "viewmodel light index", minimum=-1)
    integer(value.get("draw_count"), "viewmodel draw count", minimum=1)
    require(isinstance(value.get("material"), str) and value["material"], "Viewmodel material absent")
    require(isinstance(value.get("pipeline"), dict) and value["pipeline"], "Viewmodel pipeline absent")
    require(value.get("uniform_scope") == "emitted-vulkan-draw-after-apply-surface-uniforms",
            "Viewmodel observation is not an actual emitted draw")


def validate_spec(spec):
    require(isinstance(spec, dict) and set(spec) - {"model_geometry"} == {"requested_mode", "effective_mode", "fallback_reason",
            "material", "shader", "probe_required", "dynamic_lights_required"}, "Invalid viewmodel scene assertions")
    require(type(spec["requested_mode"]) is int and spec["requested_mode"] in (0, 1, 2) and
            type(spec["effective_mode"]) is int and spec["effective_mode"] in (0, 1, 2) and
            type(spec["fallback_reason"]) is int and spec["fallback_reason"] in (0, 2, 4),
            "Invalid fixture viewmodel modes")
    model_fallback = spec.get("model_geometry", False) and spec["fallback_reason"] == 4
    require((spec["shader"] in (3, 4) or model_fallback and spec["shader"] == 2)
            and isinstance(spec["material"], str) and spec["material"],
            "Viewmodel fixture needs an authored normal/PBR material")
    require(spec["fallback_reason"] != 4 or model_fallback and spec["requested_mode"] == 2
            and spec["effective_mode"] == 1, "Invalid unsupported-model fallback recipe")
    require(type(spec["probe_required"]) is bool and type(spec["dynamic_lights_required"]) is bool,
            "Viewmodel fixture requirements must be explicit")
    require(type(spec.get("model_geometry", False)) is bool, "Fixture model geometry must be boolean")


def validate_frame(records, spec, camera):
    validate_spec(spec)
    draws = [record["data"] for record in records if record["kind"] == "viewmodel"
             and record["data"].get("material") == spec["material"]]
    require(draws, "Live player weapon did not reach emitted viewmodel path")
    for value in draws:
        validate_draw(value)
        require(value.get("model_geometry", False) is spec.get("model_geometry", False),
                "Live weapon took the wrong card/model geometry path")
        require(all(value[key] == spec[key] for key in
                    ("requested_mode", "effective_mode", "fallback_reason", "shader")),
                "Actual viewmodel mode/material shader differs from fixture")
        if spec.get("model_geometry", False):
            shader = value["pipeline"].get("shader", {})
            require(value["draw_count"] == 36 and value["indexed"] is False
                    and type(shader.get("VertexFormat")) is int and shader["VertexFormat"] > 0,
                    "Fixture HUD box did not submit its actual 36 model vertices")
            if spec["effective_mode"] == 2:
                require(shader.get("ShadeVertex") == 0 and shader.get("LightNoNormals") == 0
                        and shader.get("UseSpriteCenter") == 1 and shader.get("UseLevelMesh") == 0,
                        "HUD model pipeline does not consume its enhanced world sample")
        if spec["effective_mode"] == 2:
            yaw, pitch = math.radians(camera["yaw"]), math.radians(camera["pitch"])
            x, y, z = camera["position"]
            expected = [x + 8 * math.cos(yaw) * math.cos(pitch), z - 8 * math.sin(pitch),
                        y + 8 * math.sin(yaw) * math.cos(pitch)]
            require(all(abs(actual - wanted) < 1e-4 for actual, wanted in zip(value["sample"], expected)),
                    "Viewmodel sample is not camera-forward eight units in shader coordinates")
        if spec["probe_required"]:
            resource = value.get("probe_resource", {})
            require(value["authored_probe"] >= 0 and value["runtime_irradiance_index"] > 0 and
                    resource.get("available") is True and resource.get("index") == value["runtime_irradiance_index"],
                    "Enhanced weapon has no current published environment pair")
        if spec["dynamic_lights_required"]:
            require(value["light_index"] >= 0, "Enhanced weapon has no uploaded local light range")


def authored_members(scene, api):
    native = scene["native"]
    spec = native["state_assertions"]["viewmodel"]
    validate_spec(spec)
    members = api._base_members()
    api._material_layers(members)
    model = api._Map(floor=0, ceiling=160, sky=True)
    model.records["sector"][0]["lightlevel"] = 96
    model.boundary([(-256, -192), (-256, 192), (256, 192), (256, -192)], ["SDVW"] * 4)
    # Keep a real mirror, world sprite, PBR wall and colored local lights in the
    # same ordinary playable room as the live first-person weapon.
    model.records["linedef"][2].update(id=1101, special=182)
    x, y, _ = native["camera"]["position"]
    model.thing(1, x, y, angle=native["camera"]["yaw"], tid=1100)
    model.thing(9892, 32, 0, 64)
    model.thing(9890, 0, 0, angle=0, pitch=45, lm_suncolor=16774336, lm_sunintensity=1, lm_sampledist=64)
    model.thing(9800, 48, -48, 64, tid=1110, arg0=255, arg1=96, arg2=48, arg3=192)
    model.thing(9800, 96, 80, 64, tid=1111, arg0=48, arg1=96, arg2=255, arg3=192)
    yaw = math.radians(native["camera"]["yaw"])
    model.thing(32203, round(x + 96*math.cos(yaw) - 40*math.sin(yaw)),
                round(y + 96*math.sin(yaw) + 40*math.cos(yaw)), tid=1120)
    # One custom fixture weapon uses ordinary selection/ready/fire states. Its
    # StartItem is selected through the normal player weapon setup; no observer
    # callback changes simulation, camera, input or render phase.
    members["ZSCRIPT"] += b'''
class SDVKVMWeapon : Weapon
{
    Default { Weapon.SelectionOrder 1; Weapon.SlotNumber 2; Weapon.Kickback 0; }
    States
    {
    Spawn: SDVU A -1; Stop;
    Ready: SDVU A 1 A_WeaponReady; Loop;
    Deselect: SDVU A 1 A_Lower; Loop;
    Select: SDVU A 1 A_Raise; Loop;
    Fire: SDVU B 3 A_FireBullets(0, 0, 1, 5); SDVU A 3; Goto Ready;
    }
}
class SDVKVMPlayer : DoomPlayer
{
    Default { Player.StartItem "SDVKVMWeapon"; Player.ViewHeight 41; }
    override void GiveDefaultInventory()
    {
        Super.GiveDefaultInventory();
        let weapon = Weapon(FindInventory("SDVKVMWeapon"));
        if (weapon != null) player.ReadyWeapon = player.PendingWeapon = weapon;
    }
}
'''
    for frame, color in (("A", (108, 164, 204, 255)), ("B", (232, 188, 72, 255))):
        # Idle weapon x is zero and GetSpriteRect negates the PNG left offset.
        # Center this 96-wide HUD patch in the 320-wide weapon domain:112..208.
        # Actor-style +48 would instead place half the patch left of the view.
        members[f"sprites/SDVU{frame}0.png"] = api._texture(
            96, 96, color, (200, 86, 52, 255), offset=(-112, -72))
    members["textures/SDVN.png"] = api.png_rgba(16, 16, bytes((207, 91, 220, 255)) * 256)
    material = (api._pbr("SDVUA0", "sprite") if spec["shader"] == 4 else
                'material sprite SDVUA0\n{ normal "SDVN"\n specular "SDVSP"\n}\n')
    members["GLDEFS"] = (material + api._pbr("SDVW") + api._pbr("SDVOA0", "sprite")).encode()
    if spec.get("model_geometry", False):
        # Original rigid box, authored for the inherited OBJ Z realignment and
        # HUD model's 90-degree Y turn. It sits in front/below the live camera.
        members["models/sdvkvm.obj"] = b'''# Original SDVK HUD box; no external model asset.
v 18 -8 -4
v 30 -8 -4
v 30 0 -4
v 18 0 -4
v 18 -8 4
v 30 -8 4
v 30 0 4
v 18 0 4
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 0 -1
vn 0 0 1
vn -1 0 0
vn 1 0 0
vn 0 -1 0
vn 0 1 0
usemtl SDVW
f 1/1/1 4/4/1 3/3/1 2/2/1
f 5/1/2 6/2/2 7/3/2 8/4/2
f 1/1/3 5/2/3 8/3/3 4/4/3
f 2/1/4 3/4/4 7/3/4 6/2/4
f 1/1/5 2/2/5 6/3/5 5/4/5
f 4/1/6 8/2/6 7/3/6 3/4/6
'''
        mirror = -1 if spec["shader"] == 3 else 1
        members["MODELDEF"] = (f'model SDVKVMWeapon {{ Path "models" Model 0 "sdvkvm.obj" Skin 0 "SDVW" '
            f'Scale {mirror} 1 1 FrameIndex SDVU A 0 0 FrameIndex SDVU B 0 0 }}\n').encode()
        model_material = (api._pbr("SDVW") if spec["shader"] == 4 else
                          'material texture SDVW\n{ normal "SDVN"\n specular "SDVSP"\n}\n')
        members["GLDEFS"] = (material + model_material + api._pbr("SDVOA0", "sprite")).encode()
        if spec["fallback_reason"] == 4:
            members["ANIMDEFS"] = b"warp2 texture SDVW 0\n"
    members["textures/SDVSKY.png"] = api._texture(256, 128, (90, 132, 180, 255), (176, 194, 212, 255))
    name = native["map"]
    members["MAPINFO"] = (f'GameInfo {{ PlayerClasses = "SDVKVMPlayer" }}\n'
        f'map {name} "SDVK playable viewmodel" {{ nointermission sky1 = "SDVSKY", 0 }}\n'
        'DoomEdNums { 32203 = SDVKMarker }\n').encode()
    members[f"maps/{name}.wad"] = api.pf_indexed.wad(
        [(name, b""), ("TEXTMAP", model.text().encode()), ("ENDMAP", b"")])
    return members, {"geometry": "authored_udmf", "textures": "generated_rgba_only",
        "native_executed": False, "camera_actor_tid": None, "live_player_camera": True,
        "player_start_world": [x, y], "camera_position_world": native["camera"]["position"],
        "weapon_material": spec["material"], "world_sprite_material": "SDVOA0", "monsters": 0,
        "ordinary_weapon_states": True, "boundary_signed_areas": model.polygon_areas,
        "counts": {kind: len(rows) for kind, rows in model.records.items()}}
