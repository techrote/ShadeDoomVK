#!/usr/bin/env python3
"""Compare one safe CFX diagnostics run with two matched diagnostics-off controls."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(left, right):
    if left.size != right.size:
        return {"same_dimensions": False, "left_size": left.size, "right_size": right.size}
    a = left.convert("RGB").tobytes()
    b = right.convert("RGB").tobytes()
    changed_channels = 0
    changed_pixels = 0
    total_delta = 0
    max_delta = 0
    for i in range(0, len(a), 3):
        deltas = (abs(a[i + j] - b[i + j]) for j in range(3))
        pixel = tuple(deltas)
        changed_pixels += any(pixel)
        changed_channels += sum(value != 0 for value in pixel)
        total_delta += sum(pixel)
        max_delta = max(max_delta, *pixel)
    return {
        "same_dimensions": True,
        "changed_pixels": changed_pixels,
        "changed_channels": changed_channels,
        "max_channel_delta": max_delta,
        "mean_absolute_channel_delta": total_delta / len(a),
    }


def mesh_state(path):
    lines = path.read_text(errors="replace").splitlines()
    return {
        "sha256": digest(path),
        "header": lines[:2],
        "objects": [line for line in lines if line.startswith("o ")],
        "faces": [line for line in lines if line.startswith("f ")],
        "vertex_count": sum(line.startswith("v ") for line in lines),
        "uv_count": sum(line.startswith("vt ") for line in lines),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("off", "capture", "repeat"):
        ap.add_argument(f"--{name}-run", type=Path, required=True)
        ap.add_argument(f"--{name}-image", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    runs = {name: getattr(args, f"{name}_run").resolve()
            for name in ("off", "capture", "repeat")}
    images = {name: getattr(args, f"{name}_image").resolve()
              for name in runs}
    manifests = {name: json.loads((run / "manifest.json").read_text())
                 for name, run in runs.items()}
    pictures = {name: Image.open(path) for name, path in images.items()}
    meshes = {name: mesh_state(run / "work" / "levelmesh.obj")
              for name, run in runs.items()}
    compared = metrics(pictures["off"], pictures["capture"])
    repeat = metrics(pictures["off"], pictures["repeat"])
    identities = {}
    for field, values in {
        "executable": [m["source"]["exe"]["sha256"] for m in manifests.values()],
        "source_patch": [m["source"]["local_patch_sha256"] for m in manifests.values()],
        "iwad": [m["content"][0]["sha256"] for m in manifests.values()],
        "config": [m["run"]["config_sha256"] for m in manifests.values()],
        "map": [m["run"]["map"] for m in manifests.values()],
        "resolution": [m["run"]["actual_resolution"] for m in manifests.values()],
        "exit_zero": [m["status"] == "EXITED" and m["exit_status"] == 0
                      for m in manifests.values()],
        "mesh_header": [m["header"] for m in meshes.values()],
        "mesh_objects": [m["objects"] for m in meshes.values()],
        "mesh_faces": [m["faces"] for m in meshes.values()],
        "mesh_vertex_count": [m["vertex_count"] for m in meshes.values()],
        "mesh_uv_count": [m["uv_count"] for m in meshes.values()],
    }.items():
        identities[field] = all(value == values[0] for value in values)
    result = {
        "schema": "cfx-002-safe-equivalence-v1",
        "runs": {name: {"id": manifests[name]["run_id"], "path": str(runs[name]),
                        "image": str(images[name]),
                        "image_sha256": digest(images[name]),
                        "mesh_sha256": meshes[name]["sha256"]}
                 for name in runs},
        "state_assertions": identities,
        "image_off_vs_capture": compared,
        "image_off_vs_off_repeat": repeat,
        "within_observed_off_repeat_variance": (
            compared["same_dimensions"] and repeat["same_dimensions"] and
            compared["changed_pixels"] <= repeat["changed_pixels"] and
            compared["mean_absolute_channel_delta"] <=
            repeat["mean_absolute_channel_delta"]),
        "mesh_payload_limit": "OBJ vertex/UV payload differs within off/off controls; topology, counts, and objects are asserted, full vertex bytes are not.",
        "scope_limit": "One stationary safe Doom II MAP01 view; this is not proof of all renderer paths.",
    }
    result["pass"] = (all(identities.values()) and
                      result["within_observed_off_repeat_variance"])
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"pass": result["pass"], "out": str(args.out),
                      "off_capture": compared, "off_repeat": repeat}, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
