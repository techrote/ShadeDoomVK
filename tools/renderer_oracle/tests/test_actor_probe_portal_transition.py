"""SDVK-010 linked-portal actor transition scene-assertion negatives."""
from __future__ import annotations

import copy
import unittest

from tools.renderer_oracle import run
from tools.renderer_oracle.common import EvidenceError


def actor(tid, source, presentation, source_sector, render_sector, target, authored, thru,
          source_group, render_group, runtime, context, epoch=7):
    return {"kind": "probe", "data": {
        "material": "SDVTA0", "authored_index": authored, "runtime_irradiance_index": runtime,
        "fallback": runtime == 0, "probe_epoch": epoch,
        "resource": {"available": runtime != 0}, "context": context,
        "actor_selection": {
            "available": True, "actor_tid": tid, "actor_position": source,
            "presentation_position": presentation, "source_sector": source_sector,
            "render_sector": render_sector, "sector_target": target,
            "authored_index": authored, "policy": "portal-sector-conservative",
            "through_portal_mode": thru,
            "source_portal_group": source_group, "render_portal_group": render_group,
            "portal_group_count": 3, "portal_ambiguous": True, "spatial": False,
            "selected": True, "portal_mirrored": False,
        }}}


SPEC = {
    "material": "SDVTA0", "minimum_draws": 3, "require_live": True,
    "require_distinct_runtime_pairs": True,
    "samples": [
        {"role": "before", "actor_tid": 5100, "actor_position": [-112, 0, 0],
         "presentation_position": [-112, 0, 0], "source_sector": 0, "render_sector": 0,
         "sector_target": 0, "authored_index": 0, "policy": "portal-sector-conservative",
         "through_portal_mode": 0, "group_relation": "same", "portal_mirrored": False,
         "context_type": "main", "context_producer": "root", "context_depth": 0,
         "context_position": [-320, 0, 64], "context_mirrored": False},
        {"role": "on", "actor_tid": 5101, "actor_position": [1088, -24, 0],
         "presentation_position": [1088, -24, 0], "source_sector": 1, "render_sector": 1,
         "sector_target": 1, "authored_index": 1, "policy": "portal-sector-conservative",
         "through_portal_mode": 0, "group_relation": "same", "portal_mirrored": False,
         "context_type": "portal", "context_producer": "LineToLine", "context_depth": 1,
         "context_position": [704, 0, 64], "context_mirrored": False},
        {"role": "after", "actor_tid": 5102, "actor_position": [1184, 24, 0],
         "presentation_position": [1184, 24, 0], "source_sector": 1, "render_sector": 1,
         "sector_target": 1, "authored_index": 1, "policy": "portal-sector-conservative",
         "through_portal_mode": 0, "group_relation": "same", "portal_mirrored": False,
         "context_type": "portal", "context_producer": "LineToLine", "context_depth": 1,
         "context_position": [704, 0, 64], "context_mirrored": False},
    ],
}


def good_rows():
    root = {"type": "main", "producer": "root", "depth": 0,
            "position": [-320, 0, 64], "mirrored": False}
    portal = {"type": "portal", "producer": "LineToLine", "depth": 1,
              "position": [704, 0, 64], "mirrored": False}
    return [
        actor(5100, [-112, 0, 0], [-112, 0, 0], 0, 0, 0, 0, 0, 1, 1, 701, root),
        actor(5101, [1088, -24, 0], [1088, -24, 0], 1, 1, 1, 1, 0, 2, 2, 713, portal),
        actor(5102, [1184, 24, 0], [1184, 24, 0], 1, 1, 1, 1, 0, 2, 2, 713, portal),
    ]


class PortalRepeatabilityProjection(unittest.TestCase):
    def test_only_unrelated_floor_generation_and_texture_epoch_are_normalized(self):
        base = [
            {"kind": "material", "data": {"name": "SDVFL", "resource": {
                "available": True, "index": 259, "generation": 3, "epoch": 2, "span": 4}}},
            {"kind": "resource", "data": {"texture_epoch": 3, "probe_epoch": 2}},
            {"kind": "probe", "data": {"probe_epoch": 2, "resource": {
                "available": True, "index": 267, "generation": 1, "epoch": 2, "span": 2}}},
        ]
        other = copy.deepcopy(base)
        other[0]["data"]["resource"]["generation"] = 4
        other[1]["data"]["texture_epoch"] = 4
        self.assertEqual(run._portal_probe_repeatability_projection(base),
                         run._portal_probe_repeatability_projection(other))

    def test_probe_and_nonfloor_identity_remain_exact(self):
        base = [
            {"kind": "material", "data": {"name": "SDVTA0", "resource": {
                "available": True, "index": 300, "generation": 2, "epoch": 2, "span": 4}}},
            {"kind": "probe", "data": {"probe_epoch": 2, "resource": {
                "available": True, "index": 267, "generation": 1, "epoch": 2, "span": 2}}},
        ]
        for mutate in (
            lambda rows: rows[0]["data"]["resource"].update(generation=3),
            lambda rows: rows[1]["data"]["resource"].update(generation=2),
            lambda rows: rows[1]["data"].update(probe_epoch=3),
            lambda rows: rows[1]["data"]["resource"].update(epoch=3),
        ):
            other = copy.deepcopy(base)
            mutate(other)
            with self.subTest(other=other):
                self.assertNotEqual(run._portal_probe_repeatability_projection(base),
                                    run._portal_probe_repeatability_projection(other))


class PortalActorProbeAssertions(unittest.TestCase):
    def test_before_on_after_positive(self):
        selected = run._portal_actor_probe_assertions(good_rows(), SPEC)
        self.assertEqual([sample["role"] for sample, _ in selected], ["before", "on", "after"])

    def test_adversarial_transition_controls_reject(self):
        mutations = {
            "nearest-cross-group": lambda rows: rows[1]["data"]["actor_selection"].update(policy="spatial-nearest", spatial=True),
            "wrong-sector-target": lambda rows: rows[1]["data"]["actor_selection"].update(sector_target=0),
            "wrong-through-mode": lambda rows: rows[1]["data"]["actor_selection"].update(through_portal_mode=1),
            "double-transform": lambda rows: rows[1]["data"]["actor_selection"].update(presentation_position=[64, -24, 0]),
            "wrong-context": lambda rows: rows[1]["data"]["context"].update(producer="root", depth=0),
            "double-context-transform": lambda rows: rows[1]["data"]["context"].update(position=[1728, 0, 64]),
            "ordinal-zero-conflation": lambda rows: rows[0]["data"].update(authored_index=-1),
            "stale-epoch": lambda rows: rows[2]["data"].update(probe_epoch=8),
            "missing-sample": lambda rows: rows.pop(1),
            "sample-association": lambda rows: rows[1]["data"]["actor_selection"].update(actor_tid=5102),
            "cross-group-substitution": lambda rows: rows[1]["data"].update(runtime_irradiance_index=701),
            "wrong-group-relation": lambda rows: rows[1]["data"]["actor_selection"].update(render_portal_group=1),
        }
        for name, mutate in mutations.items():
            rows = good_rows()
            mutate(rows)
            with self.subTest(name=name), self.assertRaises(EvidenceError):
                run._portal_actor_probe_assertions(rows, SPEC)

    def test_runtime_zero_is_rejected_only_when_live_pair_is_required(self):
        rows = good_rows()
        rows[1]["data"].update(runtime_irradiance_index=0, fallback=True, resource={"available": False})
        rows[2]["data"].update(runtime_irradiance_index=0, fallback=True, resource={"available": False})
        with self.assertRaisesRegex(EvidenceError, "published runtime probe pair"):
            run._portal_actor_probe_assertions(rows, SPEC)
        fallback = copy.deepcopy(SPEC)
        fallback["require_live"] = False
        fallback["require_distinct_runtime_pairs"] = False
        run._portal_actor_probe_assertions(rows, fallback)


if __name__ == "__main__":
    unittest.main()
