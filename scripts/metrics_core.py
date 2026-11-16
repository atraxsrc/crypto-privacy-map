"""Data model for metrics.json.

Pure logic: no network, no filesystem, no clock. Everything here is a function of
its arguments, so the whole module is testable offline and deterministically.
"""

import math
import re
from datetime import date, datetime, timedelta

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
    # NaN and the infinities are numeric but not JSON. json.dump writes them as
    # bare NaN/Infinity literals, which JSON.parse rejects - so one bad average
    # upstream would take the whole metrics strip off the page.
    if not math.isfinite(value):
        raise ValueError(f"value must be finite, got {value!r}")
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
    if not math.isfinite(v["value"]):
        raise ValueError(f"{where}: value must be finite")


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
        # Without this, a None or int slot raises AttributeError from .get and
        # escapes callers that catch ValueError per this function's contract.
        if not isinstance(rec, dict):
            raise ValueError(f"{pid}: record must be an object, got {type(rec).__name__}")
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


# ── history and trends ────────────────────────────────────────────────
#
# metrics-history.json stores {protocol_id: {value_key: [[YYYY-MM-DD, value], ...]}}
# with a point appended only when the value changes. The series is therefore a
# step function: the value in force on any day is the newest point on or
# before it. Storing changes rather than days keeps the file (and the nightly
# commit) quiet when nothing moved.

HISTORY_DAYS = 45
TREND_DAYS = 30


def _as_date(day):
    return date.fromisoformat(day)


def update_history(history, records, today):
    """Return a new history with today's ok values folded in, then pruned.

    A point is appended only when the value differs from the newest stored
    one. Pruning drops points older than HISTORY_DAYS but keeps the newest
    point before the cutoff, since it still defines the value in force at
    the start of the window.
    """
    out = {pid: {k: [list(p) for p in pts] for k, pts in keys.items()}
           for pid, keys in (history or {}).items()}
    for pid, rec in records.items():
        if rec.get("status") != "ok":
            continue
        for v in rec["values"]:
            pts = out.setdefault(pid, {}).setdefault(v["key"], [])
            if pts and pts[-1][0] == today:
                pts[-1][1] = v["value"]
            elif not pts or pts[-1][1] != v["value"]:
                pts.append([today, v["value"]])
    cutoff = _as_date(today) - timedelta(days=HISTORY_DAYS)
    for keys in out.values():
        for k, pts in keys.items():
            old = [p for p in pts if _as_date(p[0]) < cutoff]
            keys[k] = old[-1:] + [p for p in pts if _as_date(p[0]) >= cutoff]
    return out


def trend_from_history(points, current, today, days=TREND_DAYS):
    """Percent change against the value in force `days` ago.

    None when the history does not reach back that far (a young series must
    not fake a trend) or the base is zero.
    """
    target = _as_date(today) - timedelta(days=days)
    base = None
    for day, value in points or []:
        if _as_date(day) <= target:
            base = value
        else:
            break
    if base is None or base == 0:
        return None
    return round((current - base) / abs(base) * 100, 1)


def attach_trends(records, history, today):
    """Set trend30d on every ok value that has enough history. In place."""
    for pid, rec in records.items():
        if rec.get("status") != "ok":
            continue
        for v in rec["values"]:
            t = trend_from_history(history.get(pid, {}).get(v["key"]), v["value"], today)
            if t is not None and math.isfinite(t):
                v["trend30d"] = t
            else:
                v.pop("trend30d", None)
    return records


def _strip_times(obj):
    if isinstance(obj, dict):
        return {k: _strip_times(v) for k, v in obj.items() if k not in ("generated", "fetched")}
    if isinstance(obj, list):
        return [_strip_times(x) for x in obj]
    return obj


def is_material_change(previous, document, max_quiet_days=6):
    """True if document differs from previous in anything but timestamps.

    Also true once the previous document is max_quiet_days old, so the
    page's "metrics Xd ago" never ages past its dimming threshold just
    because the upstream numbers held still.
    """
    if not previous:
        return True
    if _strip_times(previous) != _strip_times(document):
        return True
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        age = (datetime.strptime(document["generated"], fmt)
               - datetime.strptime(previous["generated"], fmt))
    except (KeyError, TypeError, ValueError):
        return True
    return age >= timedelta(days=max_quiet_days)
