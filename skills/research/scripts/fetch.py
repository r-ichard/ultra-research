"""Tool 2: fetch a page, report quality signals, and STAGE it (don't commit).

The flow that satisfies "look at the content before deciding to download":
  1. `fetch <url> --stage <folder>` fetches ONCE, writes the clean markdown to
     <folder>/.staging/<hash>.md, and prints a quality REPORT + content preview.
  2. Claude inspects the report+preview. Paywall? empty? off-topic? -> skip.
  3. Keep  -> `fetch --keep <staged_path> --rank N --engine X`  (just renames; no re-fetch)
     Skip  -> `fetch --drop <staged_path>`                       (deletes the staged file)

So a page is only committed to the evidence locker after Claude has read it.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import fetch as fetch_page  # noqa: E402
from extract_meta import extract_metadata  # noqa: E402

STAGING = ".staging"
_STAGED_HASH = re.compile(r"^[0-9a-f]{12}\.md$")


def _slug(text: str, n: int = 50) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n]) or "page"


def _under_cwd(p: Path) -> Path:
    """Resolve p (relative to cwd) and refuse if it escapes the current directory.
    Blocks absolute paths and `..` traversal so writes/deletes stay in the project."""
    cwd = Path.cwd().resolve()
    rp = (cwd / p).resolve()
    if rp != cwd and cwd not in rp.parents:
        raise SystemExit(f"refusing: path escapes the current directory: {p}")
    return rp


def _safe_stage_dir(folder) -> Path:
    """--stage may only target a folder under the cwd (no absolute paths, no ..)."""
    return _under_cwd(Path(folder))


def _validate_staged(staged) -> Path:
    """--keep/--drop accept ONLY a real staged file: <...>/.staging/<12-hex>.md under
    the cwd. Prevents a prompt-injected command from deleting/overwriting arbitrary files."""
    p = Path(staged)
    if p.parent.name != STAGING or not _STAGED_HASH.match(p.name):
        raise SystemExit(f"refusing: not a staged file ({staged}); expected {STAGING}/<hash>.md")
    return _under_cwd(p)


def _frontmatter(meta: dict, final_url: str, engine: str, rank, fetched_at: str) -> str:
    def esc(v):
        v = str(v).replace("\n", " ").strip()
        return '"' + v.replace('"', '\\"') + '"' if any(c in v for c in ':#"\'') else v
    fields = {
        "url": final_url, "title": meta.get("title", "unknown"), "engine": engine,
        "rank": rank, "published": meta.get("published", "unknown"),
        "updated": meta.get("updated", "unknown"), "author": meta.get("author", "unknown"),
        "org": meta.get("org", "unknown"), "char_count": meta.get("char_count", 0),
        "fetched_at": fetched_at,
    }
    body = "\n".join(f"{k}: {esc(v) if isinstance(v, str) else v}" for k, v in fields.items())
    return f"---\n{body}\n---\n"


async def do_stage(url: str, folder: Path) -> None:
    folder = _safe_stage_dir(folder)
    page = await fetch_page(url, clean=True)
    # Rich metadata (published/updated/author/org) comes from the page HTML (JSON-LD,
    # meta tags); char_count reflects the CLEAN article content.
    meta = extract_metadata(page.html, page.fit_markdown, page.metadata)
    meta["char_count"] = page.fit_len

    stage_dir = folder / STAGING
    stage_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(page.final_url.encode()).hexdigest()[:12]
    staged = stage_dir / f"{h}.md"
    fetched_at = datetime.now(timezone.utc).isoformat()
    staged.write_text(
        _frontmatter(meta, page.final_url, "?", "?", fetched_at) + "\n" +
        (page.fit_markdown or "_(empty)_") + "\n", encoding="utf-8")

    md = page.fit_markdown or ""
    report = {
        "requested_url": url,
        "final_url": page.final_url,
        "success": page.success,
        "status_code": page.status_code,
        "blocked_status": page.blocked_status,
        "title": meta.get("title", "unknown"),
        "author": meta.get("author", "unknown"),
        "org": meta.get("org", "unknown"),
        "published": meta.get("published", "unknown"),
        "raw_len": page.raw_len,
        "fit_len": page.fit_len,
        "fit_ratio": page.fit_ratio,
        "looks_empty": page.looks_empty,
        "paywall_hits": page.paywall_hits,
        "staged_path": str(staged),
        "preview_head": md[:1200],
        "preview_tail": md[-500:] if len(md) > 1700 else "",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def do_keep(staged: Path, rank, engine: str) -> None:
    staged = _validate_staged(staged)
    text = staged.read_text(encoding="utf-8")
    # patch engine + rank into the staged front-matter placeholders
    text = re.sub(r"^engine: \?$", f"engine: {engine}", text, count=1, flags=re.M)
    text = re.sub(r"^rank: \?$", f"rank: {rank}", text, count=1, flags=re.M)
    title = (re.search(r'^title: "?(.*?)"?$', text, flags=re.M) or [None, "page"])[1]
    host = ""
    m = re.search(r"^url: \"?(.*?)\"?$", text, flags=re.M)
    if m:
        host = urlparse(m[1]).netloc.replace("www.", "")
    final = staged.parent.parent / f"{int(rank):02d}-{_slug(host)}-{_slug(title, 40)}.md"
    final.write_text(text, encoding="utf-8")
    staged.unlink(missing_ok=True)
    print(f"kept -> {final}")


def do_drop(staged: Path) -> None:
    staged = _validate_staged(staged)
    staged.unlink(missing_ok=True)
    print(f"dropped {staged}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch + inspect + stage a page (commit only on --keep)")
    ap.add_argument("url", nargs="?", help="URL to fetch & stage")
    ap.add_argument("--stage", help="evidence-locker folder to stage into")
    ap.add_argument("--keep", help="staged path to commit into the locker")
    ap.add_argument("--drop", help="staged path to delete")
    ap.add_argument("--rank", default=99, help="rank to assign when keeping")
    ap.add_argument("--engine", default="?", help="engine attribution when keeping")
    args = ap.parse_args()

    if args.keep:
        do_keep(Path(args.keep), args.rank, args.engine)
    elif args.drop:
        do_drop(Path(args.drop))
    elif args.url and args.stage:
        try:
            asyncio.run(do_stage(args.url, Path(args.stage)))
        except ValueError as e:
            sys.exit(f"refusing to fetch: {e}")
    else:
        ap.error("provide either `<url> --stage DIR`, `--keep PATH`, or `--drop PATH`")


if __name__ == "__main__":
    main()
