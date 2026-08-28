# Live Metrics Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a nightly, keyless, zero-dependency pipeline that publishes measured privacy metrics to `metrics.json`, and render them beside the hand-set scores on the page without ever altering a score.

**Architecture:** The protocol roster and all editorial content stay inline in the `DATA` array in `index.html`. A Python script run by GitHub Actions writes exactly one file, `metrics.json`, and nothing else. The page renders every card completely from inline data on first paint, then fetches `metrics.json` and re-renders to layer metrics on. Metrics are decoration over an already-complete document, so the site works identically with no network.

**Tech Stack:** Python 3.11+ standard library only (`urllib.request`, `json`, `concurrent.futures`, `unittest`). Vanilla JS/CSS in `index.html`. GitHub Actions. No package manager, no build step, no dependencies, no secrets.

**Spec:** `docs/superpowers/specs/2026-08-29-live-metrics-design.md`

## Global Constraints

- **Python standard library only.** No pip install, no `requirements.txt`, no third-party import. If a task seems to need a package, it is the wrong task.
- **No API keys, tokens, or secrets.** Every endpoint must work unauthenticated. A source that requires registration is dropped and its protocol is listed in `UNSOURCED`.
- **Metrics never affect a score.** No task may read, write, or derive `score`. The 0-10 is hand-set editorial content, permanently.
- **The pipeline writes exactly one file: `metrics.json`.** No task may have the automation modify `index.html`, `README.md`, or any editorial content.
- **The page must render fully with `metrics.json` absent, empty, or malformed.** No error banner, no layout shift, no visible plumbing. Console warning only.
- **No price or market-cap data.** Metrics must be privacy-relevant (pool sizes, shielded shares, transaction counts, TVL). This is not a market tracker.
- **Writing style:** plain hyphens only in all new code, comments, docs, and commit messages. No em-dashes or en-dashes. (Existing `8–10` band labels in `index.html` are pre-existing content; leave them alone.)
- **Run tests with:** `python3 -m unittest discover -s scripts/tests -v`
- **Commit style:** no `Co-Authored-By` trailer. Author is the repo owner.
- **Git note:** `~/.gitconfig` is unreadable in this environment. Prefix git commands with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_AUTHOR_NAME=atraxsrc GIT_AUTHOR_EMAIL=92285717+atraxsrc@users.noreply.github.com GIT_COMMITTER_NAME=atraxsrc GIT_COMMITTER_EMAIL=92285717+atraxsrc@users.noreply.github.com` or commits will fail with "unknown error occurred while reading the configuration files".

## File Structure

| File | Responsibility |
| --- | --- |
| `scripts/protocol_ids.py` | Parse protocol ids out of `index.html`. The page is the roster's single source of truth. |
| `scripts/metrics_core.py` | Pure data-model logic: value construction, document assembly, schema validation, `lastGood` merging. No network, no filesystem. |
| `scripts/sources/base.py` | `Source` dataclass plus HTTP helpers with timeout, retry, and identifying User-Agent. |
| `scripts/sources/<name>.py` | One module per data source. Each exposes a single `SOURCE`. |
| `scripts/sources/__init__.py` | `REGISTRY` (sources) and `UNSOURCED` (ids with no keyless source, each with a reason). |
| `scripts/fetch_metrics.py` | CLI entrypoint and runner: isolation, concurrency, atomic write, exit code. |
| `scripts/tests/*.py` | `unittest` suite. Fully offline; no test touches the network. |
| `scripts/tests/fixtures/*.json` | Recorded upstream responses, so source parsing is tested deterministically. |
| `metrics.json` | Generated. Bot-owned. Never hand-edited. |
| `index.html` | Renders the metrics strip. Human-owned editorial content. |
| `.github/workflows/metrics.yml` | Nightly cron plus manual dispatch. |

Every test file begins with this two-line path shim so the suite runs from any working directory:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
```

---

### Task 1: Protocol ids in DATA, and a parser for them

Gives every protocol a stable key. Names are not stable enough to key `metrics.json` on.

**Files:**
- Modify: `index.html` (the 10 entries in the `DATA` array, starting line 463)
- Create: `scripts/protocol_ids.py`
- Test: `scripts/tests/test_protocol_ids.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ids_from_index_html(path: str | Path) -> list[str]`, raising `ValueError` on an empty or duplicated roster.

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/test_protocol_ids.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import tempfile
import unittest

from protocol_ids import ids_from_index_html

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _write(text):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return tmp.name


class IdsFromIndexHtmlTest(unittest.TestCase):
    def test_extracts_ids_in_document_order(self):
        path = _write('''
          const DATA = [
            { column: "default", id: "monero", name: "Monero" },
            { column: "optin", id: "zcash-shielded", name: "Zcash Shielded" }
          ];
        ''')
        self.assertEqual(ids_from_index_html(path), ["monero", "zcash-shielded"])

    def test_raises_when_no_ids_present(self):
        path = _write("const DATA = [{ name: 'Monero' }];")
        with self.assertRaisesRegex(ValueError, "no protocol ids"):
            ids_from_index_html(path)

    def test_raises_on_duplicate_ids(self):
        path = _write('''
            { id: "monero", name: "Monero" },
            { id: "monero", name: "Monero Again" }
        ''')
        with self.assertRaisesRegex(ValueError, "duplicate protocol ids"):
            ids_from_index_html(path)

    def test_real_index_html_has_ten_unique_ids(self):
        ids = ids_from_index_html(REPO_ROOT / "index.html")
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)
        self.assertIn("monero", ids)
        self.assertIn("zcash-shielded", ids)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'protocol_ids'`

- [ ] **Step 3: Write the parser**

Create `scripts/protocol_ids.py`:

```python
"""Read the protocol roster out of index.html.

The page owns the roster. The pipeline parses ids from it rather than keeping a
second list, so the two can never drift apart.
"""

import re
from pathlib import Path

# Matches an id in either layout: on its own line, or inline after another
# property. Anchoring to a preceding { or , keeps it from matching text that
# merely looks like an id inside a card's prose.
ID_RE = re.compile(r'[{,]\s*id:\s*"([a-z0-9-]+)"\s*,')


def ids_from_index_html(path):
    """Return protocol ids in document order.

    Raises ValueError if the file contains no ids or any duplicates, both of
    which mean the roster is broken rather than empty.
    """
    text = Path(path).read_text(encoding="utf-8")
    ids = ID_RE.findall(text)
    if not ids:
        raise ValueError(f"no protocol ids found in {path}")
    seen, dupes = set(), set()
    for pid in ids:
        if pid in seen:
            dupes.add(pid)
        seen.add(pid)
    if dupes:
        raise ValueError(f"duplicate protocol ids in {path}: {sorted(dupes)}")
    return ids
```

- [ ] **Step 4: Add an `id` to each DATA entry in `index.html`**

In the `DATA` array (starts line 463), add an `id:` as the first property of every
entry, on its own line. The parser accepts either layout, but its own line matches
the surrounding style. The ten ids, in the array's existing order:

```
Monero              -> id: "monero",
Zano                -> id: "zano",
Beldex              -> id: "beldex",
MWC                 -> id: "mwc",
Zcash Shielded      -> id: "zcash-shielded",
Railgun             -> id: "railgun",
Tornado Cash        -> id: "tornado-cash",
Samourai Whirlpool  -> id: "samourai-whirlpool",
Decred CSPP         -> id: "decred-cspp",
Dash PrivateSend    -> id: "dash-privatesend",
```

Each entry becomes, for example:

```js
    {
      id: "monero",
      column: "default", name: "Monero", ticker: "XMR", url: "https://www.getmonero.org",
      reviewed: "2026-06-13",
```

Change nothing else. No score, prose, tag, or date is touched in this task.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, 4 tests

- [ ] **Step 6: Verify the page still renders**

Open `index.html` in a browser. All ten cards render exactly as before; `id` is an
unused property at this point. Confirm no console errors.

- [ ] **Step 7: Commit**

```bash
git add index.html scripts/protocol_ids.py scripts/tests/test_protocol_ids.py
git commit -m "Add stable protocol ids and a parser for the roster"
```

---

### Task 2: Metrics document model and validation

The schema gate. Everything downstream trusts `validate_output`, so it is written first.

**Files:**
- Create: `scripts/metrics_core.py`
- Test: `scripts/tests/test_metrics_core.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `SCHEMA_VERSION: int = 1`, `FORMATS: tuple`, `STATUSES: tuple`
  - `make_value(key, label, value, fmt, unit=None, trend30d=None) -> dict`
  - `build_output(records: dict, generated: str) -> dict`
  - `validate_output(out: dict) -> None`, raising `ValueError`

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/test_metrics_core.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'metrics_core'`

- [ ] **Step 3: Write the implementation**

Create `scripts/metrics_core.py`:

```python
"""Data model for metrics.json.

Pure logic: no network, no filesystem, no clock. Everything here is a function of
its arguments, so the whole module is testable offline and deterministically.
"""

import re

SCHEMA_VERSION = 1
FORMATS = ("pct", "int", "coin", "usd")
STATUSES = ("ok", "unsourced", "error")

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def make_value(key, label, value, fmt, unit=None, trend30d=None):
    """Build one measured value. Raises ValueError on anything unrenderable."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}, expected one of {FORMATS}")
    # bool is a subclass of int; a True reaching the page is always a bug.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"value must be numeric, got {type(value).__name__}")
    out = {"key": key, "label": label, "value": value, "format": fmt}
    if unit is not None:
        out["unit"] = unit
    if trend30d is not None:
        out["trend30d"] = trend30d
    return out


def build_output(records, generated):
    """Assemble the full document from per-protocol records."""
    return {"schema": SCHEMA_VERSION, "generated": generated, "metrics": records}


def _validate_value(v, where):
    for field in ("key", "label", "value", "format"):
        if field not in v:
            raise ValueError(f"{where}: value missing {field!r}")
    if v["format"] not in FORMATS:
        raise ValueError(f"{where}: unknown format {v['format']!r}")
    if isinstance(v["value"], bool) or not isinstance(v["value"], (int, float)):
        raise ValueError(f"{where}: value must be numeric")


def _validate_payload(payload, where):
    """Validate the shared shape of an ok record and a lastGood block."""
    if not isinstance(payload.get("source"), dict):
        raise ValueError(f"{where}: missing source object")
    for field in ("name", "url"):
        if not payload["source"].get(field):
            raise ValueError(f"{where}: source missing {field!r}")
    if not _TS_RE.match(str(payload.get("fetched", ""))):
        raise ValueError(f"{where}: fetched must be an ISO-8601 Z timestamp")
    values = payload.get("values")
    if not isinstance(values, list) or not values:
        raise ValueError(f"{where}: expected at least one value")
    for v in values:
        _validate_value(v, where)


def validate_output(out):
    """Raise ValueError unless out is a well-formed metrics document."""
    if out.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"schema must be {SCHEMA_VERSION}, got {out.get('schema')!r}")
    if not _TS_RE.match(str(out.get("generated", ""))):
        raise ValueError("generated must be an ISO-8601 Z timestamp")
    metrics = out.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")

    for pid, rec in metrics.items():
        status = rec.get("status")
        if status not in STATUSES:
            raise ValueError(f"{pid}: unknown status {status!r}")
        if status == "ok":
            _validate_payload(rec, pid)
        elif status == "unsourced":
            if not rec.get("reason"):
                raise ValueError(f"{pid}: unsourced record needs a reason")
        elif status == "error":
            if not rec.get("error"):
                raise ValueError(f"{pid}: error record needs an error message")
            if rec.get("lastGood") is not None:
                _validate_payload(rec["lastGood"], f"{pid}.lastGood")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, 17 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/metrics_core.py scripts/tests/test_metrics_core.py
git commit -m "Add metrics document model and schema validation"
```

---

### Task 3: lastGood merge, so a failing source degrades to labelled-old

**Files:**
- Modify: `scripts/metrics_core.py`
- Test: `scripts/tests/test_metrics_core.py` (append a new test class)

**Interfaces:**
- Consumes: `metrics_core.build_output` from Task 2.
- Produces: `merge_previous(records: dict, previous: dict | None) -> dict`

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/test_metrics_core.py`, above the `if __name__` block, and
add `merge_previous` to the existing `from metrics_core import ...` line:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ImportError: cannot import name 'merge_previous'`

- [ ] **Step 3: Write the implementation**

Append to `scripts/metrics_core.py`:

```python
def merge_previous(records, previous):
    """Attach lastGood to error records using the previous run's data.

    An error record inherits the newest known-good payload: the previous run's
    ok values, or whatever lastGood that run was already carrying. Preserving
    the original `fetched` across consecutive failures is the point - the page
    must be able to say how old the number really is, so a card degrades to
    labelled-old instead of going blank.
    """
    prev = (previous or {}).get("metrics", {})
    merged = {}
    for pid, rec in records.items():
        if rec.get("status") != "error":
            merged[pid] = rec
            continue
        old = prev.get(pid, {})
        if old.get("status") == "ok":
            good = {"fetched": old["fetched"], "source": old["source"],
                    "values": old["values"]}
        elif old.get("lastGood"):
            good = old["lastGood"]
        else:
            good = None
        merged[pid] = {**rec, "lastGood": good} if good else rec
    return merged
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, 22 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/metrics_core.py scripts/tests/test_metrics_core.py
git commit -m "Carry last good values forward when a source fails"
```

---

### Task 4: HTTP helpers with timeout, bounded retry, and an identifying User-Agent

**Files:**
- Create: `scripts/sources/__init__.py` (empty placeholder for now), `scripts/sources/base.py`
- Test: `scripts/tests/test_sources_base.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Source` frozen dataclass with fields `id`, `source_name`, `source_url`, `fetch`
  - `http_get_json(url, timeout=10, retries=2, opener=None) -> dict | list`
  - `http_post_json(url, payload, timeout=10, retries=2, opener=None) -> dict | list`
  - `USER_AGENT: str`

The `opener` parameter exists so tests inject a fake instead of monkeypatching
`urllib`. No test in this repo touches the network.

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/test_sources_base.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import io
import json
import unittest
import urllib.error

from sources.base import USER_AGENT, Source, http_get_json


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class FakeOpener:
    """Replays a queued script of responses, recording the requests it saw."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.timeouts = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        self.timeouts.append(timeout)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(json.dumps(item).encode("utf-8"))


class HttpGetJsonTest(unittest.TestCase):
    def test_returns_parsed_json(self):
        opener = FakeOpener([{"tvl": 12.5}])
        self.assertEqual(http_get_json("https://x.test/a", opener=opener), {"tvl": 12.5})

    def test_sends_identifying_user_agent(self):
        opener = FakeOpener([{}])
        http_get_json("https://x.test/a", opener=opener)
        self.assertEqual(opener.requests[0].get_header("User-agent"), USER_AGENT)

    def test_passes_timeout_through(self):
        opener = FakeOpener([{}])
        http_get_json("https://x.test/a", timeout=3, opener=opener)
        self.assertEqual(opener.timeouts[0], 3)

    def test_retries_transient_failure_then_succeeds(self):
        opener = FakeOpener([urllib.error.URLError("reset"), {"ok": 1}])
        self.assertEqual(http_get_json("https://x.test/a", opener=opener), {"ok": 1})
        self.assertEqual(len(opener.requests), 2)

    def test_raises_after_exhausting_retries(self):
        opener = FakeOpener([urllib.error.URLError("reset")] * 3)
        with self.assertRaisesRegex(RuntimeError, "failed after 3 attempts"):
            http_get_json("https://x.test/a", retries=2, opener=opener)
        self.assertEqual(len(opener.requests), 3)

    def test_does_not_retry_client_errors(self):
        # A 404 will still be a 404 next time; retrying it only wastes the
        # endpoint's goodwill and delays the run.
        err = urllib.error.HTTPError("https://x.test/a", 404, "Not Found", {}, None)
        opener = FakeOpener([err, {"ok": 1}])
        with self.assertRaisesRegex(RuntimeError, "404"):
            http_get_json("https://x.test/a", opener=opener)
        self.assertEqual(len(opener.requests), 1)

    def test_retries_server_errors(self):
        err = urllib.error.HTTPError("https://x.test/a", 503, "Unavailable", {}, None)
        opener = FakeOpener([err, {"ok": 1}])
        self.assertEqual(http_get_json("https://x.test/a", opener=opener), {"ok": 1})

    def test_raises_on_malformed_json(self):
        class BadOpener:
            def __call__(self, req, timeout=None):
                return FakeResponse(b"<html>nope</html>")

        with self.assertRaises(RuntimeError):
            http_get_json("https://x.test/a", retries=0, opener=BadOpener())


class SourceTest(unittest.TestCase):
    def test_is_frozen(self):
        s = Source(id="x", source_name="N", source_url="https://n.test", fetch=lambda: [])
        with self.assertRaises(Exception):
            s.id = "y"


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources'`

- [ ] **Step 3: Write the implementation**

Create an empty `scripts/sources/__init__.py` (Task 6 fills it in), then create
`scripts/sources/base.py`:

```python
"""Shared plumbing for data sources.

Every source is a small module exposing one SOURCE. Sources are deliberately
dumb: fetch, parse, return values, or raise. Isolation, retries, timeouts and
error recording are the runner's job, not theirs.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, List

USER_AGENT = (
    "crypto-privacy-map-metrics/1.0 "
    "(+https://github.com/atraxsrc/crypto-privacy-map)"
)
TIMEOUT_S = 10
RETRIES = 2


@dataclass(frozen=True)
class Source:
    """One upstream data source for one protocol."""

    id: str
    source_name: str
    source_url: str
    fetch: Callable[[], List[dict]]


def _request(url, data=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers)


def _send(req, timeout, retries, opener):
    _open = opener or urllib.request.urlopen
    attempts = retries + 1
    last = None
    for _ in range(attempts):
        try:
            with _open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 4xx is a permanent answer. Retrying wastes the endpoint's
            # goodwill and delays the rest of the run.
            if 400 <= e.code < 500:
                raise RuntimeError(f"{req.full_url} failed: HTTP {e.code}") from e
            last = e
        except (urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError, UnicodeDecodeError) as e:
            last = e
    raise RuntimeError(f"{req.full_url} failed after {attempts} attempts: {last}")


def http_get_json(url, timeout=TIMEOUT_S, retries=RETRIES, opener=None):
    """GET a JSON document. Raises RuntimeError on any unrecoverable failure."""
    return _send(_request(url), timeout, retries, opener)


def http_post_json(url, payload, timeout=TIMEOUT_S, retries=RETRIES, opener=None):
    """POST a JSON body and parse the JSON response. Used for JSON-RPC nodes."""
    body = json.dumps(payload).encode("utf-8")
    return _send(_request(url, data=body), timeout, retries, opener)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, 31 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/sources/__init__.py scripts/sources/base.py scripts/tests/test_sources_base.py
git commit -m "Add HTTP helpers with timeout, bounded retry, and a named agent"
```

---

### Task 5: The runner - isolation, concurrency, atomic write, exit code

The load-bearing task. One source failing must never fail the run, and a red run must never lose data.

**Files:**
- Create: `scripts/fetch_metrics.py`
- Test: `scripts/tests/test_fetch_metrics.py`

**Interfaces:**
- Consumes: `metrics_core.build_output`, `metrics_core.merge_previous`, `metrics_core.validate_output`, `sources.base.Source`.
- Produces:
  - `run_source(source: Source, now: str) -> tuple[str, dict]`
  - `collect(registry, unsourced: dict, now: str, workers: int = 4) -> dict`
  - `load_previous(path) -> dict | None`
  - `write_atomic(path, data) -> None`
  - `error_ratio(records: dict, registry) -> float`
  - `main(argv=None) -> int`

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/test_fetch_metrics.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetch_metrics'`

- [ ] **Step 3: Write the implementation**

Create `scripts/fetch_metrics.py`:

```python
#!/usr/bin/env python3
"""Fetch privacy metrics and write metrics.json.

Run nightly by .github/workflows/metrics.yml.

Two invariants drive the design. First, one source failing never fails the run:
each source is isolated and degrades into an error record that carries the last
known-good values forward. Second, a red run is a notification and never a
rollback: the file is written before the exit code is decided, so a widespread
outage still preserves history.

Usage:
    python3 scripts/fetch_metrics.py [--dry-run] [--output PATH]
"""

import argparse
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from metrics_core import build_output, merge_previous, validate_output
from sources import REGISTRY, UNSOURCED

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "metrics.json"
MAX_WORKERS = 4
FAILURE_THRESHOLD = 0.5


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_source(source, now):
    """Run one source, converting any failure into an error record."""
    try:
        values = source.fetch()
        if not values:
            raise RuntimeError("source returned no values")
        return source.id, {
            "status": "ok",
            "fetched": now,
            "source": {"name": source.source_name, "url": source.source_url},
            "values": values,
        }
    except Exception as e:  # noqa: BLE001 - isolation is the entire point
        return source.id, {"status": "error", "error": f"{type(e).__name__}: {e}"}


def collect(registry, unsourced, now, workers=MAX_WORKERS):
    """Run every source concurrently, then add the deliberately unsourced ids."""
    records = {}
    if registry:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for pid, rec in pool.map(lambda s: run_source(s, now), registry):
                records[pid] = rec
    for pid, reason in unsourced.items():
        records[pid] = {"status": "unsourced", "reason": reason}
    return records


def load_previous(path):
    """Return the previous document, or None if it is missing or unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_atomic(path, data):
    """Write via a temp file and rename, so readers never see a partial file."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def error_ratio(records, registry):
    """Share of registered sources that errored. Unsourced ids do not count."""
    if not registry:
        return 0.0
    failed = sum(1 for s in registry if records.get(s.id, {}).get("status") == "error")
    return failed / len(registry)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch privacy metrics.")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the document to stdout and write nothing")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="path to metrics.json")
    args = parser.parse_args(argv)

    now = utc_now_iso()
    records = collect(REGISTRY, UNSOURCED, now)
    records = merge_previous(records, load_previous(args.output))
    document = build_output(records, now)
    validate_output(document)

    if args.dry_run:
        json.dump(document, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    write_atomic(args.output, document)

    ratio = error_ratio(records, REGISTRY)
    for pid, rec in sorted(records.items()):
        if rec["status"] == "error":
            print(f"warning: {pid}: {rec['error']}", file=sys.stderr)
    if ratio > FAILURE_THRESHOLD:
        print(f"error: {ratio:.0%} of sources failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, 46 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_metrics.py scripts/tests/test_fetch_metrics.py
git commit -m "Add metrics runner with source isolation and atomic writes"
```

---

### Task 6: The registry, and a coverage test that makes roster drift fail

The mechanism that stops the page and the pipeline from silently diverging.

**Files:**
- Modify: `scripts/sources/__init__.py`
- Test: `scripts/tests/test_registry_coverage.py`

**Interfaces:**
- Consumes: `protocol_ids.ids_from_index_html`, `sources.base.Source`.
- Produces: `sources.REGISTRY: tuple[Source, ...]`, `sources.UNSOURCED: dict[str, str]`

At this task the registry is still empty; Task 7 populates it. Every one of the ten
ids therefore starts life in `UNSOURCED`, and Task 7 moves five of them across.

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/test_registry_coverage.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import unittest

from protocol_ids import ids_from_index_html
from sources import REGISTRY, UNSOURCED

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class RegistryCoverageTest(unittest.TestCase):
    def setUp(self):
        self.page_ids = set(ids_from_index_html(REPO_ROOT / "index.html"))
        self.source_ids = {s.id for s in REGISTRY}

    def test_no_id_is_both_sourced_and_unsourced(self):
        self.assertEqual(self.source_ids & set(UNSOURCED), set())

    def test_every_page_protocol_is_classified(self):
        # Adding a protocol to index.html must force a deliberate decision about
        # whether it has a keyless data source. Silence is not an answer.
        missing = self.page_ids - self.source_ids - set(UNSOURCED)
        self.assertEqual(missing, set(),
                         f"protocols in index.html with no source and no UNSOURCED entry: {sorted(missing)}")

    def test_registry_has_no_ids_the_page_does_not_have(self):
        extra = (self.source_ids | set(UNSOURCED)) - self.page_ids
        self.assertEqual(extra, set(),
                         f"classified ids that no longer exist in index.html: {sorted(extra)}")

    def test_every_unsourced_entry_states_a_reason(self):
        for pid, reason in UNSOURCED.items():
            self.assertTrue(reason and len(reason) > 10,
                            f"{pid}: UNSOURCED needs a real reason, got {reason!r}")

    def test_source_ids_are_unique(self):
        self.assertEqual(len(self.source_ids), len(REGISTRY))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ImportError: cannot import name 'REGISTRY' from 'sources'`

- [ ] **Step 3: Write the registry**

Replace the contents of `scripts/sources/__init__.py`:

```python
"""Source registry.

REGISTRY holds protocols we can measure with a keyless public endpoint.
UNSOURCED holds protocols we have looked at and cannot measure that way, each
with the reason. Together they must cover every id in index.html exactly, which
test_registry_coverage.py enforces - so adding a protocol to the page forces an
explicit decision here rather than silently producing a card with no metrics.
"""

REGISTRY = ()

UNSOURCED = {
    "monero": "pending: source added in a later task",
    "zano": "no keyless public API for transaction or pool statistics",
    "beldex": "no keyless public explorer API found",
    "mwc": "no keyless public explorer API found",
    "zcash-shielded": "pending: source added in a later task",
    "railgun": "pending: source added in a later task",
    "tornado-cash": "pending: source added in a later task",
    "samourai-whirlpool": "coordinator seized in 2024; no live public statistics",
    "decred-cspp": "mixing participation is not exposed by a keyless endpoint",
    "dash-privatesend": "PrivateSend usage is not exposed by a keyless endpoint",
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, 51 tests

- [ ] **Step 5: Verify the runner produces a complete document**

Run: `python3 scripts/fetch_metrics.py --dry-run`
Expected: JSON on stdout with `"schema": 1` and ten `"unsourced"` records. Exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/sources/__init__.py scripts/tests/test_registry_coverage.py
git commit -m "Add source registry with enforced roster coverage"
```

---

### Task 7: Real data sources

Each source is verified against the live endpoint once, its response recorded as a fixture, and its parser tested against that fixture forever after.

**Files:**
- Create: `scripts/sources/tornado.py`, `scripts/sources/defillama.py`, `scripts/sources/zcash.py`, `scripts/sources/monero.py`
- Create: `scripts/tests/fixtures/*.json`
- Modify: `scripts/sources/__init__.py`
- Test: `scripts/tests/test_sources_parsers.py`

**Interfaces:**
- Consumes: `sources.base.Source`, `sources.base.http_get_json`, `sources.base.http_post_json`, `metrics_core.make_value`.
- Produces: a module-level `SOURCE` in each source module, and for each a pure parser `parse(payload) -> list[dict]` that the tests exercise directly.

**Separating `parse` from `fetch` is the point of this task.** `fetch` does the network
call and hands the payload to `parse`; tests only ever call `parse`. That is what
keeps the suite offline and deterministic while still covering the logic that breaks
when an upstream changes shape.

- [ ] **Step 1: Verify each endpoint by hand before writing any code**

For each candidate below, run the probe and confirm three things: it returns
without any credential, its terms permit automated nightly use, and the field you
intend to read is actually present.

```bash
# Tornado Cash - pool balances via a public Ethereum JSON-RPC node.
# The 100 ETH pool contract. eth_getBalance returns wei as a hex string.
curl -s -X POST https://eth.llamarpc.com \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getBalance",
       "params":["0xA160cdAB225685dA1d56aa342Ad8841c3b53f291","latest"]}'

# Railgun and Aztec - DefiLlama, keyless.
curl -s https://api.llama.fi/protocol/railgun | head -c 400
curl -s https://api.llama.fi/protocol/aztec  | head -c 400

# Zcash - shielded pool value. Confirm which fields the endpoint actually exposes.
curl -s 'https://api.blockchair.com/zcash/stats' | head -c 600

# Monero - daily transaction count.
curl -s 'https://api.blockchair.com/monero/stats' | head -c 600
```

**If a probe needs a key, is rate-limited to uselessness, or forbids automated
use, drop that source.** Leave its id in `UNSOURCED` with the real reason and move
on. Half the roster being unsourced is an expected outcome of the keyless
constraint, not a problem to engineer around. Do not substitute a keyed endpoint.

- [ ] **Step 2: Record fixtures from the probes**

Save each successful probe response verbatim:

```bash
mkdir -p scripts/tests/fixtures
curl -s https://api.llama.fi/protocol/railgun > scripts/tests/fixtures/defillama_railgun.json
curl -s 'https://api.blockchair.com/zcash/stats' > scripts/tests/fixtures/blockchair_zcash.json
# ...one per source that survived step 1
```

For the RPC source, hand-write `scripts/tests/fixtures/rpc_balance.json` in the
exact shape the node returned, for example:

```json
{ "jsonrpc": "2.0", "id": 1, "result": "0x21e19e0c9bab2400000" }
```

- [ ] **Step 3: Write the failing parser tests**

Create `scripts/tests/test_sources_parsers.py`. Adjust the field paths to match
what step 1 actually returned; the assertions below assume the documented shapes.

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import json
import unittest

from sources import defillama, tornado

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TornadoParseTest(unittest.TestCase):
    def test_converts_hex_wei_to_ether(self):
        # 0x21e19e0c9bab2400000 wei == 10000 ETH
        values = tornado.parse({"pool-100": load("rpc_balance.json")})
        self.assertEqual(values[0]["format"], "coin")
        self.assertEqual(values[0]["unit"], "ETH")
        self.assertAlmostEqual(values[0]["value"], 10000.0, places=6)

    def test_raises_on_rpc_error_response(self):
        with self.assertRaisesRegex(RuntimeError, "rpc error"):
            tornado.parse({"pool-100": {"error": {"code": -32000, "message": "nope"}}})

    def test_raises_when_result_is_missing(self):
        with self.assertRaisesRegex(RuntimeError, "rpc error"):
            tornado.parse({"pool-100": {"jsonrpc": "2.0", "id": 1}})


class DefiLlamaParseTest(unittest.TestCase):
    def test_extracts_current_tvl(self):
        values = defillama.parse(load("defillama_railgun.json"))
        self.assertEqual(values[0]["key"], "tvl")
        self.assertEqual(values[0]["format"], "usd")
        self.assertGreater(values[0]["value"], 0)

    def test_raises_when_tvl_series_is_empty(self):
        with self.assertRaisesRegex(RuntimeError, "no TVL"):
            defillama.parse({"name": "Railgun", "tvl": []})

    def test_raises_when_payload_has_no_tvl_key(self):
        with self.assertRaisesRegex(RuntimeError, "no TVL"):
            defillama.parse({"name": "Railgun"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ImportError: cannot import name 'defillama' from 'sources'`

- [ ] **Step 5: Write the source modules**

Create `scripts/sources/tornado.py`:

```python
"""Tornado Cash pool balances, read straight off a public Ethereum node.

Fully reproducible: anyone with any Ethereum RPC endpoint gets the same numbers,
with no explorer or indexer in between.
"""

from metrics_core import make_value

from .base import Source, http_post_json

RPC_URL = "https://eth.llamarpc.com"
WEI_PER_ETH = 10 ** 18

# Fixed-denomination ETH pools. Address per denomination.
POOLS = {
    "pool-100": ("100 ETH pool", "0xA160cdAB225685dA1d56aa342Ad8841c3b53f291"),
}


def _balance_call(address):
    return {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance",
            "params": [address, "latest"]}


def parse(responses):
    """Turn {pool_key: rpc_response} into values. Raises on any RPC error."""
    values = []
    for key, (label, _address) in POOLS.items():
        payload = responses[key]
        result = payload.get("result")
        if not result:
            raise RuntimeError(f"rpc error for {key}: {payload.get('error', 'no result')}")
        eth = int(result, 16) / WEI_PER_ETH
        values.append(make_value(key, label, round(eth, 2), "coin", unit="ETH"))
    return values


def _fetch():
    responses = {key: http_post_json(RPC_URL, _balance_call(address))
                 for key, (_label, address) in POOLS.items()}
    return parse(responses)


SOURCE = Source(
    id="tornado-cash",
    source_name="Ethereum JSON-RPC",
    source_url="https://etherscan.io/address/0xA160cdAB225685dA1d56aa342Ad8841c3b53f291",
    fetch=_fetch,
)
```

Create `scripts/sources/defillama.py`:

```python
"""TVL from DefiLlama, which serves its protocol endpoints without a key.

One parser, two sources: Railgun and Aztec differ only by slug.
"""

from metrics_core import make_value

from .base import Source, http_get_json

API = "https://api.llama.fi/protocol/{slug}"


def parse(payload):
    """Read the latest point of the TVL series."""
    series = payload.get("tvl") or []
    if not series:
        raise RuntimeError(f"no TVL series in payload for {payload.get('name', '?')}")
    latest = series[-1]
    tvl = latest.get("totalLiquidityUSD")
    if tvl is None:
        raise RuntimeError("no TVL value in latest series point")
    return [make_value("tvl", "Value in pool", round(float(tvl), 2), "usd")]


def _make(protocol_id, slug):
    def _fetch():
        return parse(http_get_json(API.format(slug=slug)))

    return Source(
        id=protocol_id,
        source_name="DefiLlama",
        source_url=f"https://defillama.com/protocol/{slug}",
        fetch=_fetch,
    )


RAILGUN = _make("railgun", "railgun")
AZTEC = _make("aztec", "aztec")
```

Note: `AZTEC` is defined now but must not be added to `REGISTRY` until Aztec
exists in `index.html`, or `test_registry_coverage` fails. It joins the registry
in the editorial plan that adds the protocol.

Create `scripts/sources/zcash.py` and `scripts/sources/monero.py` following the
same three-part shape - a module docstring naming the endpoint, a pure `parse`,
and a `SOURCE` - using the exact field names the step 1 probe returned. Each
`parse` must raise `RuntimeError` with a readable message when its field is
absent, so an upstream shape change becomes an `error` record with `lastGood`
rather than a crash or a silently wrong number.

- [ ] **Step 6: Move the newly sourced ids out of UNSOURCED**

In `scripts/sources/__init__.py`, import the modules, list their sources, and
delete the matching `UNSOURCED` entries. Only include sources whose probe in
step 1 actually succeeded:

```python
# Import only the modules you actually created in step 5.
from . import defillama, monero, tornado, zcash

REGISTRY = (
    tornado.SOURCE,
    defillama.RAILGUN,
    zcash.SOURCE,
    monero.SOURCE,
)

UNSOURCED = {
    "zano": "no keyless public API for transaction or pool statistics",
    "beldex": "no keyless public explorer API found",
    "mwc": "no keyless public explorer API found",
    "samourai-whirlpool": "coordinator seized in 2024; no live public statistics",
    "decred-cspp": "mixing participation is not exposed by a keyless endpoint",
    "dash-privatesend": "PrivateSend usage is not exposed by a keyless endpoint",
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS. `test_registry_coverage` confirms the ten ids are still exactly covered.

- [ ] **Step 8: Generate the first real metrics.json**

Run: `python3 scripts/fetch_metrics.py`
Expected: exit 0, `metrics.json` created. Inspect it:

```bash
python3 -m json.tool metrics.json | head -40
```

Confirm real numbers for the sourced protocols and `unsourced` records with
reasons for the rest.

- [ ] **Step 9: Commit**

```bash
git add scripts/sources/ scripts/tests/fixtures/ scripts/tests/test_sources_parsers.py metrics.json
git commit -m "Add keyless metric sources for Tornado, Railgun, Zcash and Monero"
```

---

### Task 8: Render the metrics strip

**Files:**
- Modify: `index.html` - CSS after line 220 (`.card-foot.stale .dot`), markup at line 416 (before `</section>`) and 438-446 (footer), JS at 593 (`cardHTML`) and 650-656 (bootstrap)

**Interfaces:**
- Consumes: `metrics.json` as produced by Task 7.
- Produces: no exported interface. This is the final consumer.

- [ ] **Step 1: Add the CSS**

Insert after line 220 (`.card-foot.stale .dot { ... }`), before the
`/* ── METHODOLOGY ── */` comment:

```css
    /* ── LIVE METRICS ──
       Deliberately unlike .card-foot. Review freshness is a claim about human
       judgment; metric freshness is a claim about a cron job. Sharing dots or
       chips between them would imply a card was re-read when a bot merely
       re-pinged an API. */
    .metrics { margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--tn-border); }
    .metrics.aged { opacity: .5; }
    .metric { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; font-size: 10.5px; line-height: 1.85; }
    .metric-label { color: var(--tn-comment); }
    .metric-value { color: var(--tn-fg-bright); font-variant-numeric: tabular-nums; white-space: nowrap; }
    .metric-trend { font-size: 9px; margin-left: 5px; }
    .metric-trend.up { color: var(--tn-green); }
    .metric-trend.down { color: var(--tn-red); }
    .metrics-age { margin-top: 6px; font-size: 9px; color: var(--tn-comment); opacity: .8; }
```

- [ ] **Step 2: Add the footer slot**

Replace the footer block at lines 438-446 with:

```html
  <footer>
    <span>// @atraxsrc</span>
    <span class="sep">|</span>
    <span>Last reviewed: <span class="updated" id="last-reviewed"></span></span>
    <span class="sep">|</span>
    <span id="stale-summary"></span>
    <span class="sep" id="metrics-sep" hidden>|</span>
    <span id="metrics-age" hidden></span>
    <span class="sep">|</span>
    <span>Not financial advice</span>
  </footer>
```

Both new spans start `hidden` so that when `metrics.json` is unreachable the
footer shows no dangling separator and no empty slot.

- [ ] **Step 3: Add the explanatory note**

Insert immediately before the `</section>` that closes the methodology block
(line 416, after the `.bands` div):

```html
    <p class="lead" style="margin-top:22px">
      Live figures are measured nightly from public, key-free sources and are shown
      only where such a source exists; many privacy protocols publish no usable
      endpoint, so their cards carry no measured figures. Measured values never
      change a score - scores stay hand-set.
    </p>
```

- [ ] **Step 4: Add the rendering JS**

Insert after `function isStale(p) { ... }` (line 591):

```js
  /* ── live metrics (see metrics.json, written nightly by CI) ── */
  const METRICS_URL = "metrics.json";
  const METRIC_AGED_DAYS = 7;   // past this, the strip dims and says how old it is
  let METRICS = null;

  function compactNum(n) {
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (abs >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(Math.round(n * 100) / 100);
  }

  function fmtMetric(v) {
    if (v.format === "pct") return v.value.toFixed(1) + "%";
    if (v.format === "usd") return "$" + compactNum(v.value);
    if (v.format === "coin") return compactNum(v.value) + (v.unit ? " " + v.unit : "");
    return compactNum(v.value);
  }

  function relTime(iso) {
    const hours = (Date.now() - new Date(iso).getTime()) / 3600000;
    if (!isFinite(hours)) return "unknown";
    if (hours < 1) return "just now";
    if (hours < 48) return Math.round(hours) + "h ago";
    return Math.round(hours / 24) + "d ago";
  }

  function metricsHTML(rec) {
    if (!rec) return "";
    let values = null, fetched = null;
    if (rec.status === "ok") {
      values = rec.values; fetched = rec.fetched;
    } else if (rec.status === "error" && rec.lastGood) {
      values = rec.lastGood.values; fetched = rec.lastGood.fetched;
    }
    // unsourced, or an error with no history: render nothing at all. A
    // permanent empty slot reads as a bug; absence is explained once in the
    // methodology note, not repeated on every card.
    if (!values || !values.length) return "";

    const ageDays = (Date.now() - new Date(fetched).getTime()) / DAY_MS;
    const aged = ageDays > METRIC_AGED_DAYS;
    const rows = values.map((v) => {
      let trend = "";
      if (typeof v.trend30d === "number" && v.trend30d !== 0) {
        const dir = v.trend30d > 0 ? "up" : "down";
        const arrow = v.trend30d > 0 ? "▲" : "▼";
        trend = `<span class="metric-trend ${dir}">${arrow} ${esc(Math.abs(v.trend30d).toFixed(1))}</span>`;
      }
      return `<div class="metric"><span class="metric-label">${esc(v.label)}</span>` +
             `<span class="metric-value">${esc(fmtMetric(v))}${trend}</span></div>`;
    }).join("");

    return `<div class="metrics${aged ? " aged" : ""}">${rows}` +
           `<div class="metrics-age">measured ${esc(relTime(fetched))}</div></div>`;
  }

  function metricFor(id) {
    return METRICS && METRICS.metrics ? METRICS.metrics[id] : null;
  }

  function loadMetrics() {
    fetch(METRICS_URL, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then((data) => {
        if (!data || data.schema !== 1 || !data.metrics) {
          throw new Error("unexpected metrics schema");
        }
        METRICS = data;
        const age = document.getElementById("metrics-age");
        age.textContent = "Metrics " + relTime(data.generated);
        age.hidden = false;
        document.getElementById("metrics-sep").hidden = false;
        render();
      })
      .catch((e) => console.warn("[privacy-map] metrics unavailable:", e.message));
  }
```

- [ ] **Step 5: Hook the strip into the card**

In `cardHTML` (line 593), insert `${metricsHTML(metricFor(p.id))}` between
`${tags}` and `${reviewed}` in the returned template:

```js
        ${tags}
        ${metricsHTML(metricFor(p.id))}
        ${reviewed}
```

Then add `loadMetrics();` on the line immediately after the existing `render();`
call at line 656:

```js
  render();
  loadMetrics();
```

The order matters: `render()` paints everything from inline `DATA` first, so the
first paint never waits on the network. `loadMetrics()` only ever adds to an
already-complete page.

- [ ] **Step 6: Verify the offline path**

```bash
mv metrics.json /tmp/metrics.json.bak
python3 -m http.server 8000
```

Open `http://localhost:8000`. The page must look **exactly** as it did before this
task: all cards present, no metrics strips, no dangling `|` in the footer, no
error banner. The console shows one warning: `[privacy-map] metrics unavailable: HTTP 404`.

- [ ] **Step 7: Verify all three metric states**

```bash
mv /tmp/metrics.json.bak metrics.json
```

Hand-edit a working copy so it contains one `ok` record, one `error` record with a
`lastGood` whose `fetched` is 10 days old, and one `unsourced` record. Reload and
confirm: the `ok` card shows values plus "measured Nh ago"; the `error` card shows
the old values dimmed (`.aged`) with "measured 10d ago"; the `unsourced` card shows
no strip at all. Restore the real file afterwards with
`python3 scripts/fetch_metrics.py`.

- [ ] **Step 8: Commit**

```bash
git add index.html
git commit -m "Render live metrics beside the hand-set scores"
```

---

### Task 9: Nightly CI

**Files:**
- Create: `.github/workflows/metrics.yml`

**Interfaces:**
- Consumes: `scripts/fetch_metrics.py`.
- Produces: nightly commits touching only `metrics.json`.

- [ ] **Step 1: Write the workflow**

```yaml
name: metrics

on:
  schedule:
    # 03:17 UTC. Off the hour on purpose: public endpoints get hammered by
    # every cron scheduled at :00.
    - cron: "17 3 * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: metrics
  cancel-in-progress: false

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # No setup-python and no install step: the runner ships a usable Python 3
      # and the pipeline has no dependencies.
      - name: Run test suite
        run: python3 -m unittest discover -s scripts/tests -v

      - name: Fetch metrics
        id: fetch
        continue-on-error: true
        run: python3 scripts/fetch_metrics.py

      - name: Commit if changed
        run: |
          if git diff --quiet -- metrics.json; then
            echo "no metric changes"
            exit 0
          fi
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add metrics.json
          git commit -m "chore(metrics): nightly refresh"
          git push

      - name: Surface widespread source failure
        if: steps.fetch.outcome == 'failure'
        run: |
          echo "More than half the sources failed. Data was still written and"
          echo "committed, so lastGood is preserved. Check the fetch step log."
          exit 1
```

`continue-on-error` on the fetch step plus the final check is what makes a red run
a notification rather than a rollback: the commit always happens, and the job still
ends red so the failure is visible.

- [ ] **Step 2: Verify the workflow parses**

```bash
python3 -c "
import json, sys
try:
    import yaml
except ImportError:
    print('pyyaml absent - checking indentation only')
    sys.exit(0)
print(json.dumps(yaml.safe_load(open('.github/workflows/metrics.yml')), indent=2)[:400])
"
```

If PyYAML is absent, skip the check. Do not install it - the no-dependency rule
applies to tooling too. GitHub validates the file on push.

- [ ] **Step 3: Commit and trigger a real run**

```bash
git add .github/workflows/metrics.yml
git commit -m "Add nightly metrics workflow"
git push
```

Then in the repository's Actions tab, run **metrics** via `workflow_dispatch`.

- [ ] **Step 4: Verify the run end to end**

Confirm: the test step passed; the fetch step wrote real values; either a commit
named `chore(metrics): nightly refresh` appeared or the log says "no metric
changes"; and the live site at `https://atraxsrc.github.io/crypto-privacy-map/`
shows metric strips after the Pages deploy completes.

---

### Task 10: Correct the README

The README currently advertises an automated watch agent that opens PRs. No such workflow exists. Now that a real one does, the claim gets replaced with the truth.

**Files:**
- Modify: `README.md` (the "Staying current" and "Updating the data" sections)

- [ ] **Step 1: Replace the false automation claim**

In "Staying current", replace the `**Automated watch**` bullet with:

```markdown
- **Nightly metrics** - a GitHub Action fetches measured figures (pool balances,
  shielded shares, transaction counts) from public, key-free sources and commits
  them to `metrics.json`. The page layers these onto the cards. Measured data
  never changes a score: scores stay hand-set. Protocols with no keyless public
  source simply carry no measured figures.
```

- [ ] **Step 2: Document the pipeline**

Add after "Updating the data":

````markdown
## The metrics pipeline

`metrics.json` is generated. Do not edit it by hand.

```bash
python3 scripts/fetch_metrics.py --dry-run     # print, write nothing
python3 scripts/fetch_metrics.py               # write metrics.json
python3 -m unittest discover -s scripts/tests  # run the tests
```

Python 3 standard library only - no dependencies, no API keys, no secrets.

To add a protocol: add its entry to `DATA` in `index.html` with a unique `id`,
then classify that id in `scripts/sources/__init__.py` as either a source in
`REGISTRY` or an entry in `UNSOURCED` with a reason. `test_registry_coverage`
fails until you do, which is deliberate.
````

- [ ] **Step 3: Verify no stale claims remain**

```bash
grep -n "cloud agent\|opens a PR\|opens an issue" README.md
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Describe the metrics pipeline and drop the unbuilt watch-agent claim"
```

---

## Out of scope: the editorial expansion

The spec's editorial workstream - adding roughly ten protocols and re-verifying the
six stale entries - is **deliberately not in this plan**. It is research work gated
on verifying current facts against live sources, not code work that can be driven by
a failing test, and mixing the two would produce a plan whose tasks cannot all be
verified the same way. It gets its own plan.

Two things this plan leaves ready for it: `scripts/sources/defillama.py` already
defines `AZTEC`, unused until Aztec exists in `index.html`; and
`test_registry_coverage` will fail the moment a new protocol is added without a
sourced/unsourced decision, which is the intended forcing function.

## Verification

The whole plan is done when all of these hold:

```bash
python3 -m unittest discover -s scripts/tests -v   # all tests pass
python3 scripts/fetch_metrics.py --dry-run          # valid document, exit 0
grep -c 'id: "' index.html                         # 10 protocol ids
```

- The Actions run for **metrics** is green and has committed a `metrics.json`.
- The live site renders metric strips on sourced cards and nothing on unsourced ones.
- Deleting `metrics.json` and reloading gives a page identical to today's, with one
  console warning and no visible error.
- No score in `DATA` differs from its value before this work started.
