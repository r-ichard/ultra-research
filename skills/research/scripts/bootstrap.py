#!/usr/bin/env python3
"""Silent first-run bootstrap for ultra-research.

Runs under the SYSTEM python (stdlib only — no third-party imports here). It
guarantees a managed virtualenv with crawl4ai + a headless Chromium browser
exists, then hands the requested tool over to that venv's python.

Invoked by the skill (never by the user directly):

    python3 "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" serp  <engine> "<query>"
    python3 "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" fetch <url> --stage <folder>
    python3 "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" fetch --keep <path> --rank N --engine X
    python3 "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" fetch --drop <path>

Silent by design (disclosed in the README, not at runtime): the first run
installs ~200 MB ONCE PER MACHINE under $XDG_DATA_HOME/ultra-research
(default ~/.local/share/ultra-research), entirely outside the user's project.
Subsequent runs find it ready and skip straight to the tool.

All setup output is sent to stderr so the tool's real stdout (the SERP listing
or the JSON quality report) stays clean for the caller to parse.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent           # skills/research/scripts
REQUIREMENTS = SCRIPTS.parent / "requirements.txt"   # skills/research/requirements.txt

TOOLS = {"serp": SCRIPTS / "serp.py", "fetch": SCRIPTS / "fetch.py"}


def _data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "ultra-research"


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _requirements_hash() -> str:
    data = REQUIREMENTS.read_bytes() if REQUIREMENTS.exists() else b""
    return hashlib.sha256(data).hexdigest()[:16]


def ensure_env() -> Path:
    """Create the venv + install deps + browser if missing or stale.
    Returns the path to the venv's python. Idempotent and quiet on the happy path."""
    home = _data_home()
    venv_dir = home / "venv"
    py = _venv_python(venv_dir)
    ready = home / ".ready"
    want = _requirements_hash()

    # Fast path: already provisioned for the current requirements.
    if py.exists() and ready.exists() and ready.read_text().strip() == want:
        return py

    home.mkdir(parents=True, exist_ok=True)
    if not py.exists():
        print("[ultra-research] first-run setup: creating environment…", file=sys.stderr)
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    # Install/refresh dependencies into the managed venv (output -> stderr).
    subprocess.run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
                   check=True, stdout=sys.stderr)
    subprocess.run([str(py), "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS)],
                   check=True, stdout=sys.stderr)
    # Download the headless browser crawl4ai/Playwright drives (~200 MB, once).
    subprocess.run([str(py), "-m", "playwright", "install", "chromium"],
                   check=True, stdout=sys.stderr)

    ready.write_text(want)
    print("[ultra-research] setup complete.", file=sys.stderr)
    return py


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in TOOLS:
        sys.exit(f"usage: bootstrap.py {{{'|'.join(TOOLS)}}} <args...>")
    tool, rest = sys.argv[1], sys.argv[2:]
    py = ensure_env()
    # Replace this process with the tool running under the venv python.
    os.execv(str(py), [str(py), str(TOOLS[tool]), *rest])


if __name__ == "__main__":
    main()
