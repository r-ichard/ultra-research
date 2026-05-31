"""Test suite for date-boundary and date-coherence features.

Run directly:
    cd skills/research/scripts && python3 test_date_features.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure imports resolve against the scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import serp_url, TIME_PARAMS
from fetch import _date_coherence


def test_time_params_structure() -> None:
    assert set(TIME_PARAMS.keys()) == {"google", "brave", "duckduckgo"}
    assert set(TIME_PARAMS["google"].keys()) == {"day", "week", "month", "month6", "year"}
    assert set(TIME_PARAMS["brave"].keys()) == {"day", "week", "month", "year"}
    assert set(TIME_PARAMS["duckduckgo"].keys()) == {"day", "week", "month", "year"}
    print("  ✓ TIME_PARAMS structure")


def test_serp_url_google() -> None:
    assert "tbs=qdr:d,sbd:1" in serp_url("google", "bun vs node", "day")
    assert "tbs=qdr:w,sbd:1" in serp_url("google", "bun vs node", "week")
    assert "tbs=qdr:m,sbd:1" in serp_url("google", "bun vs node", "month")
    assert "tbs=qdr:m6,sbd:1" in serp_url("google", "bun vs node", "month6")
    assert "tbs=qdr:y,sbd:1" in serp_url("google", "bun vs node", "year")
    assert "tbs=" not in serp_url("google", "bun vs node")
    assert "tbs=" not in serp_url("google", "bun vs node", "invalid")
    print("  ✓ Google --when URLs")


def test_serp_url_brave() -> None:
    assert "tf=pd" in serp_url("brave", "bun vs node", "day")
    assert "tf=pw" in serp_url("brave", "bun vs node", "week")
    assert "tf=pm" in serp_url("brave", "bun vs node", "month")
    assert "tf=p1y" in serp_url("brave", "bun vs node", "year")
    assert "tf=" not in serp_url("brave", "bun vs node")
    assert "tf=" not in serp_url("brave", "bun vs node", "month6")  # unsupported → omit
    print("  ✓ Brave --when URLs")


def test_serp_url_duckduckgo() -> None:
    assert "df=d" in serp_url("duckduckgo", "bun vs node", "day")
    assert "df=w" in serp_url("duckduckgo", "bun vs node", "week")
    assert "df=m" in serp_url("duckduckgo", "bun vs node", "month")
    assert "df=y" in serp_url("duckduckgo", "bun vs node", "year")
    assert "df=" not in serp_url("duckduckgo", "bun vs node")
    assert "df=" not in serp_url("duckduckgo", "bun vs node", "month6")  # unsupported → omit
    print("  ✓ DuckDuckGo --when URLs")


def test_serp_url_unsupported_engine() -> None:
    # Bing has no TIME_PARAMS entry → any 'when' should be silently ignored
    url = serp_url("bing", "bun vs node", "month")
    assert "month" not in url
    assert "bun+vs+node" in url
    print("  ✓ Unsupported engine silently omits time param")


def test_date_coherence_fresh() -> None:
    now = datetime.now(timezone.utc)
    half_day = (now - timedelta(hours=12)).isoformat()
    two_days = (now - timedelta(days=2)).isoformat()
    assert _date_coherence(half_day, "unknown", "day") == "fresh"
    assert _date_coherence(two_days, "unknown", "week") == "fresh"
    print("  ✓ date_coherence fresh")


def test_date_coherence_stale() -> None:
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=60)).isoformat()
    assert _date_coherence(old, "unknown", "month") == "stale"
    assert _date_coherence(old, "unknown", "year") == "fresh"
    print("  ✓ date_coherence stale")


def test_date_coherence_unknown() -> None:
    assert _date_coherence("unknown", "unknown", "month") == "unknown"
    assert _date_coherence("", "", "week") == "unknown"
    print("  ✓ date_coherence unknown")


def test_date_coherence_no_when() -> None:
    assert _date_coherence("2023-01-01", "unknown", None) == "n/a"
    assert _date_coherence("2023-01-01", "unknown", "") == "n/a"
    print("  ✓ date_coherence n/a when no window")


def test_date_coherence_updated_trumps_published() -> None:
    now = datetime.now(timezone.utc)
    old_pub = (now - timedelta(days=60)).isoformat()
    new_upd = (now - timedelta(hours=12)).isoformat()
    assert _date_coherence(old_pub, new_upd, "day") == "fresh"
    assert _date_coherence(old_pub, new_upd, "week") == "fresh"
    print("  ✓ date_coherence updated trumps published")


def test_date_coherence_ambiguous() -> None:
    # Unparseable date string should return ambiguous
    assert _date_coherence("not-a-date", "unknown", "month") == "ambiguous"
    print("  ✓ date_coherence ambiguous")


def main() -> int:
    print("\n▶ test_date_features.py")
    tests = [
        test_time_params_structure,
        test_serp_url_google,
        test_serp_url_brave,
        test_serp_url_duckduckgo,
        test_serp_url_unsupported_engine,
        test_date_coherence_fresh,
        test_date_coherence_stale,
        test_date_coherence_unknown,
        test_date_coherence_no_when,
        test_date_coherence_updated_trumps_published,
        test_date_coherence_ambiguous,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  ✗ {t.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__} ERROR: {e}")
            failed += 1
    print()
    if failed:
        print(f"FAILED: {failed}/{len(tests)} test(s)")
        return 1
    print(f"PASSED: {len(tests)}/{len(tests)} tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
