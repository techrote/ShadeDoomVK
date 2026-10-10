#!/usr/bin/env python3
"""Offline *proposed* SDVK-010 draw-record semantic checks, not native observer.

Accepts only already-captured JSON. Never imports a renderer or mutates probes.
Requires one explicit same-driver capture for local validation; native acceptance
requires independent two-process comparison by the eventual renderer oracle.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "sdvk010-actor-probe-observation/v0"
FALLBACK_REASONS = {"missing-sector", "no-authored-probes", "pair-unpublished",
                    "probe-disabled", "reset-cleared", "unencodable",
                    "atlas-unavailable", "unresolved"}
ALLOWED_MODES = {"uniform", "lightmap-gather", "none"}


class InvalidEvidence(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise InvalidEvidence(reason)


def obj(value, label: str) -> dict:
    require(isinstance(value, dict), f"{label}: expected object")
    return value


def integer(value, label: str, lo=0) -> int:
    require(type(value) is int and value >= lo, f"{label}: expected integer >= {lo}")
    return value


def scalar(value, label: str) -> float:
    require(type(value) in (int,float) and math.isfinite(value),f"{label}: nonfinite/non-number")
    return float(value)


def xyz(value, label: str) -> list[float]:
    require(isinstance(value, list) and len(value) == 3, f"{label}: require 3D vector")
    return [scalar(v,label+" component") for v in value]


def unit(value, label: str) -> list[float]:
    v = xyz(value,label)
    l2 = sum(q*q for q in v)
    require(abs(l2 - 1.0) <= 0.005, f"{label}: not a finite unit vector")
    return v


def resource(probe: dict, name: str) -> dict | None:
    value = obj(probe[name],name)
    require(type(value.get("available")) is bool,name+": explicit availability missing")
    if not value["available"]:
        require(value.get("index") is None and value.get("identity") is None and
                value.get("view_type") in ("none","unknown"),
                name+": unavailable resource must not masquerade as a live pair")
        return None
    require(value.get("view_type")=="cube",name+": environment view is not cube")
    idx=integer(value.get("index"),name+".index",1)
    iden=obj(value.get("identity"),name+".identity")
    for key in ("index","generation","epoch","span"):
        integer(iden.get(key),name+".identity."+key,1)
    require(isinstance(iden.get("owner"),str) and bool(iden["owner"]),name+": identity owner missing")
    require(idx==iden["index"],name+": view descriptor and PF-003 index differ")
    return iden


def check_event(evt: dict) -> None:
    evt=obj(evt,"event")
    integer(evt.get("frame"),"frame")
    require(bool(evt.get("draw_id")),"draw ID missing")
    require(bool(evt.get("pipeline_sha")),"pipeline identity missing")
    actor=obj(evt.get("actor"),"actor")
    xyz(actor.get("world_position"),"actor.world_position")
    require(bool(actor.get("semantic_actor_id")) and bool(actor.get("material_id")),"actor/material semantic IDs missing")
    require(type(actor.get("sector_present")) is bool,"sector presence must be explicit")
    authored=actor.get("authored_probe_index")
    if authored is not None:
        integer(authored,"authored probe ordinal")
    if actor.get("selection_basis")=="sector-authored":
        require(actor["sector_present"] and authored is not None,"authored target claimed without actual actor sector")
    ctx=obj(evt.get("context"),"PF-010 context")
    for key in ("view_epoch","view_identity"):
        integer(ctx.get(key),"context."+key,1)
    require(isinstance(ctx.get("map"),str) and bool(ctx["map"]),"map identity missing")
    xyz(ctx.get("displacement"),"portal displacement")
    for key in ("source_portal_group","render_portal_group"):
        if ctx.get(key) is not None:
            integer(ctx[key],key)
    require(type(ctx.get("mirror")) is bool,"mirror parity missing")
    if actor.get("selection_basis")=="sector-authored":
        require(ctx.get("source_portal_group") is not None,"sector actor has no stable source portal group")

    probe=obj(evt.get("probe"),"probe")
    mode=probe.get("mode")
    require(mode in ALLOWED_MODES,"unknown probe sampling mode")
    base=integer(probe.get("runtime_base"),"uniform runtime base")
    cap=integer(probe.get("bindless_capacity"),"capacity",260)
    dyn=integer(probe.get("dynamic_start"),"dynamic start",259)
    for key in ("probe_epoch","lightmap_epoch","levelmesh_epoch","lightmap_probe_epoch"):
        integer(probe.get(key),key,1)
    require(type(probe.get("fallback")) is bool,"fallback flag required")
    reason=probe.get("fallback_reason")
    require(reason=="none" or reason in FALLBACK_REASONS,"unknown fallback reason")
    page=probe.get("probe_map_page")
    if page is not None: integer(page,"probe-map page")
    map_value=probe.get("probe_map_value")
    if map_value is not None:
        integer(map_value,"probe-map texel")
        require(map_value<=65535,"R16_UINT probe map cannot encode descriptor")
    phase=probe.get("publication_phase")
    require(phase in ("initial","cleared","publishing","published","retired"),"invalid publication phase")
    irr=resource(probe,"irradiance")
    pre=resource(probe,"prefilter")
    if mode == "uniform" or mode=="none":
        if base==0:
            require(probe["fallback"] and reason!="none","runtime 0 needs explicit fallback reason")
            require(irr is None and pre is None,"runtime 0 must not dereference cube slots")
            require(probe.get("pair_owner") is None,"fallback cannot claim live descriptor pair")
        else:
            require(not probe["fallback"] and reason=="none","live runtime base mislabeled fallback")
            require(base>=dyn and base+1<cap,"live pair outside dynamic capacity")
            require(irr is not None and pre is not None,"live pair must have two published cube descriptors")
            require(irr["index"]==base and pre["index"]==base+1,"adjacent cube slots violated")
            require(irr["span"]==pre["span"]==2,"PF-003 adjacent pair span not 2")
            for key in ("generation","epoch","owner"):
                require(irr[key]==pre[key],f"PF-003 pair {key} mismatch")
            require(probe.get("pair_owner")==irr["owner"],"pair owner differs from PF-003 owner")
            require(phase not in ("retired","initial"),"live pair consumed in invalid publication phase")
    else:
        # Uniform runtime0 is a *selector* for the per-texel gather branch;
        # it does not mean all four gathered taps are absent. Per-tap native
        # assertions are mandatory post-#7; absent taps/weights prevent an
        # 'accepted' claim. This prepass will not fake per-tap identities.
        require(base==0 and page is not None,"lightmap-gather needs uniform0 and a current page")
        require(map_value is not None,"lightmap-gather must include actual probe-map texel")
        require(irr is None and pre is None,"gather branch uniform0 has no live uniform cube pair")

    pbr=obj(evt.get("pbr"),"pbr")
    require(type(pbr.get("active")) is bool,"PBR mode missing")
    for field in ("metallic","roughness","ao"):
        value=scalar(pbr.get(field),"pbr."+field)
        require(0<=value<=1,"pbr."+field+" outside [0,1]")
    if pbr["active"]:
        n=unit(pbr.get("world_normal"),"N")
        v=unit(pbr.get("world_view"),"V")
        r=unit(pbr.get("world_reflection"),"R")
        dot=sum(a*b for a,b in zip(v,n))
        expected=[2*dot*n[i]-v[i] for i in range(3)]
        require(max(abs(a-b) for a,b in zip(r,expected))<=0.005,"N/V/R cubemap reflection mismatch")
        lod=scalar(pbr.get("prefilter_lod"),"prefilter LOD")
        require(0<=lod<=4 and abs(lod-4*pbr["roughness"])<=0.005,"incorrect roughness LOD")
        require(pbr.get("sampler_direction_space")=="shader-world","cube/sample space ambiguous")
    sun=obj(evt.get("sun"),"sun")
    xyz(sun.get("world_direction"),"sun world direction")
    xyz(sun.get("shader_direction"),"sun shader direction")
    xyz(sun.get("color"),"sun color")
    scalar(sun.get("intensity"),"sun intensity")
    scalar(sun.get("attenuation"),"sun attenuation")
    integer(sun.get("world_query_epoch"),"world Query epoch",1)
    require(sun.get("visibility_mode") in ("cpu-tracesky","shader-trace","lightmap-baked",
            "unoccluded-proxy","none","unknown"),"sun occlusion mode unknown")
    if sun.get("visibility_result") is not None:
        result=scalar(sun["visibility_result"],"sun visibility")
        require(0<=result<=1,"sun visibility outside [0,1]")


def validate(data: dict) -> dict:
    data=obj(data,"observation")
    require(data.get("schema")==SCHEMA,"unknown proposed observer schema")
    require(isinstance(data.get("fixture_id"),str) and bool(data["fixture_id"]),"fixture identity missing")
    require(isinstance(data.get("capture_id"),str) and bool(data["capture_id"]),"capture identity missing")
    events=data.get("events")
    require(isinstance(events,list) and bool(events),"emitted draw list empty")
    # Preserve insertion order; frame-local draws may be emitted in subpass order.
    last_probe_epoch={}
    previous_phase={}
    previous_identity={}
    for e in events:
        check_event(e)
        aid=e["actor"]["semantic_actor_id"]
        identity_key=(e["context"]["map"],aid)
        epoch=e["probe"]["probe_epoch"]
        if identity_key in last_probe_epoch:
            require(epoch>=last_probe_epoch[identity_key],"probe epoch regressed for actor/map")
            was=previous_phase[identity_key]
            now=e["probe"]["publication_phase"]
            if was=="published" and now in ("cleared","publishing"):
                require(epoch>last_probe_epoch[identity_key],
                        "probe content reset without a LightProbeEpoch advance")
            old=previous_identity[identity_key]
            new=e["probe"]["irradiance"]["identity"]
            if old and new and old["index"]==new["index"] and old["owner"]!=new["owner"]:
                require((old["generation"],old["epoch"])!=(new["generation"],new["epoch"]),
                        "reused descriptor owner without PF-003 generation/epoch change")
        last_probe_epoch[identity_key]=epoch
        previous_phase[identity_key]=e["probe"]["publication_phase"]
        previous_identity[identity_key]=e["probe"]["irradiance"]["identity"]
    return {"status":"OFFLINE_SCHEMA_AND_CROSS_FIELD_PASS_NOT_NATIVE_ACCEPTANCE",
            "fixture_id":data["fixture_id"],"capture_id":data["capture_id"],"draws_checked":len(events)}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record",type=Path,help="Already-emitted proposed JSON draw records")
    args=parser.parse_args()
    try:
        result=validate(json.loads(args.record.read_text(encoding="utf-8")))
    except (InvalidEvidence,ValueError,KeyError,TypeError) as exc:
        parser.exit(1,f"FAIL: {exc}\n")
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
