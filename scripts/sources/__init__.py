"""Source registry.

REGISTRY holds protocols we can measure with a keyless public endpoint.
UNSOURCED holds protocols we have looked at and cannot measure that way, each
with the reason. Together they must cover every id in index.html exactly, which
test_registry_coverage.py enforces - so adding a protocol to the page forces an
explicit decision here rather than silently producing a card with no metrics.
"""

from . import defillama, monero, tornado, zcash

REGISTRY = (
    tornado.SOURCE,
    defillama.RAILGUN,
    defillama.PRIVACY_POOLS,
    monero.SOURCE,
    zcash.SOURCE,
)

UNSOURCED = {
    "zano": "no keyless public API for transaction or pool statistics",
    "beldex": "no keyless public explorer API found",
    "mwc": "no keyless public explorer API found",
    "samourai-whirlpool": "coordinator seized in 2024; no live public statistics",
    "decred-cspp": "mixing participation is not exposed by a keyless endpoint",
    "pirate-chain": "explorer exposes no JSON API for supply or usage",
    "grin": "scan.grin.money serves price and hashrate only; no usage metric",
    "firo": "public explorers expose no Spark pool or usage figures",
    "litecoin-mweb": "litecoinspace.org block data carries no MWEB balance; published figures conflict",
    "dash-privatesend": "CoinJoin (formerly PrivateSend) usage is not exposed by a keyless endpoint",
}
