import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import unittest

from metrics_core import (attach_trends, is_material_change, make_value,
                          trend_from_history, update_history)


def ok(value, key="tvl"):
    return {"status": "ok", "fetched": "2026-11-17T03:17:00Z",
            "source": {"name": "X", "url": "https://x.org"},
            "values": [make_value(key, "Value", value, "usd")]}


class UpdateHistoryTest(unittest.TestCase):
    def test_first_value_starts_a_series(self):
        h = update_history({}, {"a": ok(100)}, "2026-11-01")
        self.assertEqual(h, {"a": {"tvl": [["2026-11-01", 100]]}})

    def test_unchanged_value_adds_no_point(self):
        h = update_history({"a": {"tvl": [["2026-11-01", 100]]}}, {"a": ok(100)}, "2026-11-02")
        self.assertEqual(h["a"]["tvl"], [["2026-11-01", 100]])

    def test_changed_value_appends(self):
        h = update_history({"a": {"tvl": [["2026-11-01", 100]]}}, {"a": ok(120)}, "2026-11-02")
        self.assertEqual(h["a"]["tvl"], [["2026-11-01", 100], ["2026-11-02", 120]])

    def test_second_run_same_day_overwrites(self):
        h = update_history({"a": {"tvl": [["2026-11-02", 100]]}}, {"a": ok(130)}, "2026-11-02")
        self.assertEqual(h["a"]["tvl"], [["2026-11-02", 130]])

    def test_non_ok_records_are_ignored(self):
        h = update_history({}, {"a": {"status": "error", "error": "x"},
                                "b": {"status": "unsourced", "reason": "y"}}, "2026-11-02")
        self.assertEqual(h, {})

    def test_prune_keeps_newest_point_before_cutoff(self):
        old = [["2026-08-01", 1], ["2026-09-01", 2], ["2026-11-01", 3]]
        h = update_history({"a": {"tvl": old}}, {}, "2026-11-17")
        # cutoff is 45 days back (2026-10-03): 09-01 still defines the value then
        self.assertEqual(h["a"]["tvl"], [["2026-09-01", 2], ["2026-11-01", 3]])

    def test_input_is_not_mutated(self):
        src = {"a": {"tvl": [["2026-11-01", 100]]}}
        update_history(src, {"a": ok(120)}, "2026-11-02")
        self.assertEqual(src, {"a": {"tvl": [["2026-11-01", 100]]}})


class TrendTest(unittest.TestCase):
    def test_none_when_history_is_younger_than_window(self):
        self.assertIsNone(trend_from_history([["2026-11-01", 100]], 150, "2026-11-17"))

    def test_uses_value_in_force_thirty_days_ago(self):
        pts = [["2026-09-01", 50], ["2026-10-10", 100], ["2026-11-10", 200]]
        # 30 days before 11-17 is 10-18; the value in force then is 100
        self.assertEqual(trend_from_history(pts, 110, "2026-11-17"), 10.0)

    def test_negative_change(self):
        self.assertEqual(trend_from_history([["2026-10-01", 200]], 150, "2026-11-17"), -25.0)

    def test_zero_base_gives_none(self):
        self.assertIsNone(trend_from_history([["2026-10-01", 0]], 5, "2026-11-17"))

    def test_attach_sets_and_clears(self):
        rec = {"a": ok(110), "b": ok(5)}
        rec["b"]["values"][0]["trend30d"] = 9.9  # stale value must not survive
        hist = {"a": {"tvl": [["2026-10-01", 100]]}, "b": {"tvl": [["2026-11-10", 5]]}}
        attach_trends(rec, hist, "2026-11-17")
        self.assertEqual(rec["a"]["values"][0]["trend30d"], 10.0)
        self.assertNotIn("trend30d", rec["b"]["values"][0])


class MaterialChangeTest(unittest.TestCase):
    def doc(self, generated, value=1, fetched=None):
        r = ok(value)
        r["fetched"] = fetched or generated
        return {"schema": 1, "generated": generated, "metrics": {"a": r}}

    def test_no_previous_is_a_change(self):
        self.assertTrue(is_material_change(None, self.doc("2026-11-17T03:00:00Z")))

    def test_timestamps_alone_are_not_a_change(self):
        prev = self.doc("2026-11-16T03:00:00Z")
        self.assertFalse(is_material_change(prev, self.doc("2026-11-17T03:00:00Z")))

    def test_value_change_is_a_change(self):
        prev = self.doc("2026-11-16T03:00:00Z", value=1)
        self.assertTrue(is_material_change(prev, self.doc("2026-11-17T03:00:00Z", value=2)))

    def test_quiet_for_six_days_forces_a_write(self):
        prev = self.doc("2026-11-11T03:00:00Z")
        self.assertTrue(is_material_change(prev, self.doc("2026-11-17T03:00:00Z")))


if __name__ == "__main__":
    unittest.main()
