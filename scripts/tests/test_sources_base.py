import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import io
import json
import unittest
import urllib.error

from sources.base import USER_AGENT, Source, http_get_json


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class FakeOpener:
    """Replays a queued script of responses, recording the requests it saw."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.timeouts = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        self.timeouts.append(timeout)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(json.dumps(item).encode("utf-8"))


class HttpGetJsonTest(unittest.TestCase):
    def test_returns_parsed_json(self):
        opener = FakeOpener([{"tvl": 12.5}])
        self.assertEqual(http_get_json("https://x.test/a", opener=opener), {"tvl": 12.5})

    def test_sends_identifying_user_agent(self):
        opener = FakeOpener([{}])
        http_get_json("https://x.test/a", opener=opener)
        self.assertEqual(opener.requests[0].get_header("User-agent"), USER_AGENT)

    def test_passes_timeout_through(self):
        opener = FakeOpener([{}])
        http_get_json("https://x.test/a", timeout=3, opener=opener)
        self.assertEqual(opener.timeouts[0], 3)

    def test_retries_transient_failure_then_succeeds(self):
        opener = FakeOpener([urllib.error.URLError("reset"), {"ok": 1}])
        self.assertEqual(http_get_json("https://x.test/a", opener=opener), {"ok": 1})
        self.assertEqual(len(opener.requests), 2)

    def test_raises_after_exhausting_retries(self):
        opener = FakeOpener([urllib.error.URLError("reset")] * 3)
        with self.assertRaisesRegex(RuntimeError, "failed after 3 attempts"):
            http_get_json("https://x.test/a", retries=2, opener=opener)
        self.assertEqual(len(opener.requests), 3)

    def test_does_not_retry_client_errors(self):
        # A 404 will still be a 404 next time; retrying it only wastes the
        # endpoint's goodwill and delays the run.
        err = urllib.error.HTTPError("https://x.test/a", 404, "Not Found", {}, None)
        opener = FakeOpener([err, {"ok": 1}])
        with self.assertRaisesRegex(RuntimeError, "404"):
            http_get_json("https://x.test/a", opener=opener)
        self.assertEqual(len(opener.requests), 1)

    def test_retries_server_errors(self):
        err = urllib.error.HTTPError("https://x.test/a", 503, "Unavailable", {}, None)
        opener = FakeOpener([err, {"ok": 1}])
        self.assertEqual(http_get_json("https://x.test/a", opener=opener), {"ok": 1})

    def test_raises_on_malformed_json(self):
        class BadOpener:
            def __call__(self, req, timeout=None):
                return FakeResponse(b"<html>nope</html>")

        with self.assertRaises(RuntimeError):
            http_get_json("https://x.test/a", retries=0, opener=BadOpener())


class SourceTest(unittest.TestCase):
    def test_is_frozen(self):
        s = Source(id="x", source_name="N", source_url="https://n.test", fetch=lambda: [])
        with self.assertRaises(Exception):
            s.id = "y"


if __name__ == "__main__":
    unittest.main()
