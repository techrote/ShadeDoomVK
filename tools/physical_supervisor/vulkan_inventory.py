"""Static native64 registry/JSON/file inspection. Never load Vulkan or a DLL.

Registrations describe discoverable candidates, not actual loader selection.
Legacy Khronos keys and device-specific registrations are independent sources.
"""
from pathlib import Path

from .common import (CONTROL_VIDEO, DISPLAY_CLASS, linklike, normalized, pin,
                     read_json, require, verify_pin)


def registered_manifests(registry):
    """Collect enabled native64 registrations from the supplied value snapshot."""
    result = {}
    legacy = "software\\khronos\\vulkan\\"
    device_names = {"vulkandrivername", "vulkanimplicitlayers", "vulkanexplicitlayers"}
    for row in registry:
        if not row["present"]:
            continue
        key = row["key"].casefold()
        for value in row["values"]:
            paths = []
            if key in {legacy + name for name in ("drivers", "implicitlayers", "explicitlayers")}:
                require(value["type"] == 4 and type(value["value"]) is int,
                        "Vulkan registry manifest enable value must be DWORD")
                if value["value"] == 0:
                    paths = [value["name"]]
            elif (key.startswith(DISPLAY_CLASS.casefold() + "\\") or
                  key.startswith(CONTROL_VIDEO.casefold() + "\\")) and value["name"].casefold() in device_names:
                require(value["type"] in (1, 7), "Device Vulkan manifest must be REG_SZ or REG_MULTI_SZ")
                paths = value["value"] if value["type"] == 7 else [value["value"]]
                require(isinstance(paths, list), "Device Vulkan manifest list is malformed")
            for path in paths:
                require(isinstance(path, str) and Path(path).is_absolute(), "Manifest path must be absolute")
                identity = normalized(path)
                entry = result.setdefault(identity, {"path": path, "registrations": []})
                entry["registrations"].append({"hive": row["hive"], "key": row["key"], "value": value["name"]})
    return [result[key] for key in sorted(result)]


def inspect_registered_manifests(registry):
    """Hash static manifests/dependencies and discover their environment controls."""
    result = []
    for entry in registered_manifests(registry):
        path = Path(entry["path"])
        require(not any(linklike(part) for part in (path, *path.parents)), "Manifest path is a link/junction")
        manifest_pin = pin(path)
        document = read_json(path)
        require(isinstance(document, dict), "Registered manifest must be a JSON object")
        declarations = []
        if "ICD" in document:
            declarations.append(document["ICD"])
        if "layer" in document:
            declarations.append(document["layer"])
        if "layers" in document:
            require(isinstance(document["layers"], list), "Manifest layers must be an array")
            declarations.extend(document["layers"])
        require(declarations, "Registered manifest has no ICD/layer declaration")
        libraries, environment_keys = {}, set()
        for declaration in declarations:
            require(isinstance(declaration, dict), "Invalid manifest declaration")
            library = declaration.get("library_path")
            require(isinstance(library, str) and library, "Manifest library path is missing")
            require(Path(library).is_absolute() or "/" in library or "\\" in library,
                    "Bare manifest library requires separately resolved search-path evidence")
            target = Path(library) if Path(library).is_absolute() else path.parent / library
            require(not any(linklike(part) for part in (target, *target.parents)), "Manifest library is a link/junction")
            libraries[normalized(target)] = pin(target)
            for control in ("enable_environment", "disable_environment"):
                values = declaration.get(control, {})
                require(isinstance(values, dict) and all(isinstance(k, str) and k and isinstance(v, str)
                                                       for k, v in values.items()), "Invalid layer environment controls")
                environment_keys.update(key.upper() for key in values)
        verify_pin(manifest_pin)
        result.append({**entry, "manifest": manifest_pin, "libraries": list(libraries.values()),
                       "environment_keys": sorted(environment_keys),
                       "selection": "REGISTERED_STATIC_CANDIDATE_NOT_LOADER_READBACK"})
    return result


def verify_manifest_closure(packet):
    """Bind registered manifests, libraries and layer controls into the packet."""
    pins = {normalized(row["path"]): row for row in packet["files"]}
    # Reject missing manifest pins before reading any unpinned JSON.
    for entry in registered_manifests(packet["registry_policy"]):
        require(normalized(entry["path"]) in pins, "Registered Vulkan manifest is not pinned")
        verify_pin(pins[normalized(entry["path"])])
    modules = {normalized(path) for key in ("required_paths", "optional_paths")
               for path in packet["module_policy"][key]}
    for entry in inspect_registered_manifests(packet["registry_policy"]):
        for row in [entry["manifest"], *entry["libraries"]]:
            expected = pins.get(normalized(row["path"]))
            require(expected is not None and all(row[key] == expected[key] for key in ("sha256", "size")),
                    "Registered Vulkan manifest/library is not pinned or changed")
        require(all(normalized(row["path"]) in modules for row in entry["libraries"]),
                "Registered Vulkan library is absent from the reviewed module policy")
        require(set(entry["environment_keys"]) <= set(packet["environment_policy"]),
                "Manifest layer environment controls are not explicitly captured")
