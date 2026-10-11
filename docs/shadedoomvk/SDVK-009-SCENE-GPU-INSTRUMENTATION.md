# SDVK-009 scene GPU timestamp instrumentation candidate

This is a separately identified instrumentation candidate, first developed on frozen
`0a2fbad203549d18ac6e5a61bb4747709637bfde` and integrated onto verified
`master@41340ac5790c9cbf690fcd0c49338b5bb6c84927` (including the later SDVK-008/010
implementations). It does not modify the frozen source or
claim physical qualification. The original baseline lacks an ordinary scene
timestamp span: postprocess/lightmapper/dormant tile groups cannot establish
many-light shader scaling. A new exact build, preregistration, source/CI gates
and independent physical packet are required before using this candidate.

`scene.immediate` is one outer span per top-level MainView eye, beginning before
`HWDrawInfo::ProcessScene`, including portal recursion and `EndDrawScene`, and
ending before `PostProcessScene` and its 2D callback. LevelMesh, raytrace, camera
textures, probe faces and other root contexts do not open this span. The scope
uses the existing explicit `-sdvkobservegpu` switch and remains inactive for
ordinary/default-OFF rendering. This is a named COLOR_ATTACHMENT_OUTPUT-stage
timestamp interval, not an independently measured whole GPU frame. Nested
groups must not be added to it.

The RAII owner closes only a successfully opened group and closes once, including
exception unwinding. `PushGroup` reports whether it actually opened a group;
existing callers preserve their behavior. No new submission, fence wait, query
readback, shader change or workload/quality change is introduced. Mid-scene
`FlushCommands`/`WaitForCommands(false)` retain the pool/index/group stack;
ordered submissions use the existing semaphore chain. Group resolution/reset
remains at the final `UpdateGpuStats` after graphics completion. The dormant
thread-command producer has no call sites in this frozen source.

The physical receipt recognizes scene coverage only when all fifteen timing
processes retain exactly one resolved `scene.immediate` sample in every one of
their 120 frames and all other retained groups are complete. Missing, partial
or multiplied coverage remains inconclusive. Complete coverage permits later
threshold analysis; `physical_gpu_qualified` and `performance_accepted` remain
false until reviewed issue acceptance.

CPU tests execute the production RAII header and extracted actual command-group
functions, covering disabled/ineligible/unavailable paths, ownership, explicit
close, double close, exception unwinding, command-buffer change and exhausted
query capacity. Source tests pin the scene/postprocess boundaries, opt-in guards,
absence of new waits/submissions and query lifetime across flushes. None of these
tests is Vulkan execution or physical timing evidence.
