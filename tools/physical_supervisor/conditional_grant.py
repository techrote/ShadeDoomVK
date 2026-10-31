"""CPU-only draft for truthful conditional-grant resolution and finite budgets.

Outputs are deliberately NOT v1 approvals and cannot release the current gate.
Execution integration and independent source review remain separate work.
"""
import datetime as dt
import hashlib
import re

from .common import canonical, future, require


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
