# crypto-privacy-map

**Default vs opt-in privacy: the truth behind the protocols.**

A single-page, visual map that grades crypto privacy protocols by how much privacy
they actually deliver — not by marketing. The core thesis: **privacy that is on by
default beats privacy you have to opt into**, because if people *can* skip privacy,
most of them will, and a small anonymity set protects no one.

🔗 **Live:** https://atraxsrc.github.io/crypto-privacy-map/

---

## What it shows

Protocols are split into two columns and scored `0–10`:

| Column | Meaning |
| --- | --- |
| 🔒 **Private by default** | Every transaction is private with no user action (e.g. Monero). |
| ⚠️ **Opt-in privacy** | The user must choose privacy; most transactions stay public (e.g. Zcash shielded, mixers). |

Each card carries a privacy grade, the underlying tech, key caveats, status tags
(legal risk, adoption, etc.), and the date it was last reviewed.

## How scores work

Scores are an **opinionated synthesis**, not a precise metric — they rank real-world
privacy, weighing five factors:

1. **Default vs opt-in** — always-on privacy beats privacy you choose (biggest factor).
2. **Anonymity set** — how large a crowd you blend into.
3. **Cryptographic strength** — ring signatures, zk-SNARKs, MimbleWimble, CoinJoin, etc.
4. **Real adoption** — what share of transactions are actually private.
5. **Maturity & standing** — battle-testing, audits, and legal/operational health.

Grade bands: **8–10 High** · **6–7 Medium** · **4–5 Low**. The full breakdown lives in
the *How the scores work* section on the page.

## Staying current

The privacy landscape shifts fast (sanctions, arrests, delistings, adoption swings), so
the project is built to stay fresh:

- **Data-driven** — every protocol lives in one `DATA` array in `index.html`. Update a
  score or fact in one line; the grade colour and bar derive from the score automatically.
- **Per-entry review dates** — each entry has a `reviewed` date. Anything older than
  `STALE_AFTER_DAYS` (180) is flagged with a *Review due* chip, and the footer tallies how
  many entries need a refresh.
- **Automated watch** — a weekly cloud agent researches each protocol for material changes
  and opens a PR (confirmed, sourced changes) or an issue (unverified leads) when the data
  drifts.

## Updating the data

1. Open `index.html` and find the `DATA` array near the bottom.
2. Edit the relevant entry — `score`, `body`, `tags`, etc.
3. Bump that entry's `reviewed` date and the global `LAST_REVIEWED` to today.
4. Open it in a browser to check, then commit.

No build step, no dependencies — it's a single static HTML file.

## Tech

Plain HTML/CSS/JS, no framework. JetBrains Mono + a Tokyo Night palette.

## Disclaimer

Educational research only. Not financial or legal advice. Privacy laws and the legal
status of these tools vary by jurisdiction and change over time — do your own research.
