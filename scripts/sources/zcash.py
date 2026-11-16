"""Zcash shielded value, from a public zcashd/zebra getblockchaininfo mirror.

zcashexplorer.app serves the node's getblockchaininfo verbatim and keyless.
Every value pool except the transparent pool and the protocol-held lockbox
holds shielded user funds. Counting by exclusion means a new shielded pool
(as Ironwood was in 2026) is included automatically rather than silently
dropped from the total.
"""

from metrics_core import make_value

from .base import Source, http_get_json

API = "https://mainnet.zcashexplorer.app/api/v1/blockchain-info"
ZAT_PER_ZEC = 10 ** 8
NOT_SHIELDED = ("transparent", "lockbox")


def parse(payload):
    """Return shielded ZEC and its share of total supply."""
    pools = payload.get("valuePools") or []
    supply = (payload.get("chainSupply") or {}).get("chainValueZat")
    if not pools or not supply:
        raise RuntimeError("no value pools or chain supply in payload")
    shielded_zat = 0
    for pool in pools:
        if pool.get("id") in NOT_SHIELDED:
            continue
        # An unmonitored pool has an unknown balance; counting it as zero
        # would understate the shielded total without saying so.
        if not pool.get("monitored") or pool.get("chainValueZat") is None:
            raise RuntimeError(f"pool {pool.get('id')!r} is not monitored")
        shielded_zat += int(pool["chainValueZat"])
    if shielded_zat <= 0:
        raise RuntimeError("no shielded value found")
    return [
        make_value("shielded", "Shielded ZEC", round(shielded_zat / ZAT_PER_ZEC, 2), "coin", unit="ZEC"),
        make_value("shielded-share", "Share of supply shielded",
                   round(shielded_zat / int(supply) * 100, 2), "pct"),
    ]


def _fetch():
    return parse(http_get_json(API))


SOURCE = Source(
    id="zcash-shielded",
    source_name="Zcash node (zcashexplorer.app)",
    source_url="https://mainnet.zcashexplorer.app",
    fetch=_fetch,
)
