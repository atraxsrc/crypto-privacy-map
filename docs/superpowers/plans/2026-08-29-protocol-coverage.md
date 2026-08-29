# Protocol Coverage Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the map from 10 protocols to 20, re-verify every stale entry, and make the verification discipline machine-enforced by requiring a cited source on every card.

**Architecture:** All editorial content stays in the `DATA` array in `index.html`, which remains the single source of truth for the roster. A new `scripts/data_model.py` parses that array back into Python so a test suite can assert invariants on the real page content: valid scores, sane review dates, well-formed tags, and at least one cited source per entry. Research is done per protocol against live sources; the tests catch structural mistakes, and a final calibration pass catches ranking mistakes.

**Tech Stack:** Python 3 standard library only. Vanilla JS/CSS in `index.html`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-29-live-metrics-design.md` (the "Editorial workstream" section)

**Companion plan:** `docs/superpowers/plans/2026-08-29-live-metrics-pipeline.md`. That plan must be executed **first** - this one depends on the protocol `id` field it adds (Task 1) and the source registry it creates (Task 6).

## Global Constraints

- **THIS PLAN CANNOT BE EXECUTED FROM MEMORY.** Every factual claim - score, adoption
  figure, legal status, "founders arrested", "delisted from" - must be checked against
  a live source at the time of writing. The executor needs working web access. If you
  do not have it, **stop and say so**; do not write a single score from recall. On a
  project whose entire thesis is that measured behaviour beats asserted claims, a
  guessed number is not a small error, it is the exact failure the site exists to argue
  against.
- **Every `DATA` entry carries a `sources` array with at least one https URL.** This is
  enforced by `test_data_integrity`, not by good intentions.
- **`reviewed` is the date you actually checked the sources**, in `YYYY-MM-DD`. Never
  copy a date forward from another entry, and never post-date.
- **Scores follow the published rubric** in the "How the scores work" section of
  `index.html`: default-vs-opt-in (largest weight), anonymity set, cryptographic
  strength, real adoption, maturity and standing. Record the per-factor reasoning in
  the commit message body so a later reviewer can audit the judgment.
- **Do not restructure or restyle the page.** This plan adds entries, one tag type, and
  a source-link row. Nothing else about the layout changes.
- **Do not change an existing score without saying why** in the commit message. Silent
  rescoring destroys the map's continuity.
- **Writing style:** plain hyphens only in all new code, comments, content, and commit
  messages. No em-dashes or en-dashes. The existing page violates this in about a dozen
  places (card bullets, the methodology prose, and the `8-10` range labels); Task 9
  sweeps them, and any entry you touch before then gets fixed as you go.
- **Card prose keeps the existing voice:** exactly three short declarative bullets per
  entry, matching the ten already there. Not two, not five.
- **Run tests with:** `python3 -m unittest discover -s scripts/tests -v`
- **Git note:** `~/.gitconfig` is unreadable in this environment, so git needs
  `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null` on every command or it
  fails with "unknown error occurred while reading the configuration files". For
  author identity, do NOT invent one and do NOT copy one from any document: reuse
  the identity this repo already uses, read from its own history.
  `GIT_AUTHOR_NAME="$(git log -1 --format='%an')" GIT_AUTHOR_EMAIL="$(git log -1 --format='%ae')"`
  and the matching `GIT_COMMITTER_*` pair. No `Co-Authored-By` trailer, no
  `Claude-Session` trailer, and never an address in a commit message body.

## File Structure

| File | Responsibility |
| --- | --- |
| `scripts/data_model.py` | Parse the `DATA` array out of `index.html` into Python objects. |
| `scripts/tests/test_data_model.py` | Unit tests for the parser, against small literals. |
| `scripts/tests/test_data_integrity.py` | Invariants asserted against the real `index.html`. |
| `index.html` | The 20 entries, the `sources` link row, the `legal` tag type, the bottom panels. |
| `scripts/sources/__init__.py` | Classify each new id as sourced or unsourced. |
| `README.md` | Protocol count and the sourcing rule. |

## The per-protocol research checklist

Every new or refreshed entry runs this. It is the unit of work for Tasks 3 through 6.

1. **Alive?** Official site, latest release, latest commit. A dead project is a
   different card from a healthy one.
2. **Mechanism.** Private by default or opt-in, and which cryptography. This decides
   the column, and the column is the largest scoring factor.
3. **Anonymity set.** Transaction counts, pool sizes, shielded share. Numbers where
   they exist; "no public figures" is itself a finding worth a bullet.
4. **Real adoption.** What share of activity is actually private, and is it growing.
5. **Legal and operational standing.** Delistings, sanctions, arrests, prosecutions,
   and EU AMLR exposure ahead of the 2027 deadline.
6. **Incidents and audits.** Known breaks, deanonymisation research, completed audits.

Then: pick the column, score against the rubric, write three bullets, choose tags,
list every URL you used in `sources`, and set `reviewed` to today.

**If the research does not support a confident card, do not add the protocol.** Say so
and move on. A map of 17 well-verified protocols beats one of 20 with three guesses in
it, and there is no requirement to hit a number.

**A note on the `<...>`, `N` and `YYYY-MM-DD` markers in Tasks 4 to 6.** These are not
unfinished plan sections. They are the fields whose values are research findings and
therefore cannot exist before the research does - writing a plausible-looking score
here would be precisely the failure this plan is built to prevent. Everything about
*how* to fill them is specified: the checklist above, the published rubric, and a
template naming every required field. The final verification greps for any marker that
survived.

---

### Task 1: Parse DATA back out of the page, and assert structural invariants

Nothing here changes content. It builds the net that every later task lands in.

**Files:**
- Create: `scripts/data_model.py`
- Test: `scripts/tests/test_data_model.py`, `scripts/tests/test_data_integrity.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `extract_data_literal(html: str) -> str`
  - `js_to_json(literal: str) -> str`
  - `load_data(path) -> list[dict]`

- [ ] **Step 1: Write the failing parser test**

Create `scripts/tests/test_data_model.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import unittest

from data_model import extract_data_literal, js_to_json, load_data

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

SAMPLE = '''
<script>
  const LAST_REVIEWED = "2026-06-13";
  const DATA = [
    {
      id: "monero",
      column: "default", name: "Monero", score: 10,
      body: ["One.", "Two [bracketed] and \\"quoted\\"."],
      tags: [{ type: "ok", label: "Battle-Tested" }],
    },
  ];
  function gradeOf(score) { return score; }
</script>
'''


class ExtractTest(unittest.TestCase):
    def test_slices_exactly_the_array(self):
        literal = extract_data_literal(SAMPLE)
        self.assertTrue(literal.startswith("["))
        self.assertTrue(literal.endswith("]"))
        self.assertNotIn("gradeOf", literal)

    def test_brackets_inside_strings_do_not_end_the_array(self):
        literal = extract_data_literal(SAMPLE)
        self.assertIn("bracketed", literal)

    def test_raises_when_data_array_is_absent(self):
        with self.assertRaises(ValueError):
            extract_data_literal("<script>const OTHER = [];</script>")


class JsToJsonTest(unittest.TestCase):
    def test_quotes_bare_keys_and_drops_trailing_commas(self):
        entries = load_data_from_text(SAMPLE)
        self.assertEqual(entries[0]["id"], "monero")
        self.assertEqual(entries[0]["score"], 10)
        self.assertEqual(entries[0]["tags"][0]["type"], "ok")

    def test_does_not_touch_colons_inside_strings(self):
        text = 'const DATA = [{ id: "x", body: ["Note: this has a colon."] }];'
        self.assertEqual(load_data_from_text(text)[0]["body"], ["Note: this has a colon."])

    def test_preserves_escaped_quotes_in_strings(self):
        self.assertIn('"quoted"', load_data_from_text(SAMPLE)[0]["body"][1])

    def test_strips_line_comments_outside_strings(self):
        text = '''const DATA = [
            // a note about the entry
            { id: "x", body: ["https://example.org has slashes"] }
        ];'''
        entry = load_data_from_text(text)[0]
        self.assertEqual(entry["id"], "x")
        self.assertIn("https://example.org", entry["body"][0])


class LoadDataTest(unittest.TestCase):
    def test_reads_the_real_page(self):
        entries = load_data(REPO_ROOT / "index.html")
        self.assertGreaterEqual(len(entries), 10)
        self.assertTrue(all("id" in e for e in entries))


def load_data_from_text(text):
    import json
    return json.loads(js_to_json(extract_data_literal(text)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'data_model'`

- [ ] **Step 3: Write the parser**

Create `scripts/data_model.py`:

```python
"""Read the DATA array out of index.html as Python objects.

The page owns the editorial content. Rather than duplicate it into a JSON file
the page would then have to fetch, this module parses the JavaScript literals
directly, so tests assert invariants against exactly what ships.

DATA uses a restricted JS subset: double-quoted strings, bare identifier keys,
numbers, arrays, objects, trailing commas, and line comments. Turning that into
JSON means quoting bare keys without touching string contents, which is why
strings are masked out first.
"""

import json
import re
from pathlib import Path

_MARKER = "const DATA = ["
_KEY_RE = re.compile(r'([{,]\s*)([A-Za-z_]\w*)\s*:')
_TRAILING_COMMA_RE = re.compile(r',(\s*[\]}])')
_LINE_COMMENT_RE = re.compile(r'//[^\n]*')
_PLACEHOLDER_RE = re.compile("\x00(\\d+)\x00")


def _mask_strings(text):
    """Replace every double-quoted string with a placeholder.

    Everything downstream rewrites syntax with regexes. Masking first is what
    stops a colon, a brace, or a // inside a card's prose from being treated as
    structure.
    """
    out, strings, i, n = [], [], 0, len(text)
    while i < n:
        if text[i] != '"':
            out.append(text[i])
            i += 1
            continue
        j = i + 1
        while j < n:
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == '"':
                break
            j += 1
        if j >= n:
            raise ValueError("unterminated string literal in DATA")
        strings.append(text[i:j + 1])
        out.append(f"\x00{len(strings) - 1}\x00")
        i = j + 1
    return "".join(out), strings


def _unmask_strings(text, strings):
    return _PLACEHOLDER_RE.sub(lambda m: strings[int(m.group(1))], text)


def extract_data_literal(html):
    """Return the DATA array source, from its opening bracket to its match."""
    try:
        start = html.index(_MARKER) + len(_MARKER) - 1
    except ValueError:
        raise ValueError("no `const DATA = [` found") from None

    depth, in_str, esc = 0, False, False
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return html[start:i + 1]
    raise ValueError("unterminated DATA array")


def js_to_json(literal):
    """Convert the restricted JS literal subset to strict JSON."""
    masked, strings = _mask_strings(literal)
    masked = _LINE_COMMENT_RE.sub("", masked)
    masked = _KEY_RE.sub(r'\1"\2":', masked)
    masked = _TRAILING_COMMA_RE.sub(r"\1", masked)
    return _unmask_strings(masked, strings)


def load_data(path):
    """Parse index.html and return the DATA entries as dicts."""
    html = Path(path).read_text(encoding="utf-8")
    return json.loads(js_to_json(extract_data_literal(html)))
```

Note the `[` at `start`: `_MARKER` ends with `[`, so `len(_MARKER) - 1` puts the
slice on the bracket and `depth` starts counting from it.

- [ ] **Step 4: Write the integrity test**

Create `scripts/tests/test_data_integrity.py`. The `sources` assertion is written
now but skipped until Task 2 fills the field in, so this task stays green.

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import datetime
import re
import unittest

from data_model import load_data

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX = REPO_ROOT / "index.html"

COLUMNS = {"default", "optin"}
TAG_TYPES = {"ok", "warn", "info", "legal"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED = ("id", "column", "name", "ticker", "url", "reviewed", "tech", "score", "body", "tags")


class DataIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = load_data(INDEX)

    def test_every_entry_has_the_required_fields(self):
        for e in self.entries:
            for field in REQUIRED:
                self.assertIn(field, e, f"{e.get('name', '?')} missing {field!r}")

    def test_ids_are_unique_slugs(self):
        ids = [e["id"] for e in self.entries]
        self.assertEqual(len(ids), len(set(ids)), "duplicate protocol ids")
        for pid in ids:
            self.assertRegex(pid, SLUG_RE, f"{pid} is not a lowercase slug")

    def test_columns_are_valid(self):
        for e in self.entries:
            self.assertIn(e["column"], COLUMNS, f"{e['name']}: bad column")

    def test_scores_are_integers_in_range(self):
        for e in self.entries:
            self.assertIsInstance(e["score"], int, f"{e['name']}: score must be an int")
            self.assertGreaterEqual(e["score"], 0)
            self.assertLessEqual(e["score"], 10)

    def test_review_dates_are_real_and_not_in_the_future(self):
        today = datetime.date.today()
        for e in self.entries:
            self.assertRegex(e["reviewed"], DATE_RE, f"{e['name']}: bad date format")
            reviewed = datetime.date.fromisoformat(e["reviewed"])
            self.assertLessEqual(reviewed, today, f"{e['name']}: reviewed in the future")

    def test_urls_are_https(self):
        for e in self.entries:
            self.assertTrue(e["url"].startswith("https://"), f"{e['name']}: {e['url']}")

    def test_body_is_three_nonempty_bullets(self):
        for e in self.entries:
            self.assertEqual(len(e["body"]), 3, f"{e['name']}: expected 3 bullets")
            for line in e["body"]:
                self.assertTrue(line.strip(), f"{e['name']}: empty bullet")

    def test_tags_are_well_formed(self):
        for e in self.entries:
            for tag in e["tags"]:
                self.assertIn(tag["type"], TAG_TYPES, f"{e['name']}: bad tag type")
                self.assertTrue(tag["label"].strip(), f"{e['name']}: empty tag label")

    def test_tech_is_present(self):
        for e in self.entries:
            self.assertTrue(e["tech"].strip(), f"{e['name']}: empty tech")

    @unittest.skip("enabled in Task 2, once every entry carries its sources")
    def test_every_entry_cites_at_least_one_source(self):
        for e in self.entries:
            self.assertIn("sources", e, f"{e['name']}: no sources")
            self.assertTrue(e["sources"], f"{e['name']}: empty sources")
            for url in e["sources"]:
                self.assertTrue(url.startswith("https://"), f"{e['name']}: {url}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, with one skip. The existing ten entries satisfy every enabled
invariant. **If any fails, the current page has a real defect - fix the page, not
the test.**

- [ ] **Step 6: Commit**

```bash
git add scripts/data_model.py scripts/tests/test_data_model.py scripts/tests/test_data_integrity.py
git commit -m "Parse DATA from the page and assert structural invariants"
```

---

### Task 2: Cited sources on every card

Turns "every claim was verified" from a promise into a test.

**Files:**
- Modify: `index.html` (CSS after the `.card-foot` rules; `cardHTML`; all 10 `DATA` entries)
- Modify: `scripts/tests/test_data_integrity.py` (remove the skip)

**Interfaces:**
- Consumes: `data_model.load_data` from Task 1.
- Produces: a `sources: ["https://...", ...]` field on every `DATA` entry, rendered as a link row.

- [ ] **Step 1: Add the CSS**

Insert after the `.card-foot.stale .dot` rule:

```css
    .card-src { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 7px; font-size: 9px; }
    .card-src .lbl { color: var(--tn-comment); opacity: .7; }
    .card-src a { color: var(--tn-comment); text-decoration: none; border-bottom: 1px dotted var(--tn-border); }
    .card-src a:hover { color: var(--tn-cyan); border-bottom-color: var(--tn-cyan); }
```

- [ ] **Step 2: Render the row**

In `cardHTML`, add before the `return`:

```js
    const srcs = (p.sources || []).map((u, i) => {
      let host = u;
      try { host = new URL(u).hostname.replace(/^www\./, ""); } catch (_) { /* keep raw */ }
      return `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(host)}</a>`;
    }).join("");
    const sources = srcs
      ? `<div class="card-src"><span class="lbl">src</span>${srcs}</div>`
      : "";
```

and insert `${sources}` immediately after `${reviewed}` in the returned template.

- [ ] **Step 3: Research and add sources for the four current entries**

Monero, Zano, Zcash Shielded, and Tornado Cash were reviewed 2026-06-13 and are
still inside the freshness window, so their **claims** are not being redone here -
only the citations that back them. (Zcash is the one exception: its adoption bullet
is re-measured in Task 3, for the reason given there.) For each, find the sources
that support the bullets already written. If a bullet turns out to have no support, that is a
finding: fix the bullet and note it in the commit message.

Add to each entry, after `tags`:

```js
      sources: [
        "https://www.getmonero.org/resources/moneropedia/ringsignatures.html",
        "https://localmonero.co/blocks"
      ]
```

- [ ] **Step 4: Add interim sources for the remaining six**

The six stale entries (Beldex, MWC, Railgun, Samourai Whirlpool, Decred CSPP, Dash
PrivateSend) get their sources as part of the full re-verification in Task 3.
To keep this task green, give each one its official project URL as a starting
citation now - it is a real source for the protocol's existence and mechanism, and
Task 3 replaces it with the full set.

- [ ] **Step 5: Enable the test**

Delete the `@unittest.skip(...)` decorator from
`test_every_entry_cites_at_least_one_source`.

- [ ] **Step 6: Run the tests**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, no skips.

- [ ] **Step 7: Verify the page**

Open `index.html`. Every card shows a small `src` row of hostnames below the
review date. Links open in a new tab. The row does not wrap awkwardly at narrow
widths - check at 380px.

- [ ] **Step 8: Commit**

```bash
git add index.html scripts/tests/test_data_integrity.py
git commit -m "Require and render a cited source on every protocol card"
```

---

### Task 3: Re-verify the six stale entries, plus Zcash

**Files:**
- Modify: `index.html` (the Beldex, MWC, Railgun, Samourai Whirlpool, Decred CSPP, Dash PrivateSend and Zcash Shielded entries)

**Zcash is in scope despite being inside the freshness window.** The spec flags its
bullet "a minority of TXs use the shielded pool" as likely to understate current
shielded adoption. Adoption is a scoring factor, so if that bullet is wrong the 8 is
wrong, and a stale-but-in-window card is exactly the kind of error the review-date
machinery cannot catch.

- [ ] **Step 1: Confirm which entries are actually stale**

```bash
python3 - <<'EOF'
import sys, pathlib, datetime
sys.path.insert(0, "scripts")
from data_model import load_data
today = datetime.date.today()
for e in sorted(load_data("index.html"), key=lambda x: x["reviewed"]):
    age = (today - datetime.date.fromisoformat(e["reviewed"])).days
    print(f"{age:>5}d  {'STALE' if age > 180 else '     '}  {e['name']}")
EOF
```

- [ ] **Step 2: Run the research checklist on each of the six**

Work one protocol at a time, using the per-protocol checklist above. Pay
particular attention to the claims most likely to have moved:

- **Samourai Whirlpool** - the case against the founders has progressed since the
  card was written. "Founders arrested April 2024" and "uncertain future" both
  need current status, and the score may need to move.
- **Railgun** - "Compliance features available" and the DeFi privacy claims need
  current sourcing.
- **Dash PrivateSend**, **Decred CSPP** - check whether adoption figures still
  support their scores, and whether either project's status has changed.
- **Beldex**, **MWC** - check both are still actively developed. A dormant
  project is a materially different card.
- **Zcash Shielded** - measure the current shielded share of transactions and of
  supply. If shielded usage has grown materially since the card was written, both
  the adoption bullet and the score need to move.

- [ ] **Step 3: Update each entry**

For each: rewrite the three bullets to current fact, adjust `tech` if it changed,
set `score` per the rubric, update `tags`, replace `sources` with the full set you
actually used, and set `reviewed` to today's date.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS

- [ ] **Step 5: Confirm nothing is stale**

Re-run the Step 1 command. Expected: no `STALE` rows.

- [ ] **Step 6: Commit**

Record the reasoning. One commit for all seven is fine; the body carries the audit trail.

```bash
git add index.html
git commit -m "Re-verify the six stale entries and re-measure Zcash adoption

Beldex 6 -> N: <what changed, and which factor moved>
MWC 6 -> N: ...
Railgun 7 -> N: ...
Samourai Whirlpool 5 -> N: ...
Decred CSPP 5 -> N: ...
Dash PrivateSend 4 -> N: ...
Zcash Shielded 8 -> N: shielded adoption re-measured; ...

Sources are recorded per entry in the sources field."
```

---

### Task 4: Private-by-default, batch A

Pirate Chain, Firo, Grin, Beam. These four carry the site's thesis: privacy that is on by default, held back by scale rather than by design.

**Files:**
- Modify: `index.html` (`DATA`, default column)

- [ ] **Step 1: Research each against the checklist**

Specific questions that decide these cards:

- **Pirate Chain (ARRR)** - confirm shielding really is mandatory rather than
  default-on-but-optional. That distinction is the whole column.
- **Firo (FIRO)** - Lelantus Spark: is it opt-in or default in the current
  release? Answer decides the column. If opt-in, it belongs on the right.
- **Grin (GRIN)**, **Beam (BEAM)** - both MimbleWimble, so the differentiator is
  liveness and adoption. Check the last release and whether either is dormant.

- [ ] **Step 2: Write the entries**

Insert into `DATA` in the default column group, following the exact existing
shape. Template with every required field:

```js
    {
      id: "pirate-chain",
      column: "default", name: "Pirate Chain", ticker: "ARRR", url: "https://pirate.black",
      reviewed: "YYYY-MM-DD",
      tech: "<mechanism, dot-separated>", score: N,
      body: [
        "<claim one>",
        "<claim two>",
        "<claim three>"
      ],
      tags: [{ type: "info", label: "<label>" }],
      sources: ["https://...", "https://..."]
    },
```

Fill `reviewed` with the date you did the research and `score` from the rubric.
No entry ships with a bracketed placeholder still in it.

- [ ] **Step 3: Run the tests**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: `test_data_integrity` PASS. **`test_registry_coverage` FAILS**, naming
the four new ids. That is correct and expected - the metrics registry must
classify them, which happens in Task 7.

- [ ] **Step 4: Verify the page**

Open `index.html`. Four new cards in the left column, correct grade colours for
their scores, source rows populated, search and sort still work across all of them.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Add Pirate Chain, Firo, Grin and Beam

Per-factor reasoning for each score:
- Pirate Chain N: default <...>, anonymity set <...>, crypto <...>, adoption <...>, maturity <...>
- Firo N: ...
- Grin N: ...
- Beam N: ...

test_registry_coverage fails until Task 7 classifies these ids."
```

---

### Task 5: Private-by-default, batch B

Iron Fish, Namada, Penumbra. The newer shielded-by-default generation.

**Files:**
- Modify: `index.html` (`DATA`, default column)

- [ ] **Step 1: Research each against the checklist**

- **Iron Fish (IRON)** - confirm every transaction is shielded, and check mainnet
  activity levels.
- **Namada (NAM)** - the multi-asset shielded pool. Establish whether shielding is
  genuinely the default path for users, and the pool's current size.
- **Penumbra (UM)** - shielded DEX on Cosmos. Check whether the shielding covers
  trading as well as transfers, which is what would distinguish it.

For all three, be careful about scoring young chains highly on cryptography while
their anonymity sets are small. The rubric weights the set, and a new chain with
excellent cryptography and few users is a **Medium**, not a High. Say so in the
bullets rather than letting the score carry the caveat alone.

- [ ] **Step 2: Write the entries**

Same shape as Task 4, in the default column group.

- [ ] **Step 3: Run the tests**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: `test_data_integrity` PASS; `test_registry_coverage` still failing with
a longer id list.

- [ ] **Step 4: Verify the page**

Open `index.html`. The default column now has ten cards and reads as a coherent
ranked list from Monero downward.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Add Iron Fish, Namada and Penumbra

Per-factor reasoning for each score:
- Iron Fish N: ...
- Namada N: ...
- Penumbra N: ...

test_registry_coverage fails until Task 7 classifies these ids."
```

---

### Task 6: Opt-in privacy

Aztec, Privacy Pools, Wasabi.

**Files:**
- Modify: `index.html` (`DATA`, opt-in column)

- [ ] **Step 1: Research each against the checklist**

- **Aztec** - confirm current mainnet status and what its privacy actually covers.
  DefiLlama carries its TVL, which matters for Task 7.
- **Privacy Pools** - the association-set design. The interesting claim is that it
  offers privacy with a compliance story; check whether real usage backs that.
- **Wasabi** - the coordinator was discontinued in 2024. Establish what the
  current state of the wallet and of coinjoin coordination is. If it is
  effectively defunct, the card should say so plainly and score accordingly.

- [ ] **Step 2: Write the entries**

Same shape, `column: "optin"`.

- [ ] **Step 3: Run the tests**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: `test_data_integrity` PASS; `test_registry_coverage` failing with all
ten new ids.

- [ ] **Step 4: Verify the page**

Open `index.html`. Twenty cards total, both columns balanced.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Add Aztec, Privacy Pools and Wasabi

Per-factor reasoning for each score:
- Aztec N: ...
- Privacy Pools N: ...
- Wasabi N: ...

test_registry_coverage fails until Task 7 classifies these ids."
```

---

### Task 7: Classify the new protocols in the metrics registry

Clears the deliberate failure the last three tasks have been carrying.

**Files:**
- Modify: `scripts/sources/__init__.py`

**Interfaces:**
- Consumes: `sources.defillama.AZTEC` (defined but unregistered by the pipeline plan), `sources.base.Source`.
- Produces: a `REGISTRY` and `UNSOURCED` that together cover all 20 ids.

- [ ] **Step 1: See exactly what is unclassified**

Run: `python3 -m unittest discover -s scripts/tests -k registry -v`
Expected: FAIL, listing the ten new ids.

- [ ] **Step 2: Register Aztec**

`scripts/sources/defillama.py` already defines `AZTEC` from the pipeline plan.
Now that the protocol exists on the page, add it to `REGISTRY`:

```python
REGISTRY = (
    tornado.SOURCE,
    defillama.RAILGUN,
    defillama.AZTEC,
    zcash.SOURCE,
    monero.SOURCE,
)
```

- [ ] **Step 3: Probe for keyless sources for the rest**

Before consigning a protocol to `UNSOURCED`, check. Some of these publish open
explorer APIs:

```bash
curl -s https://api.llama.fi/protocol/privacy-pools | head -c 300
curl -s https://api.blockchair.com/grin/stats       | head -c 300
```

Any that returns useful, keyless, terms-compliant data gets a source module
following the pattern in `scripts/sources/defillama.py`: a module docstring
naming the endpoint, a pure `parse(payload)` that raises `RuntimeError` with a
readable message when its field is missing, a `_fetch` that calls `parse`, and a
`SOURCE`. Record a fixture in `scripts/tests/fixtures/` and add parser tests to
`scripts/tests/test_sources_parsers.py` covering the happy path and at least one
malformed payload.

- [ ] **Step 4: List the remainder as unsourced, with real reasons**

```python
UNSOURCED = {
    "zano": "no keyless public API for transaction or pool statistics",
    "pirate-chain": "<the actual reason you found>",
    # ...one line per remaining id
}
```

`test_registry_coverage` requires a reason longer than ten characters, so
"none" will not pass. Write what you actually found.

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS, everything green for the first time since Task 3.

- [ ] **Step 6: Regenerate and inspect metrics**

```bash
python3 scripts/fetch_metrics.py
python3 -m json.tool metrics.json | head -60
```

Expected: exit 0, twenty records, real values for the sourced ones.

- [ ] **Step 7: Commit**

```bash
git add scripts/sources/ scripts/tests/ metrics.json
git commit -m "Classify the ten new protocols as sourced or unsourced"
```

---

### Task 8: Regulatory status as a first-class signal

The spec left open whether regulatory standing becomes a tag, a card field, or a page section. **This plan settles it as a tag type**, because the tags mechanism already renders, already participates in search via `matches()`, and already carries exactly this kind of status claim ("Legal Risk", "Founders Arrested"). A new field or section would duplicate machinery that works. If you disagree, this is the task to redirect.

**Files:**
- Modify: `index.html` (tag CSS; `DATA` tags across all 20 entries)

- [ ] **Step 1: Add the tag style**

After the existing `.tag-stale` rule:

```css
    .tag-legal { background: rgba(224,175,104,.12); color: var(--tn-yellow); border: 1px solid rgba(224,175,104,.35); }
```

`TAG_TYPES` in `test_data_integrity.py` already includes `"legal"` from Task 1,
so no test change is needed.

- [ ] **Step 2: Research the regulatory picture**

Establish the current, sourced position on:

- EU AMLR restrictions on anonymity-enhancing coins for obliged entities, and the
  date they take effect.
- Which of the twenty protocols are actually in scope.
- Current exchange delisting status per protocol in major jurisdictions.
- Any sanctions or prosecutions still live.

- [ ] **Step 3: Apply legal tags**

Add a `{ type: "legal", label: "..." }` tag to every entry where regulatory
standing is a material privacy consideration, with a short, concrete label
("EU AMLR 2027", "OFAC history", "Widely delisted"). Add the sources that back
each one to that entry's `sources`.

**Do not tag every card.** A tag on all twenty carries no information. Tag the
ones where regulation is a genuine differentiator.

- [ ] **Step 4: Add a line to the methodology section**

The rubric's fifth factor is "maturity and standing". Add one sentence to that
factor's description in the "How the scores work" section explaining that legal
and regulatory standing is part of it and is surfaced as a tag.

- [ ] **Step 5: Run the tests and check the page**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: PASS

Open `index.html`. Legal tags render in the yellow warning style, distinct from
`tag-ok` and `tag-info`. Searching "AMLR" finds the tagged cards.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "Surface regulatory standing as a legal tag type"
```

---

### Task 9: Calibration, page furniture, and docs

Twenty cards scored across six sittings will not be internally consistent. This task makes them consistent and fixes the counts hard-coded elsewhere on the page.

**Files:**
- Modify: `index.html` (`LAST_REVIEWED`, `STALE_AFTER_DAYS`, the two bottom panels)
- Modify: `README.md`

- [ ] **Step 1: Print the full ranked list**

```bash
python3 - <<'EOF'
import sys, pathlib
sys.path.insert(0, "scripts")
from data_model import load_data
rows = sorted(load_data("index.html"), key=lambda e: (-e["score"], e["name"]))
for e in rows:
    print(f"{e['score']:>3}  {e['column']:<8}  {e['name']}")
EOF
```

- [ ] **Step 2: Defend every adjacent pair**

Read the list top to bottom. For each place two protocols share a score, or where
one sits directly above another, ask whether you could defend that ordering to
someone who disagrees. **The most likely error is a young default-privacy chain
scored on its cryptography rather than its anonymity set**, which the rubric
weights more heavily.

Fix any score that fails this test, and note the change and reason in the commit
message. If nothing needs fixing, say that in the commit message too - it is a
result, not a non-event.

- [ ] **Step 3: Update the review dates**

Set `LAST_REVIEWED` to today.

Then decide on `STALE_AFTER_DAYS`, currently 180. At twenty protocols, staying
green needs a review roughly every nine days. **Recommendation: leave it at 180.**
The chip is a prompt to look again, not an alarm, and lengthening the window to
make the footer look better would be optimising the instrument instead of the
measurement. If you disagree, change it here and say why.

- [ ] **Step 4: Fix the hard-coded claims in the bottom panels**

`.panel-legal` currently reads "3 of top 10 privacy projects have founders
arrested or sanctioned". At twenty protocols that count is stale and the
denominator is wrong. Recompute it from the actual roster and rewrite the line.

Check `.panel-verdict` too: "Monero remains the only protocol with real mass
privacy" is an editorial claim that the ten new entries may or may not still
support. Keep it if the research backs it; revise it if not.

Also check the two `.section-header` descriptions above the columns for any count
or claim that the expansion has invalidated.

- [ ] **Step 5: Sweep the remaining em-dashes and en-dashes**

The page predates the plain-hyphen rule and still has around a dozen, in card
bullets, the methodology prose, and the numeric range labels.

```bash
grep -n '[—–]' index.html
```

Replace every one with a plain hyphen, adjusting spacing so the sentence still
reads correctly (`x — y` becomes `x - y`, `8–10` becomes `8-10`). Check the
rendered page afterwards: the range labels sit in fixed-width chips, so confirm
nothing reflows.

```bash
grep -c '[—–]' index.html    # expect 0
```

- [ ] **Step 6: Update the README**

- The "What it shows" section: correct the protocol count.
- Add to "Updating the data": every entry needs a `sources` array of at least one
  https URL, and `python3 -m unittest discover -s scripts/tests` enforces it
  along with score range, date sanity, and tag validity.

- [ ] **Step 7: Full verification**

```bash
python3 -m unittest discover -s scripts/tests -v
python3 scripts/fetch_metrics.py --dry-run > /dev/null && echo "pipeline ok"
grep -c 'id: "' index.html
```

Expected: all tests pass, pipeline exits 0, twenty ids.

Open the page and check at 380px, 768px, and full width: no horizontal scroll, the
columns stack cleanly, and twenty cards render with no console errors.

- [ ] **Step 8: Commit**

```bash
git add index.html README.md
git commit -m "Recalibrate scores across the full roster and refresh page furniture

<score changes and reasons, or 'no score changes needed after review'>
Rewrote the legal panel count for the twenty-protocol roster.
Replaced all em-dashes and en-dashes with plain hyphens.
STALE_AFTER_DAYS left at 180."
```

---

## Verification

Done when all of these hold:

```bash
python3 -m unittest discover -s scripts/tests -v   # all pass, no skips
python3 scripts/fetch_metrics.py --dry-run          # exit 0
grep -c 'id: "' index.html                          # 20
grep -c '[—–]' index.html                          # 0
```

- Every entry has at least one https source, enforced by test.
- No entry shows a "Review due" chip.
- `REGISTRY` plus `UNSOURCED` covers all twenty ids, each unsourced one with a
  real reason.
- The ranked list defends itself top to bottom.
- The bottom panels contain no count that the expansion invalidated.
- No bracketed placeholder (`<...>`, `N`, `YYYY-MM-DD`) survives anywhere in `DATA`.

## What this plan deliberately does not do

- **It does not hit twenty at any cost.** Any protocol whose research does not
  support a confident card gets dropped, with the reason recorded. Seventeen
  verified entries is a better map than twenty with three guesses.
- **It does not restructure the page.** One new tag type and one source-link row.
- **It does not touch the scoring rubric.** Scores move; the method for setting
  them does not.
