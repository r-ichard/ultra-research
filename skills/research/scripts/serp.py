"""Tool 1: discover candidate result links from a search engine.

Claude calls this, READS the returned links, and decides which are real organic
results worth visiting. No parsing intelligence here — that's Claude's job.

Normally invoked through the silent bootstrap (so deps are guaranteed present):

    python3 "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" serp google "bun vs node"
    python3 "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" serp brave "..." --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import ENGINES, serp_candidates  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Discover candidate result links from a SERP")
    ap.add_argument("engine", choices=list(ENGINES))
    ap.add_argument("query")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a readable list")
    args = ap.parse_args()

    result = asyncio.run(serp_candidates(args.engine, args.query))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if result["blocked"]:
        print(f"# ⚠️  {args.engine} BLOCKED: {result['blocked']}")
        print(f"#    ({result['final_url']})")
        print("#    Fall back to another engine (brave / duckduckgo) for this query.")
        return
    links = result["links"]
    print(f"# {len(links)} candidate links from {args.engine} for: {args.query}\n")
    for i, l in enumerate(links, 1):
        print(f"{i:>2}. {l['text'] or '(no anchor text)'}")
        print(f"    {l['href']}")
        if l["context"]:
            print(f"    ↳ {l['context']}")


if __name__ == "__main__":
    main()
