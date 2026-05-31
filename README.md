<!-- Optional: drop a banner image at docs/assets/hero.png and uncomment:
<p align="center"><img src="docs/assets/hero.png" alt="Ultra Research" width="820"></p>
-->

<div align="center">

# 🔎 Ultra Research

**Faithful web research for Claude Code — a folder of clean, cited markdown, not a black-box answer.**

*Aggregation, not synthesis.* Gather the real spread of human sources from the open web, then reason over them **on your terms** — every claim traceable to a file you can open.

<br/>

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-8A2BE2?logo=anthropic&logoColor=white)](#-quick-start)
[![Tests](https://github.com/r-ichard/ultra-research/actions/workflows/tests.yml/badge.svg)](https://github.com/r-ichard/ultra-research/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#requirements)
[![Built with crawl4ai](https://img.shields.io/badge/Built_with-crawl4ai-00b894)](https://docs.crawl4ai.com/)
[![Security: hardened](https://img.shields.io/badge/Security-hardened-success)](#-security)

[**Quick Start**](#-quick-start) · [**How It Works**](#-how-it-works--claude-is-the-browser) · [**What Gets Installed**](#-what-happens-on-first-use) · [**Security**](#-security) · [**Roadmap**](#-roadmap)

</div>

---

> **The goal isn't a confident-sounding answer that hides its sources — it's a durable, auditable folder of what real people actually wrote, so you can judge it yourself.**

AI search tools collapse the web into one smooth paragraph. That's convenient — and it's exactly where nuance, disagreement, and provenance go to die. **Ultra Research does the opposite:** it browses like a person, reads each page, keeps only the good ones, and hands you a **folder of clean markdown** — one file per source, with metadata — that you (or Claude, when *you* ask) reason over as a separate, explicit step.

> [!NOTE]
> Unofficial, community-built. Not affiliated with or endorsed by Anthropic.

## ✨ Why Ultra Research

|  | Typical AI search | **Ultra Research** |
|--|------------------|--------------------|
| **Output** | One synthesized answer | A folder of per-source markdown you can re-open |
| **Provenance** | Citations you can't easily audit | Every file carries `url · author · org · date` front-matter |
| **Disagreement** | Smoothed away | Preserved — minority views survive as their own files |
| **Who reasons** | The tool, invisibly | **You** — collection and reasoning are separate stages |
| **Page selection** | Opaque ranker | **Claude reads the results and picks**, then inspects each page before saving |
| **Date precision** | Opaque | `--when day|week|month|year` across engines + `date_coherence` check |
| **Search operators** | None | Claude uses `site:`, `"exact"`, `OR`, `-exclude`, `..range` natively |
| **Failures** | Hidden | Skips (paywall / empty / off-topic / stale date) are reported out loud |

## 🚀 Quick Start

```bash
# 1. Add this repo as a plugin marketplace
/plugin marketplace add r-ichard/ultra-research

# 2. Install the plugin
/plugin install ultra-research

# 3. Just ask — in any project, any folder:
"research whether bun is ready for production"
#   …or invoke explicitly:
/ultra-research:research
```

That's it. **No separate setup step** — the engine installs itself on first use (see below).

<details>
<summary><b>What a session actually looks like</b></summary>

```text
You:  research whether bun is ready for production

Ultra Research proposes a plan (and invites your input):
  engines : google · brave · duckduckgo
  variants: broad · "bun production problems" (contrarian) · bun site:reddit.com (channel)
  → "Add/drop/edit before I run — and any angles or sources of your own?"

You:  add a HN search, skip youtube

…then it browses, reading results and inspecting each page before saving:
  ✓ kept  01-dev-to-bun-in-production.md         (DEV, 2026-01)
  ✓ kept  02-reddit-com-switched-back-from-bun.md
  ⤫ skipped a paywalled infoq.com article
  ⤫ skipped an empty SPA shell

Captured 7 pages from 6 hosts → ./research/is-bun-ready-for-production-20260530/
  "Enough, or want me to re-run on a new axis?"
```
*Reasoning over the locker — compare viewpoints, steelman the minority, rank by recency — is a **separate** step you ask for explicitly.*

</details>

## 🤫 What happens on first use

The first time you run a research task, the plugin **silently** sets up its engine — no prompt, no interruption, by design:

- creates a managed Python virtualenv at `~/.local/share/ultra-research/`
- installs [`crawl4ai`](https://docs.crawl4ai.com/) into it (pinned versions)
- downloads a headless Chromium browser (~200 MB) via Playwright

This happens **once per machine** and lives **entirely outside your project**. Later runs reuse it with zero setup.

> [!IMPORTANT]
> **The only thing written into your project** is a single `research/` folder in your current directory. **The only outbound network traffic** is (a) this one-time install and (b) the pages you explicitly ask it to research. Nothing else.

```bash
# To remove everything:
rm -rf ~/.local/share/ultra-research   # the engine + browser
rm -rf research/                        # captured sources in a given project
```

<a name="requirements"></a>
**Requirements:** Python 3.10+ on your `PATH`. On minimal Linux hosts you may also need system libraries for headless Chromium (`playwright install-deps` or your distro's equivalent).

## 🧠 How it works — Claude is the browser

There are **no per-engine HTML parsers**. crawl4ai drives a real stealth browser; **Claude** reads the search results, decides which links to follow, and inspects each page's content *before* it's saved. Thin tools, smart LLM.

```text
        ┌──────────────────────── CLAUDE (the judgment) ────────────────────────┐
        │  plans the search · reads SERPs · picks links · inspects each page     │
        └───────┬───────────────────────────────────────────────────┬───────────┘
                ▼                                                     ▼
   ┌─────────────────────┐                              ┌──────────────────────────┐
   │  serp               │  candidate links             │  fetch                    │
   │  read & pick the    │ ───────────────────────────▶ │  fetch + clean + quality  │
   │  real organic ones  │                              │  report → STAGE (no save) │
   └─────────────────────┘                              └────────────┬──────────────┘
                                                                      ▼
                                            Claude inspects the report ── paywall? empty? off-topic?
                                                      │                              │
                                                    KEEP  ──▶ ./research/<topic>/   DROP (discard)
```

The `research` skill drives this with a **plan-first, human-confirmed** flow: it proposes a search plan, **invites your own thoughts and sources**, then browses, inspects, and saves — leaving reasoning over the locker as a separate, explicit step.

### 📁 The evidence locker

All output lands under a single `research/` folder in your current directory — never scattered, never outside the project:

```text
research/
└── is-bun-ready-for-production-20260530/
    ├── .staging/                          # scratch (auto-gitignored)
    ├── 01-dev-to-bun-in-production.md
    └── 02-reddit-com-switched-back-from-bun.md
```

Each committed file is a metadata front-matter header followed by **clean article markdown** (nav/ads/boilerplate stripped):

```yaml
---
url: "https://dev.to/last9/is-bun-production-ready-in-2026..."
title: Is Bun Production-Ready in 2026? A Practical Assessment
engine: duckduckgo
rank: 1
published: "2026-01-16T22:00:00Z"
author: Nishant Modak
org: DEV Community
char_count: 1419
fetched_at: "2026-05-30T13:37:28+00:00"
---
```

### 🔬 Quality gate — inspect before saving

A page reaches the locker only after Claude reads it. `fetch` surfaces the signals that drive the keep/skip call:

| signal | meaning |
|--------|---------|
| `blocked_status` | 401/402/403/429 — likely paywall / login / anti-bot |
| `paywall_hits` | matched paywall/login phrases in the content |
| `looks_empty` | clean content under ~300 chars |
| `fit_ratio` | clean-vs-raw length; very low = mostly boilerplate |
| `date_coherence` | `fresh` / `stale` / `unknown` / `ambiguous` against the requested `--when` window |
| `preview_head` / `title` | so Claude can judge relevance & appropriateness |

**Honesty rules:** missing metadata is written as `unknown` (never fabricated); skipped pages and engine failures are reported plainly.

## 🛡️ Responsible use

This tool drives a real browser with stealth settings so research fetches are *reliable* against pages that break plain HTTP clients. That comes with responsibilities:

- **Respect each site's Terms of Service, `robots.txt`, and rate limits.** This is for human-paced research, not bulk scraping.
- **It does not bypass paywalls** — paywalled pages are detected and *skipped*, by design.
- **Don't use it to access content you're not authorized to**, or to evade access controls.

## 🔒 Security

Audited and hardened before release:

- **Path containment** — `--keep`/`--drop` accept only a real staged file (`.staging/<hash>.md`) under the cwd; `--stage` refuses absolute paths and `..`. A prompt-injected command can't delete or overwrite arbitrary files.
- **Prompt-injection guardrail** — fetched page content is treated as inert **data, never instructions**.
- **SSRF / local-file defense** — non-`http(s)` schemes and loopback / link-local / private / cloud-metadata hosts are refused (no `file://`, `localhost`, `169.254.169.254`).
- **Supply chain** — dependencies are pinned so the silent installer can't auto-pull an unreviewed release.
- **Clean baseline** — no `shell=True`, `eval`, `exec`, `os.system`, `pickle`, or `yaml.load`; list-arg subprocess; dependencies isolated in a managed venv; **no telemetry**.

Full write-up: [`docs/PACKAGING.md`](docs/PACKAGING.md).

## 🏗️ Architecture

```text
.claude-plugin/
  plugin.json           plugin manifest
  marketplace.json      makes this repo installable as a marketplace
skills/research/
  SKILL.md              the plan-first, LLM-driven skill that orchestrates the tools
  requirements.txt      pinned deps (installed into the managed venv on first run)
  scripts/
    bootstrap.py        silent first-run installer; execs the tools through a managed venv
    lib.py              stealth crawl4ai fetch + clean markdown + quality signals + SERP discovery + TIME_PARAMS
    serp.py             tool 1: dump candidate result links for Claude to pick; supports --when
    fetch.py            tool 2: fetch + inspect + stage; --keep / --drop to commit or discard; supports --when + date_coherence
    extract_meta.py     published / updated / author / org from JSON-LD + meta tags
```

Engines are SERP URL templates in `lib.py` (`ENGINES`). `google` / `brave` / `duckduckgo` are reliable; `bing` is best-effort.

## 🗺️ Roadmap

- [x] **Date-bounded search** across engines (`--when day|week|month|month6|year`) with `date_coherence` validation
- [x] **Advanced operator awareness** — Claude uses `site:`, `"exact"`, `OR`, `-exclude`, `..range` natively
- [ ] Optional **lightweight mode** — fall back to Claude Code's built-in WebFetch when the browser isn't needed, with crawl4ai as the stealth upgrade
- [ ] `search.md` **manifest** for reproducible, re-runnable research sessions
- [ ] Source-family **triangulation** & content dedup
- [ ] Deeper crawling via crawl4ai `AdaptiveCrawler`

## 📄 License

[MIT](LICENSE) © Richard Raduly. Built on [crawl4ai](https://docs.crawl4ai.com/).

<div align="center">
<br/>
<sub>Stop trusting the smooth answer. Read the sources.</sub>
</div>
