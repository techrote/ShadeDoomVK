# Conditional renderer grant adapter — non-executable draft

The current v1 gate requires a fresh exact-packet approval and records its
`decided_utc`. A broad earlier user grant with later agent plan review must not
be converted into a fictitious later human decision or a quote the user never
typed. `conditional_grant.py` starts a separate, explicit resolution format.

The draft keeps the grant's recorded time and verbatim instructions separate
from the later plan review. It binds both digests, checks condition/source
blockers, and checks finite total and per-test attempt counts including failed
creation attempts. Retries/repetitions need a new packet and reviewed
disposition. Duplicate packet/test charges, attempt gaps, expanded budgets,
missing conditions and unaccepted source fail closed. The default existing
packet still has no automatic retries.

The resolution is deliberately marked `execution_ready:false`, has no
`decided_utc`, and is not a v1 approval. The existing approval function rejects
it. This code does not create an approval, publish a release, write a budget
claim, clear STOP or start a process. Its four CPU tests include 24 finite
synthetic reservations, global/per-test exhaustion, replay rejection and proof
that the result cannot release the existing gate.

Remaining integration work is an independently reviewed prospective approval
schema and an atomic owner/packet/test-bound budget reservation before native
creation. Failure/abort/retry accounting and release/claim coupling must be
qualified with native CPU controls before any renderer uses this adapter.
The worker/controller/instance attestation is a separate candidate. Genuine
native properties are not a renderer diagnostic or physical acceptance.

Physical qualification remains HELD / NOT ACCEPTED; historical STOP records and
failures stay immutable, and issue #9 remains open. This draft confers no new
physical authority beyond a real owner's recorded instructions.
