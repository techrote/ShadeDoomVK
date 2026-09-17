# PF renderer oracle

This directory contains the small deterministic **pre-foundation oracle** introduced by PF-001.

It is deliberately not the full SDVK-002 renderer benchmark/reference-scene system. GitHub-hosted CI does not have a trustworthy Doom runtime/IWAD/Vulkan presentation environment, so PF-001 does not pretend that source inspection is equivalent to rendered validation. Instead it provides two complementary contracts:

1. `run.py` + `probes.json` + `baseline.json` pin cheap source-level renderer invariants and known baseline defects in CI.
2. `runtime_evidence.schema.json` defines the machine-readable state shape that later runnable renderer fixtures/captures must emit.

## Run locally

From the repository root:

```bash
python3 -m unittest discover -s tools/pf_oracle/tests -v
python3 tools/pf_oracle/run.py \
  --manifest tools/pf_oracle/probes.json \
  --baseline tools/pf_oracle/baseline.json \
  --output pf-oracle.json
```

Run it twice and compare the two JSON files to verify determinism:

```bash
python3 tools/pf_oracle/run.py --baseline tools/pf_oracle/baseline.json --output pf-oracle-a.json
python3 tools/pf_oracle/run.py --baseline tools/pf_oracle/baseline.json --output pf-oracle-b.json
cmp pf-oracle-a.json pf-oracle-b.json
```

The runner uses only the Python standard library.

PF-002 also adds a tiny C++ lifetime primitive fixture. To run the same check locally:

```bash
mkdir -p build/pf-oracle
c++ -std=c++17 -Wall -Wextra -Werror \
  -Isrc/common/rendering/hwrenderer/data \
  tools/pf_oracle/tests/resource_generation_fixture.cpp \
  -o build/pf-oracle/resource-generation-fixture
build/pf-oracle/resource-generation-fixture
```

The fixture deliberately retains stale slot identities through retire/reuse/reset transitions and asserts that validation rejects them while incrementing the diagnostic counters.

## Result meanings

`invariant_passed`
: A renderer/source contract that later work depends on is still present.

`invariant_broken`
: An expected contract disappeared or changed unexpectedly. The oracle exits non-zero.

`known_defect_reproduced`
: A deliberately pinned pre-fix defect marker is still present. This is expected until its owning PF issue repairs the defect.

`known_defect_changed`
: A pinned defect marker disappeared/changed. This also exits non-zero: a real fix is welcome, but its owning issue must deliberately update the probe and checked-in baseline in the same accepted change.

This distinction prevents both accidental regression and accidental "green CI" caused by deleting a reproducer.

## Adding or changing probes

A probe is appropriate here when it protects a durable PF architecture seam or a minimized source-level reproducer. Prefer symbols/semantic markers over line numbers.

Every probe declares an owning stable issue ID. When an owning issue intentionally changes the source contract:

1. update/add the relevant runtime or source fixture;
2. update `probes.json` deliberately;
3. regenerate/review `baseline.json`;
4. explain the semantic delta in the issue/PR evidence;
5. update relevant `docs/shadedoomvk/rag/` references.

Do not weaken a probe merely to make CI green.

## Runtime/image evidence

`runtime_evidence.schema.json` is the interchange contract for later executable fixtures. It can describe:

- main/portal/mirror/camera/probe render context;
- semantic material layers and sampler choices;
- resource slots/generations;
- considered/selected/rejected lights;
- probe mode/index/fallback;
- shadow mode/candidate/selection state;
- timings/counters;
- optional image hash/comparison metadata.

The comparison rules are in `docs/shadedoomvk/PF-EQUIVALENCE-PROTOCOL.md`.
