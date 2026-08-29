"""Monero daily transaction count from the Coin Metrics community API.

The community tier is keyless and rate-limited but ample for one nightly call.
Blockchair's Monero stats endpoint was the first candidate and was dropped: it
exposes a cumulative transaction total but no 24h count, and a lifetime total
says nothing about current usage.

The series is ascending by time, so the newest complete day is the last point.
"""

from metrics_core import make_value

from .base import Source, http_get_json

API = (
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    "?assets=xmr&metrics=TxCnt&frequency=1d&page_size=3"
)


def parse(payload):
    """Read TxCnt from the newest point of the series."""
    series = payload.get("data") or []
    if not series:
        raise RuntimeError("no transaction count: empty series")
    raw = series[-1].get("TxCnt")
    if raw is None:
        raise RuntimeError("no transaction count in the newest series point")
    try:
        count = int(float(raw))
    except (TypeError, ValueError):
        raise RuntimeError(f"transaction count is not a number: {raw!r}") from None
    return [make_value("tx_24h", "Transactions per day", count, "int")]


def _fetch():
    return parse(http_get_json(API))


SOURCE = Source(
    id="monero",
    source_name="Coin Metrics",
    source_url="https://charts.coinmetrics.io/network-data/",
    fetch=_fetch,
)
