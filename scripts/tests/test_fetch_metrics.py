import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import json
import tempfile
import unittest
from pathlib import Path

import fetch_metrics
from metrics_core import make_value, validate_output
from sources.base import Source

NOW = "2026-08-29T03:17:44Z"


def good(pid, value=1.0):
    return Source(id=pid, source_name="Example", source_url="https://example.org",
                  fetch=lambda: [make_value("v", "V", value, "usd")])


def broken(pid, exc=None):
    def _boom():
        raise exc or RuntimeError("upstream is down")
    return Source(id=pid, source_name="Example", source_url="https://example.org",
                  fetch=_boom)


def empty(pid):
    return Source(id=pid, source_name="Example", source_url="https://example.org",
                  fetch=lambda: [])


class RunSourceTest(unittest.TestCase):
    def test_success_produces_ok_record(self):
        pid, rec = fetch_metrics.run_source(good("monero"), NOW)
        self.assertEqual(pid, "monero")
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(rec["fetched"], NOW)
        self.assertEqual(rec["source"]["name"], "Example")

    def test_exception_becomes_error_record_naming_the_type(self):
        _, rec = fetch_metrics.run_source(broken("monero", ValueError("bad shape")), NOW)
        self.assertEqual(rec["status"], "error")
        self.assertIn("ValueError", rec["error"])
        self.assertIn("bad shape", rec["error"])

    def test_empty_value_list_is_an_error_not_a_success(self):
        # An ok record with no values would render an empty metrics strip,
        # which looks like a broken card rather than an absent source.
        _, rec = fetch_metrics.run_source(empty("monero"), NOW)
        self.assertEqual(rec["status"], "error")
        self.assertIn("no values", rec["error"])


class CollectTest(unittest.TestCase):
    def test_one_broken_source_does_not_stop_the_others(self):
        records = fetch_metrics.collect([good("a"), broken("b"), good("c")], {}, NOW)
        self.assertEqual(records["a"]["status"], "ok")
        self.assertEqual(records["b"]["status"], "error")
        self.assertEqual(records["c"]["status"], "ok")

    def test_unsourced_entries_are_emitted_with_their_reason(self):
        records = fetch_metrics.collect([], {"grin": "no public API"}, NOW)
        self.assertEqual(records["grin"], {"status": "unsourced", "reason": "no public API"})

    def test_output_passes_validation(self):
        records = fetch_metrics.collect([good("a"), broken("b")], {"c": "none"}, NOW)
        validate_output({"schema": 1, "generated": NOW, "metrics": records})


class LoadPreviousTest(unittest.TestCase):
    def test_returns_none_when_file_is_missing(self):
        self.assertIsNone(fetch_metrics.load_previous("/nonexistent/metrics.json"))

    def test_returns_none_when_file_is_malformed(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        self.assertIsNone(fetch_metrics.load_previous(f.name))

    def test_reads_a_valid_document(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"schema": 1, "generated": NOW, "metrics": {}}, f)
        self.assertEqual(fetch_metrics.load_previous(f.name)["generated"], NOW)


class WriteAtomicTest(unittest.TestCase):
    def test_writes_readable_json_and_leaves_no_temp_files(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "metrics.json"
            fetch_metrics.write_atomic(target, {"schema": 1})
            self.assertEqual(json.loads(target.read_text())["schema"], 1)
            self.assertEqual(list(Path(d).iterdir()), [target])


class ErrorRatioTest(unittest.TestCase):
    def test_counts_only_registered_sources(self):
        records = {"a": {"status": "ok"}, "b": {"status": "error"},
                   "c": {"status": "unsourced"}}
        self.assertEqual(fetch_metrics.error_ratio(records, [good("a"), broken("b")]), 0.5)

    def test_empty_registry_is_not_a_failure(self):
        self.assertEqual(fetch_metrics.error_ratio({}, []), 0.0)


class MainTest(unittest.TestCase):
    def setUp(self):
        self._registry = fetch_metrics.REGISTRY
        self._unsourced = fetch_metrics.UNSOURCED

    def tearDown(self):
        fetch_metrics.REGISTRY = self._registry
        fetch_metrics.UNSOURCED = self._unsourced

    def test_dry_run_writes_nothing(self):
        fetch_metrics.REGISTRY = [good("a")]
        fetch_metrics.UNSOURCED = {}
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "metrics.json"
            code = fetch_metrics.main(["--dry-run", "--output", str(target)])
            self.assertEqual(code, 0)
            self.assertFalse(target.exists())

    def test_majority_failure_still_writes_but_exits_nonzero(self):
        # A red run is a notification, never a rollback: the file must land so
        # lastGood survives to the next run.
        fetch_metrics.REGISTRY = [broken("a"), broken("b"), good("c")]
        fetch_metrics.UNSOURCED = {}
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "metrics.json"
            code = fetch_metrics.main(["--output", str(target)])
            self.assertEqual(code, 1)
            self.assertTrue(target.exists())
            validate_output(json.loads(target.read_text()))

    def test_healthy_run_exits_zero(self):
        fetch_metrics.REGISTRY = [good("a"), good("b")]
        fetch_metrics.UNSOURCED = {}
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "metrics.json"
            self.assertEqual(fetch_metrics.main(["--output", str(target)]), 0)


if __name__ == "__main__":
    unittest.main()
