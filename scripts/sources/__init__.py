"""Source registry.

REGISTRY holds protocols we can measure with a keyless public endpoint.
UNSOURCED holds protocols we have looked at and cannot measure that way, each
with the reason. Together they must cover every id in index.html exactly, which
test_registry_coverage.py enforces - so adding a protocol to the page forces an
explicit decision here rather than silently producing a card with no metrics.
"""

from . import defillama, monero, tornado

REGISTRY = (
    tornado.SOURCE,
    defillama.RAILGUN,
    monero.SOURCE,
)

UNSOURCED = {
    "zano": "no keyless public API for transaction or pool statistics",
    "beldex": "no keyless public explorer API found",
    "mwc": "no keyless public explorer API found",
    "zcash-shielded": "no keyless endpoint exposes shielded pool value; Blockchair's Zcash stats carry no shielded fields and the Coin Metrics community tier has no shielded metrics for ZEC",
    "samourai-whirlpool": "coordinator seized in 2024; no live public statistics",
    "decred-cspp": "mixing participation is not exposed by a keyless endpoint",
    "dash-privatesend": "PrivateSend usage is not exposed by a keyless endpoint",
}
