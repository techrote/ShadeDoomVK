"""Truthful conditional grants and an append-only, OS-serialized attempt ledger.

The earlier user instruction is distinct from a later agent plan review. Every
native renderer creation attempt is charged durably, including failed creates.
No automatic retry, refund, historical STOP removal or campaign is supported.
"""
import datetime as dt
import hashlib
import os
import re
import subprocess
from pathlib import Path

from .common import (Gate, canonical, exclusive, future, linklike, pin,
                     read_json, require, sealed_environment, utc, verify_pin)

STAGES = ["compositing", "shadow-boundary-1", "shadow-boundary-2"]


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def check_budget(grant, charges, test, packet_sha256, *, reviewed_retry=False):
    require(grant["schema"] == "sdvk009-conditional-renderer-grant/v1", "Unsupported conditional grant")
    cap, retries = grant["max_renderer_launches"], grant["max_retries_per_test"]
    require(type(cap) is int and 0 < cap <= 24 and type(retries) is int and 0 <= retries <= 3,
            "Invalid or expanded user budget")
    require(grant["user_instruction_verbatim"].strip() and grant["user_addendum_verbatim"].strip(),
            "Actual conditional instruction and retry addendum are required")
    require(isinstance(grant["tests"], list) and grant["tests"] and
            all(isinstance(name, str) and name for name in grant["tests"]) and
            len(grant["tests"]) == len(set(grant["tests"])), "Test contracts must be named and unique")
    require(test in grant["tests"] and re.fullmatch(r"[0-9a-f]{64}", packet_sha256), "Unknown test or packet identity")
    seen, counts = set(), {}
    for row in charges:
        identity = (row["test"], row["packet_sha256"])
        require(row["test"] in grant["tests"] and re.fullmatch(r"[0-9a-f]{64}", row["packet_sha256"]),
                "Invalid historical charge")
        require(identity not in seen and type(row["attempt"]) is int and
                row["attempt"] == counts.get(row["test"], 0), "Budget history replay or attempt gap")
        seen.add(identity); counts[row["test"]] = counts.get(row["test"], 0) + 1
        require(counts[row["test"]] <= retries + 1, "Historical per-test budget exceeded")
    require(len(charges) < cap, "Global renderer launch allowance exhausted")
    require((test, packet_sha256) not in seen, "A packet/test charge cannot be replayed")
    attempt = counts.get(test, 0)
    require(attempt <= retries, "Per-test retry allowance exhausted")
    require(attempt == 0 or reviewed_retry is True, "Retry/repetition requires a new reviewed packet and failure disposition")
    return {"test": test, "packet_sha256": packet_sha256, "attempt": attempt,
            "charge_before_native_creation": True, "counts_toward_total_including_failed_creates": True}


def resolve_for_review(grant, packet, review, charges, test):
    """Keep the user's earlier grant time distinct from this later plan review."""
    require(review["schema"] == "sdvk009-conditional-plan-review/v1", "Wrong conditional review schema")
    require(review["grant_sha256"] == digest(grant) and review["packet_sha256"] == digest(packet),
            "Conditional review binds a different grant or packet")
    future(grant["expires_utc"]); future(review["expires_utc"])
    recorded = dt.datetime.fromisoformat(grant["recorded_utc"])
    reviewed = dt.datetime.fromisoformat(review["plan_reviewed_utc"])
    created = dt.datetime.fromisoformat(packet["created_utc"])
    require(all(value.tzinfo is not None for value in (recorded, reviewed, created)) and reviewed >= max(recorded, created),
            "Conditional plan review is missing a timezone or predates its evidence")
    require(review["blocking_findings"] == [] and review["accepted_supervisor_source"] is True,
            "Conditional resolution still has source or review blockers")
    require(set(review["conditions_satisfied"]) >= set(grant["conditions"]), "Grant conditions remain unsatisfied")
    require(packet["kind"] == "diagnostic" and packet["automatic_retries"] == 0,
            "This draft cannot expand the workload or create automatic retries")
    charge = check_budget(grant, charges, test, digest(packet), reviewed_retry=review.get("reviewed_retry", False))
    return {"schema": "sdvk009-conditional-resolution-DRAFT/v1", "execution_ready": False,
            "grant_recorded_utc": grant["recorded_utc"], "plan_reviewed_utc": review["plan_reviewed_utc"],
            "grant_sha256": digest(grant), "packet_sha256": digest(packet), "prospective_charge": charge,
            "no_later_human_decision_timestamp_claimed": True,
            "remaining_gate": "Reviewed atomic budget/conditional approval integration is not implemented in v1 approve"}


def authority(packet):
    """The grant's immutable bytes bind its unique ledger and owner identity."""
    row = packet["conditional_grant"]
    verify_pin(row)
    require(row in packet["files"], "Conditional grant is absent from packet custody")
    grant = read_json(row["path"])
    require(grant["tests"] == STAGES, "Conditional execution supports only the fixed diagnostic tests")
    require(re.fullmatch(r"[A-Za-z0-9_-]{8,100}", grant["grant_id"]) and
            isinstance(grant["owner"], str) and grant["owner"].strip(), "Missing grant/owner identity")
    root = Path(grant["ledger_root"])
    require(root.is_absolute(), "Budget ledger requires an absolute, unique root")
    for part in (root, *root.parents):
        if part.exists():
            require(not linklike(part), "Budget ledger path is a link/junction")
    require(read_json(root / "grant.json") == grant, "Ledger belongs to a different grant")
    check_budget(grant, [], STAGES[0], "0" * 64)
    future(grant["expires_utc"])
    return grant


def initialize_ledger(grant):
    """Create once. Never create/reset a ledger implicitly while releasing it."""
    check_budget(grant, [], grant["tests"][0], "0" * 64)
    root = Path(grant["ledger_root"])
    require(root.is_absolute(), "Budget root must be absolute")
    for part in root.parents:
        require(not linklike(part), "Budget ancestor is a link/junction")
    root.mkdir(exist_ok=False)
    exclusive(root / "grant.json", grant, durable=True)
    return pin(root / "grant.json")


class Ledger:
    """One serialized hash chain for sessions, charges and terminal receipts.

    Unfinished sessions and interrupted publications block successors. Final
    records cannot be rewritten; an explicit assessed disposition binds every
    earlier session before a repeat. Reservations are never refunded.
    """
    def __init__(self, grant):
        self.grant = grant
        self.root = Path(grant["ledger_root"])
        self.lock = Gate(self.root, digest(grant))
        self.guard = None

    def __enter__(self):
        try:
            if os.name == "nt":
                from .windows import RootGuard
                # Ledger membership changes by design. Retain NTFS directory
                # and ancestor identities while serializing every mutation.
                self.guard = RootGuard({"runtime_roots": [{"path": str(self.root)}]}, mutable_membership=True)
            self.lock.__enter__()
            require(read_json(self.root / "grant.json") == self.grant, "Ledger grant changed")
            require(not list(self.root.glob(".pending-*")), "Interrupted budget publication needs assessment")
            self.rows = []
            previous = "0" * 64
            for index, path in enumerate(sorted(self.root.glob("event-*.json"))):
                row = read_json(path)
                require(path.name == f"event-{index:06d}.json" and row["index"] == index and
                        row["previous_sha256"] == previous and row["grant_sha256"] == digest(self.grant),
                        "Budget chain gap/change")
                self.rows.append(row)
                previous = digest(row)
            self.previous = previous
            return self
        except BaseException:
            if self.lock.lock is not None and not self.lock.lock.closed:
                self.lock.__exit__()
            if self.guard: self.guard.close()
            raise

    def __exit__(self, *args):
        try:
            if self.guard: self.guard.check()
        finally:
            self.lock.__exit__(*args)
            if self.guard: self.guard.close()

    def append(self, kind, value):
        if self.guard: self.guard.check()
        row = {"index": len(self.rows), "previous_sha256": self.previous,
               "grant_sha256": digest(self.grant), "utc": utc(), "kind": kind, "value": value}
        exclusive(self.root / f"event-{len(self.rows):06d}.json", row, durable=True)
        self.rows.append(row)
        self.previous = digest(row)
        return row

    def charges(self):
        return [r["value"] for r in self.rows if r["kind"] == "charge"]

    def start(self, packet_sha, stop_root, review):
        sessions = [r for r in self.rows if r["kind"] == "session"]
        finished = {r["value"]["packet_sha256"]: r for r in self.rows if r["kind"] == "finish"}
        for row in finished.values():
            verify_pin(row["value"]["result"])
        require(all(r["value"]["packet_sha256"] in finished for r in sessions),
                "An earlier experiment is unresolved; no concurrent or blind retry")
        require(all(r["value"]["packet_sha256"] != packet_sha and r["value"]["stop_root"] != stop_root
                    for r in sessions), "Packet or STOP root was already claimed")
        assessed = review.get("assessed_predecessors", [])
        require({digest(r) for r in finished.values()} <= set(assessed),
                "Every earlier result needs an explicit assessed disposition")
        if sessions:
            require(isinstance(review.get("retry_assessment"), str) and review["retry_assessment"].strip(),
                    "Retry/repetition assessment is required")
        return self.append("session", {"packet_sha256": packet_sha, "stop_root": stop_root,
                                       "review_sha256": digest(review), "reviewed_retry": bool(sessions)})

    def session(self, packet_sha):
        sessions = [r for r in self.rows if r["kind"] == "session" and r["value"]["packet_sha256"] == packet_sha]
        require(len(sessions) == 1 and not any(r["kind"] == "finish" and
                r["value"]["packet_sha256"] == packet_sha for r in self.rows), "Missing or finished budget session")
        return sessions[0]["value"]

    def reserve(self, packet_sha, test, stop_root):
        session = self.session(packet_sha)
        require(session["stop_root"] == stop_root, "Budget session STOP root changed")
        stage_charges = [r for r in self.charges() if r["packet_sha256"] == packet_sha]
        require([r["test"] for r in stage_charges] == STAGES[:len(stage_charges)] and
                len(stage_charges) < len(STAGES) and test == STAGES[len(stage_charges)], "Budget stage order/replay")
        # Earlier stages must pass their independent observer and late-event
        # fence before another process can even be charged.
        for charge in stage_charges:
            require(any(r["kind"] == "stage-complete" and r["value"]["charge_sha256"] == digest(charge)
                        for r in self.rows), "Earlier stage lacks a completed safety fence")
        charge = check_budget(self.grant, self.charges(), test, packet_sha,
                              reviewed_retry=session["reviewed_retry"])
        self.append("charge", charge)
        return charge

    def complete(self, packet_sha, test):
        self.session(packet_sha)
        charges = [r for r in self.charges() if r["packet_sha256"] == packet_sha and r["test"] == test]
        require(len(charges) == 1, "Stage completion has no unique charge")
        sha = digest(charges[0])
        require(not any(r["kind"] == "stage-complete" and r["value"]["charge_sha256"] == sha for r in self.rows),
                "Duplicate stage completion")
        self.append("stage-complete", {"packet_sha256": packet_sha, "charge_sha256": sha})

    def finish(self, packet_sha, status, result_pin):
        self.session(packet_sha)
        verify_pin(result_pin)
        require(status in ("FAILED_STOP", "COLLECTED_PENDING_ACCEPTANCE"), "Invalid experiment outcome")
        result = read_json(result_pin["path"])
        require(result["status"] == status, "Budget outcome differs from retained result")
        if status == "COLLECTED_PENDING_ACCEPTANCE":
            charges = [r for r in self.charges() if r["packet_sha256"] == packet_sha]
            require([r["test"] for r in charges] == STAGES and all(any(
                r["kind"] == "stage-complete" and r["value"]["charge_sha256"] == digest(charge)
                for r in self.rows) for charge in charges), "Success requires all three charged, fenced stages")
        self.append("finish", {"packet_sha256": packet_sha, "status": status, "result": result_pin})


def validate_conditional_review(packet, approval, packet_sha):
    require(approval["schema"] == "physical-supervisor/conditional-approval-v2", "Wrong conditional approval")
    require(approval["packet_sha256"] == packet_sha and approval["experiment_id"] == packet["experiment_id"],
            "Conditional approval belongs to another experiment")
    require(packet["kind"] == "diagnostic" and packet["automatic_retries"] == 0 and
            [s["name"] for s in packet["stages"]] == STAGES, "Conditional workload expansion")
    grant = authority(packet)
    review = approval["plan_review"]
    require(review["schema"] == "sdvk009-conditional-plan-review/v2" and
            review["grant_sha256"] == digest(grant) and review["packet_sha256"] == packet_sha,
            "Plan review is not bound to the grant/packet")
    future(approval["expires_utc"]); future(review["expires_utc"])
    times = [dt.datetime.fromisoformat(x) for x in (grant["recorded_utc"], packet["created_utc"], review["plan_reviewed_utc"])]
    now = dt.datetime.now(dt.timezone.utc)
    require(all(t.tzinfo is not None for t in times) and max(times[:2]) <= times[2] <= now,
            "Plan review predates its evidence or claims a future decision")
    require("decided_utc" not in approval and "phrase" not in approval,
            "A conditional grant cannot claim a later human exact-packet decision")
    require(review["blocking_findings"] == [] and review["accepted_supervisor_source"] is True and
            set(review["conditions_satisfied"]) >= set(grant["conditions"]), "Conditional prerequisites remain held")
    require(review["reviewer_provenance"].strip() and review["source_acceptance_evidence"] and review["cpu_evidence"],
            "Missing source review or CPU qualification provenance")
    for row in [*review["source_acceptance_evidence"], *review["cpu_evidence"]]:
        verify_pin(row)
    verify_supervisor_source(packet, review["supervisor_source"])
    return grant, review


def verify_supervisor_source(packet, source):
    root = Path(__file__).resolve().parents[2]
    require(Path(source["root"]).resolve(strict=True) == root, "Reviewed supervisor checkout differs")
    commands = [("rev-parse", "HEAD"), ("rev-parse", "HEAD^{tree}"),
                ("status", "--porcelain=v1", "--untracked-files=all")]
    for args, expected in zip(commands, (source["commit"], source["tree"], "")):
        result = subprocess.run([packet["git"], "--no-optional-locks", "-C", str(root), *args],
                                capture_output=True, timeout=10, check=False, env=sealed_environment(packet))
        require(result.returncode == 0 and not result.stderr and result.stdout.decode().strip() == expected,
                "Accepted supervisor source identity changed")
    pinned = {str(Path(row["path"]).resolve()) for row in packet["files"]}
    require(all(str(path.resolve()) in pinned for path in Path(__file__).parent.rglob("*") if path.is_file()),
            "Reviewed supervisor package is not fully pinned")


def boundary_charge(packet, stage):
    """Called once inside the native create callback, while the spawn gate is held."""
    grant = authority(packet)
    with Ledger(grant) as ledger:
        return ledger.reserve(packet["packet_sha256"], stage["name"], packet["stop_root"])


def complete_stage(packet, stage):
    if "conditional_grant" in packet:
        with Ledger(authority(packet)) as ledger:
            ledger.complete(packet["packet_sha256"], stage["name"])


def finish_session(packet, result_pin):
    if "conditional_grant" in packet:
        with Ledger(authority(packet)) as ledger:
            ledger.finish(packet["packet_sha256"], read_json(result_pin["path"])["status"], result_pin)
