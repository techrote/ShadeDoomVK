#!/usr/bin/env python3
"""Run the complete CPU contract checks used by CI. SPDX-License-Identifier: GPL-3.0-or-later."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/checks"))
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "temp"
    temporary.mkdir(exist_ok=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMP=str(temporary),
                       TEMP=str(temporary), TMPDIR=str(temporary))

    def run(name, arguments):
        log = output / (name + ".log")
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([sys.executable, *map(str, arguments)], cwd=ROOT,
                                    env=environment, stdout=stream, stderr=subprocess.STDOUT)
        print(f"{'PASS' if result.returncode == 0 else 'FAIL'} {name}: {log}", flush=True)
        if result.returncode:
            print(log.read_text(encoding="utf-8", errors="replace")[-12000:])
            raise SystemExit(result.returncode)

    run("pf-tests", ["-m", "unittest", "discover", "-s", "tools/pf_oracle/tests", "-q"])
    run("cfx-tests", ["tools/test_cfx_capture.py"])
    run("renderer-oracle-tests", ["-m", "unittest", "discover", "-s", "tools/renderer_oracle/tests", "-q"])
    run("renderer-corpus", ["tools/renderer_oracle/run.py", "ci", "--out", output / "renderer-corpus"])
    for suffix in ("a", "b"):
        run("oracle-" + suffix, ["tools/pf_oracle/run.py", "--baseline",
                                 "tools/pf_oracle/baseline.json", "--output",
                                 output / ("oracle-" + suffix + ".json")])
    if (output / "oracle-a.json").read_bytes() != (output / "oracle-b.json").read_bytes():
        raise SystemExit("FAIL: oracle outputs are not byte-identical")
    includes = {
        "resource_generation": ["src/common/rendering/hwrenderer/data"],
        "bindless_allocator": ["src/common/rendering", "src/common/rendering/vulkan/descriptorsets"],
        "levelmesh_contract": ["src/common/rendering/hwrenderer/data"],
        "probe_selection": ["src/common/rendering/hwrenderer/data"],
    }
    for fixture, paths in includes.items():
        arguments = ["tools/pf_oracle/fixture_runner.py", "--source",
                     f"tools/pf_oracle/tests/{fixture}_fixture.cpp"]
        for path in paths:
            arguments.extend(["--include", path])
        run(fixture, arguments)
    print("All CPU checks passed; deterministic PF oracle outputs and renderer corpus preparations match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
