# SDVK-161 — startup texture-epoch cause investigation (14 November 2026)

**Status: NONQUALIFYING DIAGNOSTIC ONLY. No fix or root cause is claimed by this commit.**

## Authority and original failure

- Source boundary: frozen PR #201 head `9b465d1ce1c73050d6a0b52cd51f592e5523b2ad`, stacked on Draft PR #196, with current accepted master unchanged at intake `0ecba708e283e33c381fae329ace7a2cedc6a3f3`.
- Original publication CI #627 `43549214686` is **FAILED** on original SDVK-161 semantic repeatability at frame 37 (80 versus 84 actual immediate wall vertices and 22 versus 23 empty light-range uploads). The missing quad is **not repaired** here.
- Separate nonqualifying 8-attempt passive-wall cohort `43584239055` / artifact `14110870017`: 8 individually admitted captures and 35/35 original negatives each; all wall traces identical, but strict comparison pair 1–2 failed on an initial `texture_epoch` difference (3 versus 4), persisting through all retained frames. Final exact RGB matched. Three other pairs passed. The accepted texture/resource generation comparator must **not** be relaxed.
- Source `VkTextureManager::RemoveTexture`, `RemovePPTexture` and `Deinit` each call `TextureEpoch.Invalidate()`. Their causal call sites, owner identities and lifetime phase were not captured in the failed original packet.

## Hypothesis / experimental discriminator

A single additional invalidation before the first retained view would explain the persistent +1 difference. It might be a legitimate transient HW/PP texture owner retirement, or an incorrect lifecycle/ownership transition. A numerical difference alone **does not justify removing an invalidation**.

This isolated branch adds default-off `SDVK161_TEXTURE_EPOCH_TRACE=1` recording to the exact three invalidating methods, with companion HW/PP registration and manager birth/destruction events. Bounded scalar events retain original before/after epoch, manager type, owner registration ordinal, current live list counts and the actual observer view phase. A native Linux callstack is collected *at the source call*, but symbol/ELF-offset resolution and output occur **after** the original 32+96-frame capture. The capped trace freezes at the end of retained frame one; each run includes a verified native first-frame texture epoch to independently reconcile against event deltas. No raw pointer is used as a cross-process identity; owner IDs are per-process first-registration ordinals.

Eight independent, source-identified original lifecycle captures are preregistered with zero retries. Each requires unchanged native run validation, original lifecycle, twelve image checkpoints, 35 original falsifying controls and original exact semantic-state/RGB comparisons. No altered capture interval, extra view, renderer result-dependent input, GPU readback, threshold, atlas/descriptor semantics or other feature execution. Every trace is marked NONQUALIFYING and the diagnostic CI intentionally fails its final PRECHECK_ONLY guard. The previous missing-wall defect stays a separate unresolved risk.

## Falsifying controls and limits

- 256 event cap; overflow, missing manager creation, owner registration/retirement mismatch, unaccounted epoch increments and wrong source/native first-retained epoch are rejection cases, not auto-normalized.
- Event caller data is bounded: at most 14 trace PC slots per event; Linux ELF module-base-relative PCs are resolved using the source-matched `addr2line` after each native process ends. Diagnostic callstack capture may perturb timing, so a negative/non-reproduction does not prove an absence of concurrency or startup ordering defects.
- No production fix unless a reproducible counterexample identifies a specific lifetime misuse and the proposed adjustment preserves stale-reference rejection. The correct stopping point for valid transient retirement is a documented **no-fix** result with the original strict gate still failing.

## Approval gates

1. Establish exact attribution of the extra `TextureEpoch.Invalidate()` event and its owner/caller via admitted original captures.
2. Independently decide legitimate lifecycle versus incorrect owner retirement, with a failing pre-fix control.
3. Only then separately implement the smallest causal fix and requalify original SDVK-161. Follow-on missing-wall investigation remains open.
4. Keep #196 and #201 Draft/HOLD and unmerged; parent #14 physical cost/stability remains unaccepted.
