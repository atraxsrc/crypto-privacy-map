import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import unittest

from metrics_core import build_output, make_value, validate_output

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


if __name__ == "__main__":
    unittest.main()
