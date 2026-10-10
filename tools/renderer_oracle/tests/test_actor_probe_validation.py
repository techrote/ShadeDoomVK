"""SDVK-010 native emitted actor-probe evidence adversarial validation."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.renderer_oracle import validate, common


def selection(*, authored=1, policy="spatial-nearest", portal=False, distance=9.0):
    return {"available": True, "contract": "sdvk-010-actor-ordinal/v1", "policy": policy,
            "selected": authored >= 0, "spatial": policy in ("spatial-nearest", "no-probe-in-radius"),
            "authored_index": authored, "sector_target": 0, "candidate_count": 2,
            "distance_squared": distance, "actor_position": [90, 96, 112],
            "source_portal_group": 1, "render_portal_group": 2 if portal else 1,
            "through_portal_mode": 1 if portal else 0, "portal_mirrored": False,
            "coordinate_space": "source-level-doom-xyz",
            "publication_policy": "PF-113 zero when selected pair absent; no alternate probe"}


class ActorProbeValidation(unittest.TestCase):
    def check(self, row, authored=1, runtime=701):
        validate._actor_probe_selection(row, authored, runtime)

    def test_spatial_live_and_missing_publication_both_remain_one_ordinal(self):
        self.check(selection(), 1, 701)
        self.check(selection(), 1, 0)  # absent pair => PF-113 runtime zero
        self.check(selection(authored=0), 0, 713)  # authored 0 != descriptor 0

    def test_portal_sector_target_and_true_no_probe_fallback(self):
        self.check(selection(authored=0, portal=True, policy="portal-sector-conservative", distance=-1), 0, 701)
        self.check(selection(authored=-1, policy="no-probe-in-radius", distance=-1), -1, 0)
        none = selection(authored=-1, policy="no-probes", distance=-1)
        none.update(candidate_count=0, spatial=False)
        self.check(none, -1, 0)

    def test_negative_mismatch_stale_slot_portal_crossing_and_zero_substitution(self):
        bad = [
            (dict(authored_index=0), 1, 701),
            (dict(candidate_count=1), 1, 701),
            (dict(distance_squared=512.0 * 512.0 + 1), 1, 701),
            (dict(selected=False), 1, 701),
            (dict(source_portal_group=2), 1, 701),
            (dict(coordinate_space="transformed-view"), 1, 701),
            (dict(publication_policy="replace absent with nearest available"), 1, 701),
            (dict(actor_position=[float('nan'),0,0]), 1, 701),
            (dict(spatial=False), 1, 701),
        ]
        for edit, authored, runtime in bad:
            s = selection()
            s.update(edit)
            with self.subTest(edit=edit), self.assertRaises(common.EvidenceError):
                self.check(s, authored, runtime)
        missing = selection(authored=-1, policy="no-probe-in-radius", distance=-1)
        with self.assertRaisesRegex(common.EvidenceError, "Absent actor probe"):
            self.check(missing, -1, 725)

    def test_incorrect_portal_sector_fallback_rejected(self):
        s = selection(authored=1, portal=True, policy="portal-sector-conservative", distance=-1)
        with self.assertRaisesRegex(common.EvidenceError, "ignored sector target"):
            self.check(s, 1, 701)
        s['authored_index'] = 0
        self.check(s, 0, 701)
        s['spatial'] = True
        with self.assertRaises(common.EvidenceError):
            self.check(s, 0, 701)


if __name__ == '__main__':
    unittest.main()
