"""Thin crawl4ai layer for LLM-driven web research.

Design: Claude (the agent) is the intelligence — it reads SERPs, picks links, and
judges page content. These functions are deliberately dumb tools:
  - fetch a URL through a stealth browser (search IS crawl)
  - return clean article markdown (crawl4ai PruningContentFilter -> fit_markdown)
  - surface quality signals so Claude can decide keep/skip BEFORE saving

Grounded in crawl4ai 0.8.6 docs: enable_stealth + magic + simulate_user +
override_navigator (anti-bot), DefaultMarkdownGenerator + PruningContentFilter
(clean content), result.links (link discovery), status/length (quality gate).
"""
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import socket
import sys
from dataclasses import dataclass, field
from typing import Optional
import base64
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

_ALLOWED_SCHEMES = ("http", "https")


def _ensure_safe_url(url: str) -> None:
    """SSRF / local-file defense: reject non-http(s) schemes and any host that
    resolves to a loopback / link-local / private / reserved address (e.g.
    file://, http://localhost, the 169.254.169.254 cloud-metadata endpoint,
    internal RFC-1918 services). Best-effort — does not defend against DNS
    rebinding (the browser re-resolves), but blocks the obvious internal targets."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"non-http(s) URL not allowed: {url}")
    host = parsed.hostname
    if not host:
        raise ValueError(f"URL has no host: {url}")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return  # unresolvable — let the browser surface the DNS error
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"blocked private/internal address {ip} for host {host}")

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

# SERP URL templates only — NO per-engine parsing. Claude reads the links.
ENGINES: dict[str, str] = {
    "google": "https://www.google.com/search?q={q}&hl=en&num=20",
    "brave": "https://search.brave.com/search?q={q}",
    "duckduckgo": "https://html.duckduckgo.com/html/?q={q}",
    "bing": "https://www.bing.com/search?q={q}&count=20&setlang=en-US&mkt=en-US",
    "qwant": "https://lite.qwant.com/?q={q}&t=web",
}

_CONSENT_COOKIES = [
    {"name": "CONSENT", "value": "YES+", "domain": ".google.com", "path": "/"},
    {"name": "SOCS", "value": "CAI", "domain": ".google.com", "path": "/"},
]

# Phrases that hint at a paywall / login wall (Claude makes the final call).
_PAYWALL_HINTS = (
    "subscribe to continue", "subscribers only", "subscription", "create a free account",
    "create an account to", "sign in to read", "log in to continue", "register to continue",
    "this content is for", "members only", "metered", "you've reached your",
    "to continue reading", "already a subscriber", "start your free trial",
)

# Engine/infra hosts that are never organic results.
_INFRA = ("google.", "gstatic.", "googleusercontent.", "bing.com/ck", "microsoft.",
          "msn.com/", "brave.com", "duckduckgo.com", "qwant.com", "policies.",
          "support.", "accounts.", "go.microsoft", "javascript:", "#")


@dataclass
class Page:
    requested_url: str
    final_url: str
    success: bool
    status_code: Optional[int]
    raw_markdown: str
    fit_markdown: str
    html: str = ""
    metadata: dict = field(default_factory=dict)
    external_links: list[dict] = field(default_factory=list)
    internal_links: list[dict] = field(default_factory=list)

    # --- quality signals for the keep/skip gate ---
    @property
    def raw_len(self) -> int:
        return len(self.raw_markdown or "")

    @property
    def fit_len(self) -> int:
        return len(self.fit_markdown or "")

    @property
    def fit_ratio(self) -> float:
        return round(self.fit_len / self.raw_len, 3) if self.raw_len else 0.0

    @property
    def looks_empty(self) -> bool:
        return self.fit_len < 300

    @property
    def paywall_hits(self) -> list[str]:
        low = (self.fit_markdown or self.raw_markdown or "").lower()[:4000]
        return [h for h in _PAYWALL_HINTS if h in low]

    @property
    def blocked_status(self) -> bool:
        return self.status_code in (401, 402, 403, 429)


def serp_url(engine: str, query: str) -> str:
    return ENGINES[engine].format(q=quote_plus(query))


def _browser() -> BrowserConfig:
    return BrowserConfig(
        headless=True,
        enable_stealth=True,
        user_agent_mode="random",
        cookies=_CONSENT_COOKIES,
        verbose=False,
    )


def _run(clean: bool) -> CrawlerRunConfig:
    gen = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.5, threshold_type="dynamic",
                                            min_word_threshold=20),
        options={"ignore_links": True},
    ) if clean else DefaultMarkdownGenerator()
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        magic=True,
        simulate_user=True,
        override_navigator=True,
        delay_before_return_html=2.0,
        page_timeout=30000,
        markdown_generator=gen,
    )


def _md(result, attr: str) -> str:
    md = getattr(result, "markdown", None)
    if md is None:
        return ""
    return getattr(md, attr, None) or (str(md) if attr == "raw_markdown" else "")


def unwrap_redirect(href: str) -> str:
    """Resolve engine redirect wrappers to the real destination URL.
    DuckDuckGo: //duckduckgo.com/l/?uddg=<enc>. Bing: bing.com/ck/a?...&u=a1<b64url>."""
    if "duckduckgo.com/l/" in href and "uddg=" in href:
        target = parse_qs(urlparse(href).query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    if "bing.com/ck/" in href:
        u = parse_qs(urlparse(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            try:
                pad = "=" * (-len(u[2:]) % 4)
                return base64.urlsafe_b64decode(u[2:] + pad).decode("utf-8", "ignore")
            except Exception:
                pass
    return href if href.startswith("http") else ("https:" + href if href.startswith("//") else href)


def is_organic(href: str) -> bool:
    if not href or not href.startswith("http"):
        return False
    low = href.lower()
    host = (urlparse(href).netloc or "").lower()
    return not any(frag in low or frag in host for frag in _INFRA)


async def fetch(url: str, *, clean: bool = True,
                crawler: Optional[AsyncWebCrawler] = None) -> Page:
    """Fetch one URL through the stealth browser. clean=True applies the content
    filter (use for article pages); clean=False keeps raw (use for SERPs)."""
    _ensure_safe_url(url)
    own = crawler is None
    # crawl4ai logs progress banners ([FETCH]/[SCRAPE]/[COMPLETE]) to stdout even
    # with verbose=False; redirect them to stderr so the tools' stdout carries ONLY
    # their own output (the SERP listing / the JSON quality report) for clean parsing.
    with contextlib.redirect_stdout(sys.stderr):
        if own:
            crawler = AsyncWebCrawler(config=_browser())
            await crawler.start()
        try:
            res = await crawler.arun(url=url, config=_run(clean))
            links = getattr(res, "links", None) or {}
            page = Page(
                requested_url=url,
                final_url=getattr(res, "redirected_url", None) or res.url,
                success=bool(res.success),
                status_code=getattr(res, "status_code", None),
                raw_markdown=_md(res, "raw_markdown"),
                fit_markdown=_md(res, "fit_markdown") or _md(res, "raw_markdown"),
                html=res.html or "",
                metadata=getattr(res, "metadata", None) or {},
                external_links=links.get("external", []) or [],
                internal_links=links.get("internal", []) or [],
            )
        finally:
            if own:
                await crawler.close()
    return page


def detect_block(page: "Page") -> Optional[str]:
    """Return a reason string if the SERP looks blocked/captcha'd, else None."""
    final = (page.final_url or "").lower()
    if "/sorry/" in final or "captcha" in final:
        return "captcha / anti-bot wall (redirected to a block page)"
    if page.blocked_status:
        return f"blocked status {page.status_code}"
    low = (page.html or "").lower()
    if "unusual traffic" in low or "our systems have detected" in low:
        return "'unusual traffic' anti-bot page"
    return None


async def serp_candidates(engine: str, query: str) -> dict:
    """Fetch a SERP and return candidate links for Claude to pick from, plus a
    block signal so a CAPTCHA/anti-bot wall isn't mistaken for 'no results'.
    Light infra filtering only — relevance judgment is Claude's job."""
    page = await fetch(serp_url(engine, query), clean=False)
    blocked = detect_block(page)
    out, seen = [], set()
    if not blocked:
        # Some engines (DuckDuckGo, Bing) wrap results in same-domain redirect
        # links, which crawl4ai files as "internal" — so scan both buckets.
        for link in page.external_links + page.internal_links:
            href = unwrap_redirect(link.get("href", ""))
            if not is_organic(href) or href in seen:
                continue
            seen.add(href)
            out.append({
                "href": href,
                "text": (link.get("text") or "").strip()[:120],
                "context": (link.get("context") or "").strip()[:200],
            })
    return {"engine": engine, "query": query, "blocked": blocked,
            "final_url": page.final_url, "links": out}
