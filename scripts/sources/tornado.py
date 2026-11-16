"""Tornado Cash pool balances, read straight off a public Ethereum node.

Fully reproducible: anyone with any Ethereum RPC endpoint gets the same numbers,
with no explorer or indexer in between.
"""

from metrics_core import make_value

from .base import Source, http_post_json

RPC_URL = "https://ethereum-rpc.publicnode.com"
WEI_PER_ETH = 10 ** 18

# Fixed-denomination ETH pools, one address each. Each pool is its own
# anonymity set, so the card shows them separately as well as summed.
# Addresses carry Etherscan's "Tornado.Cash: <n> ETH" public name tags.
POOLS = {
    "pool-0.1": ("0.1 ETH pool", "0x12D66f87A04A9E220743712cE6d9bB1B5616B8Fc"),
    "pool-1": ("1 ETH pool", "0x47CE0C6eD5B0Ce3d3A51fdb1C52DC66a7c3c2936"),
    "pool-10": ("10 ETH pool", "0x910Cbd523D972eb0a6f4cAe4618aD62622b39DbF"),
    "pool-100": ("100 ETH pool", "0xA160cdAB225685dA1d56aa342Ad8841c3b53f291"),
}


def _balance_call(address):
    return {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance",
            "params": [address, "latest"]}


def parse(responses):
    """Turn {pool_key: rpc_response} into values, total first.

    Raises on any RPC error or missing pool: a partial total would understate
    the pools without saying so.
    """
    values = []
    for key, (label, _address) in POOLS.items():
        if key not in responses:
            raise RuntimeError(f"rpc error for {key}: no response")
        payload = responses[key]
        result = payload.get("result")
        if not result:
            raise RuntimeError(f"rpc error for {key}: {payload.get('error', 'no result')}")
        eth = int(result, 16) / WEI_PER_ETH
        values.append(make_value(key, label, round(eth, 2), "coin", unit="ETH"))
    total = round(sum(v["value"] for v in values), 2)
    return [make_value("pools-total", "All ETH pools", total, "coin", unit="ETH")] + values


def _fetch():
    responses = {key: http_post_json(RPC_URL, _balance_call(address))
                 for key, (_label, address) in POOLS.items()}
    return parse(responses)


SOURCE = Source(
    id="tornado-cash",
    source_name="Ethereum JSON-RPC",
    source_url="https://etherscan.io/accounts/label/tornado-cash",
    fetch=_fetch,
)
