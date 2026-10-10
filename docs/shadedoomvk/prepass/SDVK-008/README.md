# SDVK-008 preparatory checkpoint (NOT production or acceptance)

The complete research package is retained as the ZIP beside this index: `SDVK-008-PREPASS-PACKAGE.zip`. Extract it at repository root; paths inside the archive are `docs/shadedoomvk/prepass/SDVK-008/` and `tools/prepass/sdvk008/`. Individual source/report text files live **inside the archive** because this is a preservational checkpoint, not an implementation branch. `CHECKSUMS.sha256` in the archive lists every file's exact SHA-256. The package must not be interpreted as modifications to active renderer code or a merged #8 implementation.

Start with `SDVK-008-PREPASS.md` in the extracted docs directory; companion files include a physical-GPU preregistration document, proposed runtime diagnostic JSON schema, asset-generator hash manifest and 1,620-case CPU receipt. The CPU prototype, deterministic PNM fixture generator and unit tests are under `tools/prepass/sdvk008/` within the archive. Use Python 3.10+ and standard library only.

```
python3 -m unittest discover -s tools/prepass/sdvk008 -p test_reference.py -v
python3 tools/prepass/sdvk008/test_reference.py --receipt /tmp/sdvk008-grid.json
python3 tools/prepass/sdvk008/fixtures.py --out /tmp/sdvk008-new-pnm --size 32
```

At checkpoint preparation, `master` was `cbff1d10b802e60a56d239338f810f7e1e52920d`; #7 PR #135 was open/unaccepted, and #8 was open/unimplemented. **Do not apply this archive to production shaders or treat its basis representation as accepted.** When #7 is accepted, verify the semantic T/B/N/parity, height-only card eligibility, UV/alpha mapping and portal/mirror semantics against its final implementation before starting #8. Physical performance has **not** been measured. #8 must remain open.
