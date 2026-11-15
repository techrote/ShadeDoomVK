# ShadeDoomVK — hosted software Vulkan and local GPU evaluation

**Owner clarification, 15 November 2026.** There are two normal, complementary execution environments. Do not confuse them or require either to imitate the other.

## 1. Assistant and CI: software Vulkan is normal

Autonomous implementation, regression testing, reproduction, instrumentation and visual capture on **CPU-only VPS / GitHub-hosted runners** should continue with **lavapipe/llvmpipe software Vulkan**, ordinary CPU fixtures and other available tools. These environments do not need a discrete GPU to be useful. No blanket obligation to obtain physical hardware, no suppression of software Vulkan and no demand to run every developer check locally.

Hosted software-Vulkan qualification may prove that particular shader/render paths actually executed and emitted valid frames, state and resources. **Do not label it a physical GPU benchmark**, hardware driver-stability demonstration, Windows input playtest or user acceptance.

## 2. Owner's local Windows machine: use the actual GPU

When the owner runs a ShadeDoomVK development task or evaluation build on their GPU-equipped computer, **real GPU rendering is the entire point**. It is normal and intended, not a separately authorised exception. Do not install generic launch blockers, force software rendering, ship print-only commands, disable control/audio/HUD, or suppress implemented visual features just to meet a historic testing ritual.

A user-facing development build should launch normally with the **mutually compatible implemented visual features enabled and deliberately tuned**, with PBR layers generated from user-owned IWADs, dynamic lighting/flashlight present, correct gameplay input and explicit optional-effect switches. Distinguish the integrated playtest from synthetic screenshot fixtures and report any unavailable, unmerged or content-dependent features plainly.

## 3. Preserve useful technical caution without a blanket STOP

Historical driver errors are evidence about specific workloads, not a general prohibition on local GPU use. If a **particular reproducible heavy stress test** caused a device timeout, avoid blindly looping it unchanged; keep the fault details, select an informative bounded investigation and do not change firmware, drivers or power settings without direction. Ordinary gameplay, native evaluation, visual tuning and relevant GPU profiling are not thereby forbidden.

Existing dated supervisor/physical-test documents retain their exact historical meaning and their failures remain failures. No new run is automatically proof of long-term stability or representative performance. This guidance does not merge pending PRs or rewrite earlier evidence.

Related: [AGENTS.md](../../AGENTS.md), [renderer RAG index](rag/README.md), [Lost 2003 campaign](https://github.com/techrote/ShadeDoomVK/blob/planning/lost-2003-remaster-20261114/docs/shadedoomvk/REMASTER-2003-CAMPAIGN.md).
