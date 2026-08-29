"""Shared plumbing for data sources.

Every source is a small module exposing one SOURCE. Sources are deliberately
dumb: fetch, parse, return values, or raise. Isolation, retries, timeouts and
error recording are the runner's job, not theirs.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, List

USER_AGENT = (
    "crypto-privacy-map-metrics/1.0 "
    "(+https://github.com/atraxsrc/crypto-privacy-map)"
)
TIMEOUT_S = 10
RETRIES = 2


@dataclass(frozen=True)
class Source:
    """One upstream data source for one protocol."""

    id: str
    source_name: str
    source_url: str
    fetch: Callable[[], List[dict]]


def _request(url, data=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers)


def _send(req, timeout, retries, opener):
    _open = opener or urllib.request.urlopen
    attempts = retries + 1
    last = None
    for _ in range(attempts):
        try:
            with _open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 4xx is a permanent answer. Retrying wastes the endpoint's
            # goodwill and delays the rest of the run.
            if 400 <= e.code < 500:
                raise RuntimeError(f"{req.full_url} failed: HTTP {e.code}") from e
            last = e
        except (urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError, UnicodeDecodeError) as e:
            last = e
    raise RuntimeError(f"{req.full_url} failed after {attempts} attempts: {last}")


def http_get_json(url, timeout=TIMEOUT_S, retries=RETRIES, opener=None):
    """GET a JSON document. Raises RuntimeError on any unrecoverable failure."""
    return _send(_request(url), timeout, retries, opener)


def http_post_json(url, payload, timeout=TIMEOUT_S, retries=RETRIES, opener=None):
    """POST a JSON body and parse the JSON response. Used for JSON-RPC nodes."""
    body = json.dumps(payload).encode("utf-8")
    return _send(_request(url, data=body), timeout, retries, opener)
