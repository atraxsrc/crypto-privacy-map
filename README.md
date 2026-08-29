```
┌──────────────────────────────────────────────────────────────────────┐
│  crypto-privacy-map                                                  │
│  DEFAULT vs OPT-IN: the truth behind the protocols                   │
├──────────────────────────────────────────────────────────────────────┤
│  privacy that is on by default beats privacy you have to opt into.   │
│  if people CAN skip privacy, most of them will, and a small          │
│  anonymity set protects no one.                                      │
└──────────────────────────────────────────────────────────────────────┘
```

[![metrics](https://github.com/atraxsrc/crypto-privacy-map/actions/workflows/metrics.yml/badge.svg)](https://github.com/atraxsrc/crypto-privacy-map/actions/workflows/metrics.yml)

🔗 **Live:** https://atraxsrc.github.io/crypto-privacy-map/

A single-page, visual map that grades crypto privacy protocols by how much privacy
they actually deliver - not by marketing.

---

```
$ ./map --show
```

Protocols are split into two columns and scored `0-10`:

```
  🔒 PRIVATE BY DEFAULT ── every tx is private, no user action
     monero ......................... 10/10   ring sigs · stealth · RingCT
     zano ...........................  7/10   ring sigs · confidential assets
     beldex .........................  6/10   monero fork · RingCT
     mwc ............................  6/10   mimblewimble · no on-chain addrs

  ⚠  OPT-IN PRIVACY ── user must choose; most txs stay public
     zcash-shielded .................  8/10   zk-SNARKs · sapling / orchard
     railgun ........................  7/10   zk-SNARKs · DeFi privacy layer
     tornado-cash ...................  7/10   zk-SNARK mixer · ETH / ERC-20
     samourai-whirlpool .............  5/10   coinjoin · equal-output mixing
     decred-cspp ....................  5/10   coinshuffle++ · stakeshuffle
     dash-privatesend ...............  4/10   coinjoin · masternode mixing
```

> Snapshot only - `index.html` is authoritative.

Each card carries a privacy grade, the underlying tech, key caveats, status tags
(legal risk, adoption, etc.), and the date it was last reviewed.

---

```
$ ./score --explain
```

Scores are an **opinionated synthesis**, not a precise metric. They rank real-world
privacy across five factors:

```
  [1] default vs opt-in ....... ▉▉▉▉▉  always-on beats chosen (biggest factor)
  [2] anonymity set ........... ▉▉▉▉   how large a crowd you blend into
  [3] crypto strength ......... ▉▉▉    ring sigs, zk-SNARKs, mimblewimble, coinjoin
  [4] real adoption ........... ▉▉▉    what share of txs are actually private
  [5] maturity & standing ..... ▉▉     battle-testing, audits, legal health

  BANDS   8-10 HIGH  ·  6-7 MEDIUM  ·  4-5 LOW
```

The full breakdown lives in the *How the scores work* section on the page.

---

```
$ ./map --status
```

The privacy landscape shifts fast - sanctions, arrests, delistings, adoption swings -
so the project is built to stay fresh:

- **Data-driven** - every protocol lives in one `DATA` array in `index.html`. Update a
  score or fact in one line; the grade colour and bar derive from the score automatically.
- **Per-entry review dates** - each entry has a `reviewed` date. Anything older than
  `STALE_AFTER_DAYS` (180) is flagged with a *Review due* chip, and the footer tallies how
  many entries need a refresh.
- **Nightly metrics** - a GitHub Action fetches measured figures (pool balances,
  shielded shares, transaction counts) from public, key-free sources and commits
  them to `metrics.json`. The page layers these onto the cards. Measured data
  never changes a score: scores stay hand-set. Protocols with no keyless public
  source simply carry no measured figures.

---

```
$ vim index.html
```

1. Open `index.html` and find the `DATA` array near the bottom.
2. Edit the relevant entry - `score`, `body`, `tags`, etc.
3. Bump that entry's `reviewed` date and the global `LAST_REVIEWED` to today.
4. Open it in a browser to check, then commit.

No build step and no dependencies. The site is one static HTML file plus a
generated `metrics.json`; the pipeline that writes it lives in `scripts/`.

---

```
$ python3 scripts/fetch_metrics.py
```

`metrics.json` is generated. Do not edit it by hand.

```bash
python3 scripts/fetch_metrics.py --dry-run     # print, write nothing
python3 scripts/fetch_metrics.py               # write metrics.json
python3 -m unittest discover -s scripts/tests  # run the tests
```

Python 3 standard library only - no dependencies, no API keys, no secrets.

```
  SOURCE MATRIX
  monero .............. Coin Metrics ......... transactions per day
  railgun ............. DefiLlama ............ value in pool
  tornado-cash ........ Ethereum JSON-RPC .... 100 ETH pool balance
  everything else ..... UNSOURCED ............ no keyless public endpoint
```

A source that fails degrades to its last known-good value, labelled with its real
age, rather than blanking the card. A run where most sources fail still writes the
file and then reports red: a red run is a notification, never a rollback.

To add a protocol: add its entry to `DATA` in `index.html` with a unique `id`,
then classify that id in `scripts/sources/__init__.py` as either a source in
`REGISTRY` or an entry in `UNSOURCED` with a reason. `test_registry_coverage`
fails until you do, which is deliberate.

---

```
$ uname -a
```

Plain HTML/CSS/JS, no framework. JetBrains Mono + a Tokyo Night palette.
Python 3 standard library for the metrics pipeline. GitHub Actions for the cron.

---

```
$ cat DISCLAIMER
```

Educational research only. Not financial or legal advice. Privacy laws and the legal
status of these tools vary by jurisdiction and change over time - do your own research.
