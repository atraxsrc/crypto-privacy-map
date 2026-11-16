import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import json
import unittest

from sources import defillama, monero, tornado

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TornadoParseTest(unittest.TestCase):
    def all_pools(self, **override):
        responses = {key: load("rpc_balance.json") for key in tornado.POOLS}
        responses.update(override)
        return responses

    def test_converts_hex_wei_to_ether(self):
        # 0x21e19e0c9bab2400000 wei == 10000 ETH
        values = tornado.parse(self.all_pools())
        per_pool = {v["key"]: v for v in values}
        self.assertEqual(per_pool["pool-100"]["format"], "coin")
        self.assertEqual(per_pool["pool-100"]["unit"], "ETH")
        self.assertAlmostEqual(per_pool["pool-100"]["value"], 10000.0, places=6)

    def test_total_comes_first_and_sums_every_pool(self):
        values = tornado.parse(self.all_pools())
        self.assertEqual(values[0]["key"], "pools-total")
        self.assertAlmostEqual(values[0]["value"], 10000.0 * len(tornado.POOLS), places=6)
        self.assertEqual(len(values), len(tornado.POOLS) + 1)

    def test_raises_on_rpc_error_response(self):
        with self.assertRaisesRegex(RuntimeError, "rpc error"):
            tornado.parse(self.all_pools(**{"pool-100": {"error": {"code": -32000, "message": "nope"}}}))

    def test_raises_when_result_is_missing(self):
        with self.assertRaisesRegex(RuntimeError, "rpc error"):
            tornado.parse(self.all_pools(**{"pool-100": {"jsonrpc": "2.0", "id": 1}}))

    def test_raises_when_a_pool_is_missing(self):
        # A silent partial total would understate the pools.
        responses = self.all_pools()
        del responses["pool-10"]
        with self.assertRaisesRegex(RuntimeError, "pool-10"):
            tornado.parse(responses)


class DefiLlamaParseTest(unittest.TestCase):
    def test_extracts_current_tvl(self):
        values = defillama.parse(load("defillama_railgun.json"))
        self.assertEqual(values[0]["key"], "tvl")
        self.assertEqual(values[0]["format"], "usd")
        self.assertGreater(values[0]["value"], 0)

    def test_raises_when_tvl_series_is_empty(self):
        with self.assertRaisesRegex(RuntimeError, "no TVL"):
            defillama.parse({"name": "Railgun", "tvl": []})

    def test_raises_when_payload_has_no_tvl_key(self):
        with self.assertRaisesRegex(RuntimeError, "no TVL"):
            defillama.parse({"name": "Railgun"})


class MoneroParseTest(unittest.TestCase):
    def test_reads_the_most_recent_daily_transaction_count(self):
        values = monero.parse(load("coinmetrics_monero.json"))
        self.assertEqual(values[0]["key"], "tx_24h")
        self.assertEqual(values[0]["format"], "int")
        # The series is ascending by time, so the newest point is the last one.
        self.assertEqual(values[0]["value"], 28347)

    def test_raises_when_the_series_is_empty(self):
        with self.assertRaisesRegex(RuntimeError, "no transaction count"):
            monero.parse({"data": []})

    def test_raises_when_the_metric_is_absent_from_the_point(self):
        with self.assertRaisesRegex(RuntimeError, "no transaction count"):
            monero.parse({"data": [{"asset": "xmr", "time": "2026-08-28T00:00:00Z"}]})

    def test_raises_when_the_count_is_not_a_number(self):
        # CoinMetrics serialises counts as strings, so a shape change here is
        # easy to miss without an explicit guard.
        with self.assertRaisesRegex(RuntimeError, "transaction count"):
            monero.parse({"data": [{"TxCnt": "not-a-number"}]})


if __name__ == "__main__":
    unittest.main()
