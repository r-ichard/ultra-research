# Packaging & publishing — ultra-research

This documents how the plugin is packaged, why it's built this way, and how to
publish it publicly. It is the spec the build follows.

## Goal

A **public** Claude Code plugin that any technical user can install and use **from any
folder**, driven entirely **through Claude** (the `research` skill) — no standalone CLI
required. The end-user experience target is: `/plugin install` → ask → it works.

## Why a single plugin (no PyPI)

The interface is "through Claude" only, so the Python tools never need to be a
standalone `pip`-installable CLI. That collapses what could have been two artifacts
(a PyPI package + a plugin) into **one GitHub repo that is both the plugin and its
marketplace**:

- The scripts are **bundled** in the plugin and called via `${CLAUDE_PLUGIN_ROOT}`,
  so they work regardless of the user's current directory.
- Python dependencies (`crawl4ai` + a headless Chromium) are installed at runtime into
  a **managed venv**, not into the user's environment — keeping the host clean.

## Components

```
.claude-plugin/plugin.json       plugin manifest (name: ultra-research)
.claude-plugin/marketplace.json  marketplace manifest (name: r-ichard, source: "./")
skills/research/
  SKILL.md                       the orchestrating skill (invoked /ultra-research:research
                                 or by natural language: "research X on the web")
  requirements.txt               deps installed into the managed venv
  scripts/bootstrap.py           silent installer + tool launcher (stdlib only)
  scripts/{lib,serp,fetch,extract_meta}.py   the engine + the two tools
```

Skills inside plugins are namespaced: this one is invoked as `/ultra-research:research`.
Natural-language triggers in the skill's `description` also activate it automatically.

**Two structural rules this layout enforces (both were real bugs once):**
- The engine lives **inside** the skill dir so `SKILL.md` can call it via
  `${CLAUDE_SKILL_DIR}/scripts/...` — the variable that is substituted into skill
  content. `${CLAUDE_PLUGIN_ROOT}` is only for hooks/MCP/LSP config, not skill bodies.
- `.gitignore` uses **root-anchored** `/research/` for output, so it can never match
  the `skills/research/` skill directory (an unanchored `research/` silently did).

## The silent bootstrap (key design decision)

`bootstrap.py` runs under the **system** python using only the standard library. On the
first tool call per machine it:

1. creates a venv at `$XDG_DATA_HOME/ultra-research/venv` (default `~/.local/share/...`),
2. `pip install`s `requirements.txt` into it,
3. runs `playwright install chromium` (~200 MB),
4. writes a `.ready` sentinel keyed to a hash of `requirements.txt`,
5. `os.execv`s the requested tool (`serp`/`fetch`) under the venv python.

The sentinel makes the happy path instant; changing `requirements.txt` triggers a
re-install automatically. All install output goes to **stderr** so the tool's stdout
(SERP listing / JSON report) stays clean for Claude to parse.

### Consent & transparency model

- **Silent at runtime, by explicit decision.** The first run installs without any
  message or prompt. The `/plugin install` action is treated as the user's consent.
- **Disclosed in the docs.** The README's "What happens on first use" section states
  exactly what is installed, where (`~/.local/share/ultra-research/`, outside the
  project), the ~200 MB size, the once-per-machine nature, the only network traffic,
  and a one-line uninstall. The skill carries a comment marking the silence as
  intentional so it isn't "fixed" later.

This is the deliberate split: **consent = the install action; transparency = the docs**,
not a runtime interruption.

## No-pollution guarantee

- The **only** thing written into a user's project is `research/` in the cwd (one
  subfolder per topic; `.staging/` auto-gitignored). Removable with `rm -rf research/`.
- The heavy engine lives in a machine-global cache outside the project, removable with
  `rm -rf ~/.local/share/ultra-research`.

## Security hardening (applied)

Audited before first publish; the following mitigations are in place:

- **Path containment** (`fetch.py`): `--keep`/`--drop` accept only a real staged file
  (`.staging/<12-hex>.md`) under the cwd; `--stage` refuses absolute paths and `..`.
  This blocks a prompt-injected command from deleting/overwriting arbitrary files.
- **Prompt-injection guardrail** (`SKILL.md`): fetched content is treated as inert DATA,
  never as instructions — it can't change the plan, paths, or commands.
- **URL allowlist** (`lib.py:_ensure_safe_url`): rejects non-`http(s)` schemes and hosts
  resolving to loopback / link-local / private / reserved addresses (SSRF / `file://` /
  cloud-metadata defense). Best-effort; does not cover DNS rebinding.
- **Pinned dependencies** (`requirements.txt`): `crawl4ai` pinned exactly; parsing deps
  capped below their next major so the silent installer can't auto-pull an unreviewed
  release.
- **Responsible-use notice** (`README.md`): ToS / robots / rate-limit / no-paywall-bypass.

Clean at the language level: no `shell=True`, `eval`, `exec`, `os.system`, `pickle`, or
`yaml.load`; `subprocess`/`os.execv` use list-arg form; committed filenames are sanitized.

## Publishing checklist

1. Push this directory to a public GitHub repo `r-ichard/ultra-research`
   (update the `homepage`/`repository` URLs in `plugin.json` if the slug differs).
2. Tag a release (e.g. `v0.1.0`). Plugins may omit `version` to use the commit SHA,
   but a tag gives users a stable `ref`.
3. Users install with:
   ```
   /plugin marketplace add r-ichard/ultra-research
   /plugin install ultra-research
   ```
4. Announce the natural-language trigger ("research X on the web") and the explicit
   `/ultra-research:research` form.

## Open items / future

- **crawl4ai-only engine** (current decision): full stealth on every fetch. A future
  "lightweight mode" could fall back to Claude Code's built-in WebFetch when the browser
  isn't wanted, with crawl4ai as the stealth upgrade. Deferred.
- **Linux OS deps** for headless Chromium are documented in the README rather than
  auto-installed (they need root and vary by distro).
- **Versioning** is single-track at `0.1.0` for the whole plugin.
