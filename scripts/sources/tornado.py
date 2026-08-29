"""Tornado Cash pool balances, read straight off a public Ethereum node.

Fully reproducible: anyone with any Ethereum RPC endpoint gets the same numbers,
with no explorer or indexer in between.
"""

from metrics_core import make_value

from .base import Source, http_post_json

RPC_URL = "https://ethereum-rpc.publicnode.com"
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
