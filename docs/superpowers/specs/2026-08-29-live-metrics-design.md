# Live metrics for crypto-privacy-map

Date: 2026-08-29
Status: proposed

## Problem

The map is a single static `index.html` with ten protocols hand-scored in a `DATA`
array. Two things have gone stale.

**Freshness.** With `STALE_AFTER_DAYS = 180`, six of the ten entries currently render
a "Review due" chip: Beldex, MWC, Samourai, Decred, Dash, and Railgun. Only Monero,
Zano, Zcash and Tornado are inside the window.

**Coverage.** The private-by-default column has four entries, which is too thin to
carry the site's central thesis. The whole shielded-by-default cohort is absent
(Pirate Chain, Grin, Beam, Firo, Iron Fish, Namada, Penumbra), as are several
significant opt-in systems (Aztec, Privacy Pools, Wasabi).

**Credibility.** The "real adoption" scoring factor is currently an unsourced
assertion. For a project whose thesis is that measured behaviour matters more than
marketing claims, the adoption numbers being unmeasured is the weakest joint in the
argument. Where a number is publicly checkable, showing it is worth more than
asserting it.

Separately, the README advertises an "automated watch" agent that opens PRs. No such
workflow exists in this repository.

## Goals

1. Show real, sourced, automatically refreshed metrics beside the hand-set scores.
2. Expand coverage to roughly twenty protocols and re-verify every stale entry.
3. Never let the pipeline damage, contradict, or silently alter editorial content.
4. Keep the site a dependency-free static file that works with no network.

## Non-goals

Explicitly out of scope, to keep the surface small:

- **No price or market-cap data.** This is a privacy map, not a market tracker.
  Metrics must be privacy-relevant or they do not ship.
- **No score computation.** The 0-10 stays a hand-set editorial judgment, always.
- **No client-side API calls.** The browser fetches one file from our own origin.
- **No framework, bundler, or third-party package.** Python's standard library
  only for the pipeline; no framework for the page.
- **Not the editorial PR agent.** This design covers metrics. The README claim about
  an automated watch agent gets corrected to describe what actually exists.

## Decisions taken before this design

Four forks were settled in discussion and are treated as fixed here:

| Decision | Choice |
| --- | --- |
| What "live" means | Nightly CI job, committed data file, not browser-side fetching |
| Metrics vs score | Display only. Metrics never move a score |
| Coverage | Selective, roughly twenty protocols |
| Data sources | Free and keyless only. No secrets in the repo |

## Architecture

Approach C of three considered. `DATA` stays inline in `index.html`. The pipeline's
only write surface is a new `metrics.json`.

```
 .github/workflows/metrics.yml     nightly cron + manual dispatch
            |
            v
 scripts/fetch_metrics.py          runner: isolate, retry, merge, write
            |
            +-- scripts/sources/*.py     one module per source
            |
            v
 metrics.json                      bot-owned. Never hand-edited
            |
            v
 index.html                        renders fully from inline DATA first,
                                   then enriches from metrics.json
```

The ownership boundary is the point. Editorial content (`DATA`: names, scores, prose,
tags, review dates) is human-only and lives in `index.html`. Measured content
(`metrics.json`) is bot-only. Neither writer touches the other's file, so a bad
pipeline run can produce wrong numbers but can never rewrite your words or your
grades, and a hand edit can never be clobbered by a nightly push.

This choice follows from the display-only decision. If metrics can never affect a
score, then metrics are decoration over an already-complete document, and decoration
must not be load-bearing: `index.html` renders every card completely with no network
access at all.

### Rejected alternatives

**A - move all of `DATA` into a bot-written `data.json`.** Conceptually cleanest, but
it puts prose and scores in a file the automation rewrites nightly, and the page
renders nothing when the fetch fails.

**B - split into human-owned `protocols.json` plus bot-owned `metrics.json`.** Same
ownership boundary as C with machine-readable editorial data, at the cost of the
page no longer rendering offline. Worth revisiting if `index.html` grows unwieldy or
another consumer needs the editorial data; C to B is a mechanical refactor.

## Data contract

`metrics.json`, written by the pipeline, read by the page.

```json
{
  "schema": 1,
  "generated": "2026-08-29T03:17:44Z",
  "metrics": {
    "zcash-shielded": {
      "status": "ok",
      "fetched": "2026-08-29T03:17:41Z",
      "source": { "name": "Blockchair", "url": "https://blockchair.com/zcash" },
      "values": [
        { "key": "shielded_share", "label": "Shielded share",
          "value": 34.2, "format": "pct", "trend30d": 2.1 },
        { "key": "pool_value", "label": "Pool value",
          "value": 1420000, "format": "coin", "unit": "ZEC" }
      ]
    },
    "pirate-chain": { "status": "unsourced" },
    "railgun": {
      "status": "error",
      "error": "timeout after 10s",
      "lastGood": { "fetched": "2026-08-26T03:17:12Z", "source": {}, "values": [] }
    }
  }
}
```

Keys are stable protocol slugs. This requires a new `id` field on every `DATA` entry
(`"monero"`, `"zcash-shielded"`, ...); names are not stable enough to key on.

**Status values.**

- `ok` - fetched successfully this run.
- `unsourced` - no keyless public source exists for this protocol. A permanent,
  deliberate state, not a failure. Emitted from an explicit `UNSOURCED` list in the
  source registry, each entry carrying a one-line reason, so "we looked and found
  nothing" stays distinguishable from a typo'd id.
- `error` - a source exists and the fetch failed. Transient. Carries `lastGood` when
  a previous run succeeded.

**`format`** is one of `pct`, `int`, `coin`, `usd`, and controls rendering only. All
values are raw numbers; formatting is the page's job.

**`trend30d`** is optional and is populated only when the upstream source reports a
30-day change itself. `metrics.json` holds current values only, so we cannot derive a
trend from it, and keeping our own history series is deliberately out of scope for v1.
Where a source offers no trend, the value renders without one rather than being
computed from anything we have lying around. Storing a history file is the obvious v2
if trends turn out to matter more than the current snapshot.

**`lastGood`** means the runner reads the existing `metrics.json` before writing.
A source that fails does not blank its card, it shows the last good numbers with
their real age. Degrading to older-but-labelled beats degrading to empty.

## Fetcher structure

`scripts/fetch_metrics.py`, Python 3.11+, standard library only (`urllib.request`,
`json`, `concurrent.futures`, `unittest`). Chosen over Node because Python is the
only runtime present on the development machine, so the fetcher and its tests run
locally with no toolchain install; both are preinstalled on `ubuntu-latest`. The
pipeline shares no code with the page, so the language split costs nothing: the only
contract between them is `metrics.json`.

Each source is a module in `scripts/sources/` exposing:

```python
SOURCE = Source(
    id="zcash-shielded",
    source_name="Blockchair",
    source_url="https://blockchair.com/zcash",
    fetch=_fetch,          # () -> list[Value], or raises
)
```

The runner:

1. Loads the previous `metrics.json` if present, for `lastGood`.
2. Runs every registered source with a 10s timeout and two retries on network error,
   at concurrency 4, sending a `User-Agent` identifying the project.
3. Wraps each source in try/catch. **One source failing never fails the run.**
4. Validates the assembled object against the schema before writing.
5. Writes atomically (temp file plus rename).

Exit code is 0 on success. The job exits non-zero if more than half of the registered
sources errored, so a widespread breakage shows as a red run, but it writes the file
first so `lastGood` is preserved either way. A red run is a notification, not a
rollback.

A `--dry-run` flag prints to stdout instead of writing, for local checking.

### Candidate sources

Every endpoint below is a candidate, not a commitment. Implementation verifies each
one is genuinely keyless, is within its terms of service for automated nightly use,
and returns what we think it returns. Any that fails verification is dropped and its
protocol is marked `unsourced` rather than worked around.

| Protocol | Metric | Candidate source |
| --- | --- | --- |
| Monero | Daily tx count | Public block explorer API |
| Zcash Shielded | Shielded pool value and share of supply | Blockchair Zcash stats |
| Tornado Cash | Per-denomination pool balances | `eth_getBalance` via public RPC |
| Railgun | TVL | DefiLlama (keyless) |
| Aztec | TVL, rollup activity | DefiLlama (keyless) |
| Firo, Grin, Beam | Chain activity | Project block explorers |
| Everything else | - | `unsourced` |

Roughly half the roster will be `unsourced`. That asymmetry is inherent to the
keyless constraint and is handled explicitly in the UI rather than papered over.

## Failure and staleness behaviour

The page now has two unrelated notions of freshness, and they must not share a
visual language. Review age is a claim about human judgment. Metric age is a claim
about a cron job. Rendering a green "current" dot because a bot pinged an API would
imply you re-read the card, which would be a lie.

- **Review freshness** keeps its existing treatment exactly: the `reviewed` footer,
  the fresh/stale dot, the "Review due" chip.
- **Metric freshness** renders in a separate, visually quieter strip below the
  bullets, using relative time ("updated 6h ago"). Different typography, no dots,
  no chips.

Per-card states:

| Condition | Render |
| --- | --- |
| `ok`, data under 48h | Values normally |
| `ok`, data over 7 days | Values dimmed, "last updated N days ago" |

Age is always computed from the record's `fetched` timestamp, never from `status`.
An `ok` record can still be a week old: `status` describes how the last write went,
and if CI itself has stopped running, every record stays `ok` while the whole file
ages. That case is exactly what the dimmed treatment is for, so a silently dead
pipeline surfaces on the page instead of presenting week-old numbers as current.
| `error` with `lastGood` | Last good values, "as of N days ago" |
| `error` without `lastGood`, or `unsourced` | Nothing at all |
| `metrics.json` missing or malformed | Page renders exactly as it does today |

**The last two rows are the important ones.** A card with no data source renders no
metrics block, not a placeholder and not an "N/A" row. Eight cards each carrying a
"no data source available" line would be noise repeated eight times, and a permanent
empty slot reads as a bug. The absence is explained once, in the footer legend, not
per card.

If `metrics.json` fails to load entirely, the page logs a console warning and is
otherwise indistinguishable from today's site. No error banner. A visitor should
never see the plumbing.

*Judgment call worth challenging:* rendering nothing for `unsourced` optimises for a
clean page over per-card explicitness. The alternative is a muted one-line "no public
data source" on those cards, which is more honest per card and noisier in aggregate.

## Render changes

`index.html` changes, all additive:

1. Add an `id` slug to each `DATA` entry.
2. Render synchronously from `DATA` on load, as today. **First paint never waits on
   the network.**
3. Then `loadMetrics()` fetches `metrics.json` with `cache: "no-cache"` and, on
   success, re-renders with the metrics block merged in.
4. `cardHTML(p, m)` takes an optional metrics record and appends the metrics strip.
5. New footer line: metrics generation time as relative age, plus the one-sentence
   note explaining that metrics appear only where a keyless public source exists.

Search and sort are untouched. Metrics are not searchable and add no sort modes.

## Editorial workstream

Separate from the pipeline, and gated on verification rather than recall.

Add ten: Pirate Chain, Firo, Grin, Beam, Iron Fish, Namada, Penumbra
(private-by-default); Aztec, Privacy Pools, Wasabi (opt-in). Re-verify and re-date
the six stale entries.

**Every new or changed factual claim must be verified against a current source at
the time of writing, and the `reviewed` date set to the date of that verification.**
This is not optional and not something to fill in from memory. The assistant's
training data ends May 2026; the existing entries were last reviewed 2026-06-13;
today is 2026-08-29. Any score, adoption claim, or legal-status tag written without
checking a live source would be a guess wearing the costume of a reviewed fact,
which is precisely the failure mode this whole project exists to argue against.

Two specific items flagged during discussion:

- **Re-check Zcash.** The bullet "a minority of TXs use the shielded pool" may now
  understate shielded adoption, which would change the 8.
- **Consider a regulatory-status dimension.** EU AMLR restrictions on
  anonymity-enhancing coins for exchanges are a material real-world privacy signal
  and currently appear nowhere on the page. Whether this becomes a tag, a card
  field, or a page section is an open design question, deliberately not settled here.

## CI

`.github/workflows/metrics.yml`:

- Triggers: nightly cron at 03:17 UTC (off the hour, to avoid the top-of-hour
  stampede against public endpoints) plus `workflow_dispatch`.
- `permissions: contents: write`; a concurrency group prevents overlapping runs.
- Python 3 as preinstalled on the runner. No install step and no `setup-python`,
  since there are no dependencies.
- Runs the script; if `git diff --quiet` reports no change, skips the commit.
  Otherwise commits `chore(metrics): nightly refresh` and pushes.

## Testing

The repo has no test framework. Use `unittest`, which is built in.
Run with `python3 -m unittest discover -s scripts/tests`.

Unit tests, all offline against fixtures:

- `lastGood` merge: a failing source retains previous values with the correct age.
- Schema validation rejects malformed source output.
- A source that throws is isolated; other sources still land.
- A source that hangs is cut off by the timeout.
- Relative-time formatting boundaries (under 48h, over 7 days).
- The runner exits non-zero when more than half the sources fail, but still writes.
- Registry coverage: the ids in `REGISTRY` plus `UNSOURCED` exactly equal the ids
  parsed out of `index.html`, so roster drift is a test failure and adding a
  protocol to the page forces an explicit sourced/unsourced decision.

Source modules are tested against recorded fixture responses, never live network,
so the suite is deterministic and runnable offline.

Manual checks:

- Open `index.html` with `metrics.json` deleted. Must be pixel-identical to today.
- Open it with a `metrics.json` containing one `ok`, one `error` with `lastGood`,
  and one `unsourced` entry. Verify all three render as specified.

TDD applies: tests first.

## Risks

- **Keyless endpoints disappear or change shape.** The most likely failure mode.
  Mitigated by per-source isolation, `lastGood`, and a red job on mass failure.
- **Rate limits and terms of service.** Nightly only, concurrency 4, identifying
  User-Agent. Any source whose terms forbid automated use is dropped.
- **Nightly commit noise.** One small JSON, a diff of a few hundred bytes per day.
  Negligible for years, and the commit is skipped entirely when nothing changed.
- **Forks.** A fork's workflow cannot push without its own permissions. Document it;
  the site still works, it just stops updating.

## Open questions

1. `unsourced` cards: render nothing, or a muted "no public data source" line?
2. Does regulatory status become a tag, a card field, or its own page section?
3. Keep `STALE_AFTER_DAYS` at 180 once the roster reaches twenty? At that size,
   staying green requires a review roughly every nine days.
