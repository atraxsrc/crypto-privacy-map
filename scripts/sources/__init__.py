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
