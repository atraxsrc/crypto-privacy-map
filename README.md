# crypto-privacy-map

**Default vs opt-in privacy: the truth behind the protocols.**

A single-page, visual map that grades crypto privacy protocols by how much privacy
they actually deliver - not by marketing. The core thesis: **privacy that is on by
default beats privacy you have to opt into**, because if people *can* skip privacy,
most of them will, and a small anonymity set protects no one.

🔗 **Live:** https://atraxsrc.github.io/crypto-privacy-map/

[![metrics](https://github.com/atraxsrc/crypto-privacy-map/actions/workflows/metrics.yml/badge.svg)](https://github.com/atraxsrc/crypto-privacy-map/actions/workflows/metrics.yml)

---

## What it shows

Protocols are split into two columns and scored `0-10`:

| Column | Meaning |
| --- | --- |
| 🔒 **Private by default** | Every transaction is private with no user action (e.g. Monero). |
| ⚠️ **Opt-in privacy** | The user must choose privacy; most transactions stay public (e.g. Zcash shielded, mixers). |

Services that no longer operate (e.g. Samourai Whirlpool) move to an unscored
*Offline / Historical* section: set `column: "archive"` and `score: null`.

Each card carries a privacy grade, the underlying tech, key caveats, status tags
(legal risk, adoption, etc.), and the date it was last reviewed.

## How scores work

Scores are an **opinionated synthesis**, not a precise metric - they rank real-world
privacy. Each protocol gets `0-2` on five factors and the score is their sum, so
every card shows exactly where its points come from:

1. **Default vs opt-in** (`DEF`) - always-on privacy beats privacy you choose; opt-in scores 0.
2. **Anonymity set** (`ANON`) - how large a crowd you blend into.
3. **Cryptographic strength** (`CRYPTO`) - ring signatures, zk-SNARKs, MimbleWimble, CoinJoin, etc.
4. **Usage scale** (`USAGE`) - how much real use the privacy feature gets, measured on
   its own so default-private coins don't score it for free.
5. **Maturity & standing** (`MATURE`) - battle-testing, audits, and legal/operational health.

Grade bands: **8-10 High** · **6-7 Medium** · **0-5 Low**. The full breakdown lives in
the *How the scores work* section on the page.

## Staying current

The privacy landscape shifts fast (sanctions, arrests, delistings, adoption swings), so
the project is built to stay fresh:

- **Data-driven** - every protocol lives in one `DATA` array in `index.html`. The score,
  grade colour and bar all derive from the entry's `factors` array.
- **Per-entry review dates** - each entry has a `reviewed` date. Anything older than
  `STALE_AFTER_DAYS` (180) is flagged with a *Review due* chip, and the footer tallies how
  many entries need a refresh.
- **Nightly metrics** - a GitHub Action fetches measured figures (pool balances,
  shielded shares, transaction counts) from public, key-free sources and commits
  them to `metrics.json`. The page layers these onto the cards. Measured data
  never changes a score: factor judgments stay hand-set. Protocols with no keyless public
  source simply carry no measured figures.

## Updating the data

1. Open `index.html` and find the `DATA` array near the bottom.
2. Edit the relevant entry - `factors`, `body`, `tags`, `sources`, etc. Never add a
   `score` field to a scored entry: it is computed from `factors`.
3. Bump that entry's `reviewed` date and the global `LAST_REVIEWED` to today.
4. Open it in a browser to check, then commit.

No build step and no dependencies. The site is one static HTML file plus a
generated `metrics.json`; the pipeline that writes it lives in `scripts/`.

## The metrics pipeline

`metrics.json` is generated. Do not edit it by hand.

`metrics-history.json` (also generated) records each value on the day it
changes; it drives the 30-day trend arrows, which appear once a series is 30
days old. A run that changes nothing but timestamps writes neither file, so
the nightly job only commits when a number actually moved (or every 6 days,
so the page never shows stale-looking metrics).

```bash
python3 scripts/fetch_metrics.py --dry-run     # print, write nothing
python3 scripts/fetch_metrics.py               # write metrics.json
python3 -m unittest discover -s scripts/tests  # run the tests
```

Python 3 standard library only - no dependencies, no API keys, no secrets.

To add a protocol: add its entry to `DATA` in `index.html` with a unique `id`,
then classify that id in `scripts/sources/__init__.py` as either a source in
`REGISTRY` or an entry in `UNSOURCED` with a reason. `test_registry_coverage`
fails until you do, which is deliberate.

## Tech

Plain HTML/CSS/JS, no framework. JetBrains Mono + a Tokyo Night palette.

## Disclaimer

Educational research only. Not financial or legal advice. Privacy laws and the legal
status of these tools vary by jurisdiction and change over time - do your own research.
