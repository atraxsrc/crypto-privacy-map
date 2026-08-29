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
            # allow_nan=False: a non-finite value must fail loudly here rather
            # than ship a metrics.json the browser cannot parse.
            json.dump(data, f, indent=2, sort_keys=True, allow_nan=False)
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
