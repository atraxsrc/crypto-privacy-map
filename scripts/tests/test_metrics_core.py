import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import unittest

from metrics_core import build_output, make_value, validate_output, merge_previous

NOW = "2026-08-29T03:17:44Z"


def ok_record(values=None):
    return {
        "status": "ok",
        "fetched": NOW,
        "source": {"name": "Example", "url": "https://example.org"},
        "values": values or [make_value("pool", "Pool value", 1420000, "coin", unit="ZEC")],
    }


class MakeValueTest(unittest.TestCase):
    def test_builds_minimal_value(self):
        v = make_value("share", "Shielded share", 34.2, "pct")
        self.assertEqual(v, {"key": "share", "label": "Shielded share",
                             "value": 34.2, "format": "pct"})

    def test_includes_optional_unit_and_trend(self):
        v = make_value("pool", "Pool", 5, "coin", unit="ZEC", trend30d=2.1)
        self.assertEqual(v["unit"], "ZEC")
        self.assertEqual(v["trend30d"], 2.1)

    def test_rejects_unknown_format(self):
        with self.assertRaisesRegex(ValueError, "unknown format"):
            make_value("x", "X", 1, "furlongs")

    def test_rejects_non_numeric_value(self):
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            make_value("x", "X", "1", "int")

    def test_rejects_bool_as_value(self):
        # bool is an int subclass in Python; a True here is always a bug.
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            make_value("x", "X", True, "int")

    def test_rejects_non_finite_value(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaisesRegex(ValueError, "must be finite"):
                make_value("x", "X", bad, "int")


class ValidateOutputTest(unittest.TestCase):
    def test_accepts_well_formed_document(self):
        validate_output(build_output({"zcash-shielded": ok_record()}, NOW))

    def test_accepts_unsourced_and_error_records(self):
        out = build_output({
            "pirate-chain": {"status": "unsourced", "reason": "no keyless API"},
            "railgun": {"status": "error", "error": "TimeoutError: timed out"},
        }, NOW)
        validate_output(out)

    def test_rejects_wrong_schema_version(self):
        out = build_output({}, NOW)
        out["schema"] = 2
        with self.assertRaisesRegex(ValueError, "schema"):
            validate_output(out)

    def test_rejects_unknown_status(self):
        with self.assertRaisesRegex(ValueError, "unknown status"):
            validate_output(build_output({"x": {"status": "pending"}}, NOW))

    def test_rejects_ok_record_without_values(self):
        rec = ok_record()
        rec["values"] = []
        with self.assertRaisesRegex(ValueError, "at least one value"):
            validate_output(build_output({"x": rec}, NOW))

    def test_rejects_ok_record_missing_source(self):
        rec = ok_record()
        del rec["source"]
        with self.assertRaisesRegex(ValueError, "source"):
            validate_output(build_output({"x": rec}, NOW))

    def test_rejects_error_record_without_message(self):
        with self.assertRaisesRegex(ValueError, "error"):
            validate_output(build_output({"x": {"status": "error"}}, NOW))

    def test_rejects_malformed_generated_timestamp(self):
        with self.assertRaisesRegex(ValueError, "generated"):
            validate_output(build_output({}, "yesterday"))

    def test_rejects_non_dict_record(self):
        # .get on a non-dict would raise AttributeError, which escapes callers
        # that catch ValueError per this function's documented contract.
        for bad in (None, 42, "ok", []):
            with self.assertRaisesRegex(ValueError, "must be an object"):
                validate_output(build_output({"x": bad}, NOW))

    def test_rejects_non_finite_value_that_bypassed_make_value(self):
        # json.dump would emit a bare Infinity literal here, which is not valid
        # JSON and would make the page's r.json() throw.
        rec = ok_record()
        rec["values"] = [{"key": "x", "label": "X", "value": float("inf"), "format": "int"}]
        with self.assertRaisesRegex(ValueError, "must be finite"):
            validate_output(build_output({"x": rec}, NOW))


class MergePreviousTest(unittest.TestCase):
    OLD = "2026-08-26T03:17:12Z"

    def _previous(self, record):
        return {"schema": 1, "generated": self.OLD, "metrics": {"railgun": record}}

    def test_error_inherits_previous_ok_values(self):
        prev_ok = {
            "status": "ok", "fetched": self.OLD,
            "source": {"name": "DefiLlama", "url": "https://defillama.com"},
            "values": [make_value("tvl", "TVL", 1000, "usd")],
        }
        merged = merge_previous(
            {"railgun": {"status": "error", "error": "boom"}}, self._previous(prev_ok))
        self.assertEqual(merged["railgun"]["lastGood"]["fetched"], self.OLD)
        self.assertEqual(merged["railgun"]["lastGood"]["values"][0]["value"], 1000)

    def test_last_good_carries_across_consecutive_failures(self):
        # Second failure in a row must keep the original good payload and its
        # original age, not silently restamp it as fresh.
        carried = {
            "fetched": self.OLD,
            "source": {"name": "DefiLlama", "url": "https://defillama.com"},
            "values": [make_value("tvl", "TVL", 1000, "usd")],
        }
        prev_err = {"status": "error", "error": "boom", "lastGood": carried}
        merged = merge_previous(
            {"railgun": {"status": "error", "error": "boom again"}}, self._previous(prev_err))
        self.assertEqual(merged["railgun"]["lastGood"], carried)
        self.assertEqual(merged["railgun"]["error"], "boom again")

    def test_error_without_history_gets_no_last_good(self):
        merged = merge_previous({"railgun": {"status": "error", "error": "boom"}}, None)
        self.assertNotIn("lastGood", merged["railgun"])

    def test_ok_record_is_untouched(self):
        rec = ok_record()
        merged = merge_previous({"railgun": rec}, self._previous(ok_record()))
        self.assertEqual(merged["railgun"], rec)
        self.assertNotIn("lastGood", merged["railgun"])

    def test_unsourced_never_gets_last_good(self):
        merged = merge_previous(
            {"railgun": {"status": "unsourced", "reason": "none"}}, self._previous(ok_record()))
        self.assertNotIn("lastGood", merged["railgun"])


if __name__ == "__main__":
    unittest.main()
