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
