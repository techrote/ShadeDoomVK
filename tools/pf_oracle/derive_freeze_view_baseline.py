#!/usr/bin/env python3
"""Export a pinned final tree and its exact PF-006/009/010 original seams.

This is a source-derived diagnostic baseline, never a historical executable or
native acceptance result. Git is read-only. No working-tree source is used.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "shadedoomvk-pf020-view-baseline-derivation/v1"
FULL_SHA = re.compile(r"[0-9a-f]{40}\Z")
MINIMUM_ACCEPTED_BASE = "7d29c7e4d64d61dba05524d9e7f5711ffd915d90"
HISTORIES = {
    "006": {
        "before": "eccaf068cb77d90da10472ba281520f0acb53986",
        "after": "a0fd21db5917e913c70cada765d13d4780130a6f",
        "merge": "ba9422554952355b7d3a0a87595cb994667d2be8",
    },
    "009": {
        "before": "898cab7c5c339f30f43f338741e6111de23e303b",
        "after": "8f78d5a10fe502d144b09b51f786b97e6e6bb54e",
        "merge": "b58f03decfedca12df039c68a5e36d709120bba1",
    },
    "010": {
        "before": "2f45c036ee5e7b122c0527e5a3de71c90e18288e",
        "after": "9116f9f5dff601a9c31bc97c63da39c1116f4739",
        "merge": "489e94e7194dacb7dcc2d7ed615ea9a1839a87c2",
    },
}
# Before contents, after blob IDs and exact merge parents were independently
# read through the authenticated GitHub connector on 2026-10-04. Runtime Git
# objects must match these immutable pins. This is not a fresh network check.
HISTORICAL_FILES = {
    "src/common/rendering/vulkan/pipelines/vk_renderpass.h": {
        "issue": "006", "before_blob": "1a692fc785506f83c9b31e1bf3f2d85c6d6b303e", "after_blob": "74f4ab5d57b27beec31c43b3960f126dacee7c32",
        "before_sha256": "8552dd2ed3df0ea7e8b8bc6e55ef2992f96199420d2f302058934e0a7c8177d5", "after_sha256": "400dbdb7e2a495008a952237a707a1bed94a6e8e5dd5a6fb91b86dfbe7132154",
        "hunks": [["6e54db3eb795e0f34a8a39c76e760dbe9d51e570ec720367fbadfc4308157c91","fec838e0df1d058851017b7449332d4998cae7a3960a39602036628138a371a3"],["5c7dc7708cf1186915958dea47360f229caf8e9daa0f41840aad41406e736447","a32b614312db91d546c6d0ccf804b18dc02b32f6ed2dc417eaeb77dc3d4748d5"],["825950f30170ef458d55ee0947e91af306e4549c28a8da4591bb4d02419c003c","c7cf6366bf56735290d8cf86c839f3854c1cb186a56b6a8e8a06a7668e14324e"]],
    },
    "src/common/rendering/vulkan/shaders/vk_shader.h": {
        "issue": "006", "before_blob": "abcc90eb1fd042b405c696572e34853d2822c0d1", "after_blob": "a9fd1ff4072712aacce7ad9dade7500fefc4894c",
        "before_sha256": "2c01b78c2404a2e84f8eebde203983169bdc262a60ceb16d27dc00172fd682c8", "after_sha256": "d3ff925e925981bb82483f13a19b8c5d2674946107c67039975fc97d6eae1ee1",
        "hunks": [["e53577351f19283d62096d566d6348fb2b7ed57a44c462620210052023596ecf","5f41b0c16bbe5bb05cc659bee9551c2372d8cf9206f5c6dfd68ae13b50a42dcc"],["f2a865a0018f993e1bce7cb97f5e0dbe1db66a6533ceabce556aedf3d5ec9288","fdc8796c23645b12c832c79d410631f9360094ce6c8d1dec120fbe10b2cc658a"]],
    },
    "src/common/rendering/vulkan/vk_keyidentity.h": {
        "issue": "006", "before_blob": None, "after_blob": "0dbbdb64410758eb3d501dc2b03a886d2f0ba169",
        "before_sha256": None, "after_sha256": "f66a02d1d5383b9c557975f7e46e560799ab18f6f809a21a470e33714eea3551",
        "hunks": [],
    },
    "src/rendering/hwrenderer/scene/hw_drawstructs.h": {
        "issue": "009", "before_blob": "e0d4f21d5201fd3de5cc61015644099d24c328f6", "after_blob": "00e00cf30168bd439b03aad848340ca312269b77",
        "before_sha256": "49342216ad82a08a9c6104451e7776ff14c44fb6c405b68aa72dd1ef14117b19", "after_sha256": "bfa93f652b789ffafd6475afb710250708328d7608937bbe4896ee149bfa7905",
        "hunks": [["d879d34100a7f8c9d5178c8859d561e0e22a9830dae61287ebc9329a34605a93","fe9a6ec4934ac7d967d3b3e895679ca434f688b3e3f429907c778c066ee5f34e"],["4901d2c765fd4da5324941711fc481027e71c9e0f5db3eef41627116a4678ce3","ab0c40634a385b8a6648beec4f9b0ebf4b974eb4461fc5b3e7b6a61a52e44d03"],["05ecd48b9f78224513dea41e7eeed4abab4684fdee7d747dd7e421daf840500f","173ec89d2beb3f9a67fb6c4ab6d3f34e1830b844a258d58240d9940a7be724eb"]],
    },
    "src/rendering/hwrenderer/scene/hw_sprite_surface.h": {
        "issue": "009", "before_blob": None, "after_blob": "a3966292a8367a031477c9a43056103e72122655",
        "before_sha256": None, "after_sha256": "58f3d53fcc37570c0dcc9d17a430d40143b77804b382007b8e0d9fd86068cd0f",
        "hunks": [],
    },
    "src/rendering/hwrenderer/scene/hw_sprites.cpp": {
        "issue": "009", "before_blob": "53cc4ef83337f51970b3aa0c9ba411267934416c", "after_blob": "12998a525b1d19a01e7894dc2aa4fbe7705fc87d",
        "before_sha256": "37a0ea0055c3956651f73702b8c188181df02fa9cecfd8ff71cf222662f62025", "after_sha256": "780c7024fb706ddcb39b77c97c41eeed13b2557325d1568d4f4a017529549da8",
        "hunks": [["e9ce39e84b600429a568fea180ff2c5c6cdfbaf0ab3a095402cc7a1e199b3c31","f97f63549605d811c4bcd55140e161ce75ccfa614f3084708023bd6c025defee"],["555dba3e0925291852859ab1829efad9e70b8241ec50848937d2a902bb15373d","582d56a5d80ca2ea90142ad0fb7d0ce4fa55ce0fc68626cbdefd202464d90ff9"],["a9390cca390a4c19196572f5387c68910b7a8a353d2d79f70b13bc20f063f279","88ea82111412e395a906df35f88625446f7d5d7eaf23b8ac8964ec24c077f3d2"],["b7bf96a4b72152e7db7edb043ea0eebec354d6bc3fa15b9f6697be4f8627029d","b8be351c145092b87becfe86b4b4d64d86e149165a3e85a560c3e70cc2d83997"],["98ff7b0157fe8e098c037108544d3663c6d6cb9967ab63ad2a72701ebc7151f7","cf228514c356c5e7eaacb82c048ca2870b45825dca93b57234d873711fe7ac08"],["f75270a6ea304f8f0aad43e04b0456e34ff682ad44a0341ef34f7db0f5ad6cfc","47411f8dcae8580c2ad492778f9e245db553e1704375efa72a44af65710196fd"],["1e33ae6c32c7f06087961e13bb4d6a1eaf3c6460f20909525c9abd32023ecf75","15c216da8c3a8c46dd65b7bac5fb5d49ead963b07d685f2c8aaf71e00921ba44"],["6c25ee9da783ff4901401f71e753144255538e6474b2ae30bc6f8796012ff784","ea5e9377453f125bc6b34b7297477329256878de6c852b7aa1262a47211e7f2b"],["9c915dedcedbeaa689a9fa62f5f68c8b8792182eb787560c17955bf423ec51e0","90829842310da0c401b4ead4d2397918f87c045801c3f95049d3870daa690d61"]],
    },
    "src/rendering/hwrenderer/hw_entrypoint.cpp": {
        "issue": "010", "before_blob": "22d6d0169df66119ce3fdd413f92936435b336ee", "after_blob": "2074efe4a08454c8be9a245b048e59c7e60513bf",
        "before_sha256": "b7773913035b2d838256499964da5d1e66671d2c00ffc23af1da8ba4e083fcb0", "after_sha256": "a39d31ce379d7769162a008de659df161254df004917c6881d9f699925842c85",
        "hunks": [["96f98c29adae12d2091186baa7c50db650528473a93abb1a03c7ae1b0f422a2e","7300aeddde01fa13e158569d203fc0c1ab7db76b5a59b4e027c23f43e0a2e46a"],["e84d0c821475f3d3b77fc43024645978ea20d8a590df86854f6b00dd3f52d42b","e6c7f0a5a9ec56327323fe2134787f19ab2bdc844e8af06ee63441064ddc00d2"]],
    },
    "src/rendering/hwrenderer/scene/hw_portal.h": {
        "issue": "010", "before_blob": "a3e88f64a3ff6f9a05b9d3349025473d43ad00a0", "after_blob": "79964b31f612798257e262f07ef84a937416cf6d",
        "before_sha256": "f4a42a42c898c55cfa7d6d0726a7beeb594d8921e170fade2c5bf0d4cffc3874", "after_sha256": "d18d9061eed3d1ca764510b6f3beabfb4abe751503878da1951b64fbec1656d6",
        "hunks": [["017a2861db580eea1718db11cdea38bb5317bb6b74a736c19a547cba694c429d","da1c6b9f21e144ece396d8416417287b10de06bae15ef4d4139255b0303f57d8"],["e636597631321c2ac8c58e6385144d6c18a9a175e054ee47d498ad837626eafb","246a99a98e960fc7cdbaaa60953c8420dacb9cb25c8933788b9a5bd79a96af0f"],["2629a70a614c7bc080b81553947a7a6d85d82516be5d69b7009eb37b0b386aae","958b12084d23c52a09b95d2c985f55a803690848cd60a9d4ff3232cb4a75d150"]],
    },
    "src/rendering/hwrenderer/scene/hw_rendercontext.h": {
        "issue": "010", "before_blob": None, "after_blob": "082373a0ef582d72bd96758a8a6f0f15d10e9e7f",
        "before_sha256": None, "after_sha256": "62b46406573b0b76c1337f2e284d27481d9c8d011673eabde154417af9c96739",
        "hunks": [],
    },
}

class DerivationError(RuntimeError):
    """A missing, ambiguous or changed input; never partial success."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo), *args],
        capture_output=True, check=False,
    )
    if result.returncode:
        raise DerivationError("read-only Git failed: " + " ".join(args[:3])
                              + ": " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def safe_relative(path: str) -> str:
    pure = PurePosixPath(path)
    if (not path or "\\" in path or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or any(":" in part for part in pure.parts)
            or pure.parts[0].casefold() == ".git"):
        raise DerivationError("unsafe tree path: " + repr(path))
    return path


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


@dataclass(frozen=True)
class Hunk:
    before: bytes
    after: bytes

    def record(self) -> dict:
        return {
            "before_sha256": sha256(self.before),
            "after_sha256": sha256(self.after),
            "before_bytes": len(self.before), "after_bytes": len(self.after),
        }


def parse_hunks(patch: bytes) -> list[Hunk]:
    """Retain every context byte; accept one ordinary text-file patch only."""
    if (patch.count(b"diff --git ") != 1 or b"GIT binary patch" in patch
            or b"\\ No newline at end of file" in patch):
        raise DerivationError("unsupported or multiple-file historical patch")
    hunks = []
    for section in re.split(rb"(?m)(?=^@@ )", patch)[1:]:
        lines = section.splitlines(keepends=True)
        if not re.fullmatch(rb"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@[^\n]*\n", lines[0]):
            raise DerivationError("malformed historical hunk header")
        old, new = [], []
        for line in lines[1:]:
            if not line or line[:1] not in {b" ", b"+", b"-"}:
                raise DerivationError("non-text historical hunk")
            if line[:1] in {b" ", b"-"}:
                old.append(line[1:])
            if line[:1] in {b" ", b"+"}:
                new.append(line[1:])
        hunk = Hunk(b"".join(old), b"".join(new))
        if not hunk.before or not hunk.after or hunk.before == hunk.after:
            raise DerivationError("empty or unchanged historical hunk")
        hunks.append(hunk)
    if not hunks:
        raise DerivationError("historical patch has no reversible hunks")
    return hunks


def exact_reverse(current: bytes, hunks: Iterable[Hunk]) -> tuple[bytes, list[dict]]:
    """Replace full authenticated after-hunks, without offsets or fuzz."""
    hunks = list(hunks)
    spans = []
    for ordinal, hunk in enumerate(hunks, 1):
        if current.count(hunk.after) != 1:
            raise DerivationError(f"hunk {ordinal}: full after-body must occur exactly once")
        start = current.index(hunk.after)
        spans.append((start, start + len(hunk.after), hunk, ordinal))
    spans.sort(key=lambda item: item[0])
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise DerivationError("overlapping historical after-hunks")
    baseline_parts, rebuilt_parts, records = [], [], []
    cursor = 0
    for start, end, hunk, ordinal in spans:
        untouched = current[cursor:start]
        baseline_parts.extend((untouched, hunk.before))
        rebuilt_parts.extend((untouched, hunk.after))
        records.append({
            "hunk": ordinal, **hunk.record(),
            "current_after_sha256": sha256(current[start:end]),
            "current_start_byte": start, "current_end_byte_exclusive": end,
            "current_first_line": current[:start].count(b"\n") + 1,
            "current_last_line": current[:end].count(b"\n"),
            "untouched_prefix_sha256": sha256(untouched),
        })
        cursor = end
    tail = current[cursor:]
    baseline_parts.append(tail)
    rebuilt_parts.append(tail)
    if b"".join(rebuilt_parts) != current:
        raise DerivationError("forward reconstruction is not byte-exact")
    baseline = b"".join(baseline_parts)
    if baseline == current:
        raise DerivationError("baseline did not execute a source change")
    return baseline, records


def block(source: bytes, anchor: bytes) -> bytes:
    """Extract a named class/function bounded by its actual balanced braces."""
    if source.count(anchor) != 1:
        raise DerivationError("missing or ambiguous original body anchor")
    start = source.index(anchor)
    opening = source.index(b"{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index:index + 1] == b"{":
            depth += 1
        elif source[index:index + 1] == b"}":
            depth -= 1
            if depth == 0:
                end = index + 1
                if source[end:end + 1] == b";":
                    end += 1
                return source[start:end]
    raise DerivationError("unterminated original body")


def body_guards(before: bytes, baseline: bytes, path: str) -> list[dict]:
    anchors = {
        "src/common/rendering/vulkan/pipelines/vk_renderpass.h":
            [b"class VkPipelineKey\n", b"class VkRenderPassKey\n"],
        "src/common/rendering/vulkan/shaders/vk_shader.h": [b"class VkShaderKey\n"],
    }.get(path, [])
    rows = []
    for anchor in anchors:
        original, derived = block(before, anchor), block(baseline, anchor)
        if derived != original:
            raise DerivationError("literal original key body changed: " + path)
        rows.append({"anchor": anchor.decode().strip(), "original_sha256": sha256(original),
                     "baseline_sha256": sha256(derived), "byte_equal": True})
    return rows


def verify_historical_blob(data: bytes, pin: dict, side: str, path: str) -> None:
    if (git_blob_id(data) != pin[side + "_blob"]
            or sha256(data) != pin[side + "_sha256"]):
        raise DerivationError("historical " + side + " blob pin mismatch: " + path)


def derive_plan(repo: Path, commit: str) -> tuple[dict[str, bytes | None], dict]:
    if not FULL_SHA.fullmatch(commit):
        raise DerivationError("--commit must be a full lowercase 40-character commit SHA")
    if git(repo, "rev-parse", "--verify", commit + "^{commit}").decode().strip() != commit:
        raise DerivationError("commit did not resolve exactly")
    git(repo, "merge-base", "--is-ancestor", MINIMUM_ACCEPTED_BASE, commit)
    changes, history_rows, current_rows = {}, [], []
    for issue, history in HISTORIES.items():
        merge_parents = git(repo, "show", "-s", "--format=%P", history["merge"]).decode().split()
        if merge_parents != [history["before"], history["after"]]:
            raise DerivationError("accepted merge ancestry pin mismatch: PF-" + issue)
        git(repo, "merge-base", "--is-ancestor", history["merge"], commit)
        names = git(repo, "diff", "--name-only", "--no-renames",
                    history["before"], history["after"], "--", "src").decode().splitlines()
        expected = sorted(path for path, pin in HISTORICAL_FILES.items() if pin["issue"] == issue)
        if sorted(names) != expected:
            raise DerivationError("historical production path allowlist mismatch: PF-" + issue)
        rows = []
        for path in expected:
            pin = HISTORICAL_FILES[path]
            after = git(repo, "show", history["after"] + ":" + path)
            verify_historical_blob(after, pin, "after", path)
            current = git(repo, "show", commit + ":" + path)
            current_rows.append({"path": path, "sha256": sha256(current),
                                 "git_blob": git_blob_id(current)})
            row = {"path": path, "pins": pin, "current_sha256": sha256(current)}
            if pin["before_blob"] is None:
                if git(repo, "ls-tree", history["before"], "--", path):
                    raise DerivationError("historical added file was present before: " + path)
                if current != after:
                    raise DerivationError("added-header deletion guard mismatch: " + path)
                changes[path] = None
                row.update({"operation": "remove-exact-added-header", "baseline_sha256": None})
            else:
                before = git(repo, "show", history["before"] + ":" + path)
                verify_historical_blob(before, pin, "before", path)
                patch = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                            "--no-color", "--diff-algorithm=myers", "--unified=3",
                            history["before"], history["after"], "--", path)
                hunks = parse_hunks(patch)
                if [[sha256(h.before), sha256(h.after)] for h in hunks] != pin["hunks"]:
                    raise DerivationError("historical full-hunk body pin mismatch: " + path)
                original, _ = exact_reverse(after, hunks)
                if original != before:
                    raise DerivationError("historical full reversal is not original blob: " + path)
                try:
                    baseline, hunk_rows = exact_reverse(current, hunks)
                except DerivationError as error:
                    raise DerivationError(path + ": " + str(error)) from error
                changes[path] = baseline
                row.update({"operation": "literal-full-hunk-reversal",
                            "patch_sha256": sha256(patch),
                            "baseline_sha256": sha256(baseline), "hunks": hunk_rows,
                            "original_key_bodies": body_guards(before, baseline, path),
                            "forward_reconstruction_byte_equal": True})
            rows.append(row)
        history_rows.append({
            "issue": "PF-" + issue, **history, "merge_parents": merge_parents,
            "github_compare": ("https://api.github.com/repos/techrote/ShadeDoomVK/compare/"
                               + history["before"] + "..." + history["after"]),
            "github_merge": ("https://api.github.com/repos/techrote/ShadeDoomVK/commits/"
                             + history["merge"]),
            "authenticated_pin_review_date": "2026-10-04",
            "fresh_network_check": False, "files": rows,
        })
    if set(changes) != set(HISTORICAL_FILES):
        raise DerivationError("derived production allowlist mismatch")
    sprite = changes["src/rendering/hwrenderer/scene/hw_sprites.cpp"]
    assert sprite is not None
    if b"top != -NO_VAL" not in sprite or b"if (top == -NO_VAL)" not in sprite:
        raise DerivationError("PF-014 ceiling sentinel preservation failed")
    portal = changes["src/rendering/hwrenderer/scene/hw_portal.h"]
    assert portal is not None
    if b"return x_offset[0] == inf.x_offset[0]" not in portal:
        raise DerivationError("PF-014 named sky identity preservation failed")
    return changes, {
        "schema": SCHEMA, "status": "SOURCE_DERIVATION_VERIFIED",
        "claim": "source-derived diagnostic baseline; not a historical binary",
        "commit": commit, "git_tree": git(repo, "rev-parse", commit + "^{tree}").decode().strip(),
        "minimum_accepted_base": MINIMUM_ACCEPTED_BASE,
        "working_tree_source_used": False, "git_state_mutated": False,
        "derivation_tool": {
            "path": "tools/pf_oracle/derive_freeze_view_baseline.py",
            "raw_sha256": sha256(Path(__file__).read_bytes()),
            "normalized_lf_sha256": sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        },
        "native_executed": False, "native_acceptance": False,
        "matching": "full literal historical hunks; no offsets, fuzz or partial application",
        "compile_definitions": {"current": [], "original-seams": ["PF020_ORIGINAL_SEAMS=1"]},
        "baseline_production_context_available": False,
        "historical": history_rows, "current_guarded_files": current_rows,
        "changed_paths": sorted(changes), "modified_files": 6, "removed_headers": 3,
        "preserved": {
            "all_paths_outside_allowlist": "must remain exact pinned current Git bytes",
            "all_modified_file_bytes_outside_hunks": "byte-exact forward reconstruction",
            "PF014_ceiling_sentinel_and_named_sky_identity": True,
            "PF015_CFX_material_PBR_and_lifetime_repairs": "outside delta; not reverted",
        },
        "limits": [
            "No image, cache, state or GPU equivalence measured by this tool.",
            "Baseline existing current-only tests are not claimed to pass.",
            "Observer-derived labels cannot be presented as baseline production context.",
            "A clean build and actual branch/state/image witnesses are still required.",
        ],
    }


def tree_entries(repo: Path, commit: str) -> list[tuple[str, str, str]]:
    rows = []
    for record in git(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        path = safe_relative(path_bytes.decode("utf-8"))
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise DerivationError("unsupported tree entry kind/mode: " + path)
        rows.append((path, mode, oid))
    if len({path.casefold() for path, _, _ in rows}) != len(rows):
        raise DerivationError("case-colliding paths cannot be exported portably")
    return rows


def choose_output(repo: Path, requested: Path) -> Path:
    repo = repo.resolve()
    output = requested if requested.is_absolute() else repo / requested
    build = repo / "build"
    if ".." in output.parts or not output.is_relative_to(build) or output == build:
        raise DerivationError("output must be a new child of this repository's ignored build directory")
    cursor = output
    while cursor != repo:
        if cursor.exists() and (cursor.is_symlink()
                                or getattr(cursor, "is_junction", lambda: False)()):
            raise DerivationError("output ancestor is a link/junction")
        cursor = cursor.parent
    output = output.resolve()
    if not output.is_relative_to(build):
        raise DerivationError("resolved output escapes ignored build directory")
    if output.exists():
        raise DerivationError("output already exists; retained attempts are never overwritten")
    relative = output.relative_to(repo).as_posix()
    git(repo, "check-ignore", "--no-index", "-q", "--", relative + "/derivation.json")
    return output


def json_write(path: Path, data: dict) -> None:
    path.write_bytes((json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def closure_digest(rows: list[dict]) -> str:
    projection = [[r["path"], r["mode"], r["sha256"], r["bytes"]] for r in rows]
    return sha256(json.dumps(projection, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def export(repo: Path, commit: str, requested: Path) -> dict:
    """Export actual Git blob bytes; never checkout, archive filters or CRLF conversion."""
    changes, report = derive_plan(repo, commit)
    entries = tree_entries(repo, commit)
    output = choose_output(repo, requested)
    output.mkdir(parents=True, exist_ok=False)
    json_write(output / "derivation.json", {**report, "status": "EXPORT_IN_PROGRESS"})
    current_rows, baseline_rows = [], []
    process = None
    try:
        process = subprocess.Popen(
            ["git", "--no-replace-objects", "-C", str(repo), "cat-file", "--batch"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        assert process.stdin is not None and process.stdout is not None
        for path, mode, oid in entries:
            process.stdin.write((oid + "\n").encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").strip().split()
            if len(header) != 3 or header[0] != oid or header[1] != "blob":
                raise DerivationError("Git batch blob identity mismatch: " + path)
            size = int(header[2])
            data = process.stdout.read(size)
            if len(data) != size or process.stdout.read(1) != b"\n" or git_blob_id(data) != oid:
                raise DerivationError("Git batch truncated or corrupt blob: " + path)
            baseline = changes.get(path, data)
            for variant, content, rows in (
                ("current", data, current_rows), ("original-seams", baseline, baseline_rows)
            ):
                if content is None:
                    continue
                destination = output / variant / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                if mode == "100755" and sys.platform != "win32":
                    destination.chmod(0o755)
                if destination.read_bytes() != content:
                    raise DerivationError("export byte verification failed: " + path)
                rows.append({"path": path, "mode": mode, "bytes": len(content),
                             "sha256": sha256(content), "git_blob": git_blob_id(content)})
        process.stdin.close()
        if process.wait(timeout=30) != 0:
            raise DerivationError("Git batch export failed")
        current_map = {r["path"]: r for r in current_rows}
        baseline_map = {r["path"]: r for r in baseline_rows}
        actual_changed = sorted(path for path in current_map
                                if path not in baseline_map
                                or current_map[path]["sha256"] != baseline_map[path]["sha256"])
        if actual_changed != sorted(changes) or set(baseline_map) - set(current_map):
            raise DerivationError("export differs outside exact nine-path allowlist")
        report.update({
            "status": "PASS", "output": output.relative_to(repo).as_posix(),
            "export_byte_verified": True, "changed_path_allowlist_verified": True,
            "closure": {
                "current": {"files": current_rows, "file_count": len(current_rows),
                            "sha256": closure_digest(current_rows)},
                "original-seams": {"files": baseline_rows, "file_count": len(baseline_rows),
                                   "sha256": closure_digest(baseline_rows)},
            },
        })
        for variant, rows in (("current", current_rows), ("original-seams", baseline_rows)):
            runtime = [row for row in rows if row["path"].startswith(
                ("src/", "libraries/", "wadsrc/", "cmake/"))
                or row["path"].endswith("CMakeLists.txt")]
            report["closure"][variant]["runtime_source"] = {
                "file_count": len(runtime), "sha256": closure_digest(runtime),
                "membership": "src/, libraries/, wadsrc/, cmake/, all CMakeLists.txt",
            }
        json_write(output / "derivation.json", report)
        return report
    except Exception as error:
        json_write(output / "derivation.json", {
            **report, "status": "FAIL", "error": str(error),
            "native_executed": False, "partial_export_retained": True,
        })
        raise
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=30)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="one full pinned final-source commit")
    parser.add_argument("--out", type=Path, help="fresh ignored build child (required for export)")
    parser.add_argument("--verify-only", action="store_true", help="verify guards without exporting")
    args = parser.parse_args(argv)
    if not args.verify_only and args.out is None:
        parser.error("--out is required unless --verify-only")
    try:
        if args.verify_only:
            _, report = derive_plan(ROOT, args.commit)
        else:
            report = export(ROOT, args.commit, args.out)
        print(json.dumps({
            "status": report["status"], "commit": report["commit"],
            "changed_paths": report["changed_paths"], "native_acceptance": False,
            "out": None if args.verify_only else report["output"],
        }, sort_keys=True))
        return 0
    except (DerivationError, OSError, subprocess.SubprocessError, ValueError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
