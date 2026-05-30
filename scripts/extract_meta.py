"""Extract faithful page metadata: published / updated / author / org + char count.

Honesty rule (Foundation #1): never guess. Missing values are the literal
string "unknown" so the evidence locker doesn't fabricate provenance.
"""
from __future__ import annotations

import json
from typing import Optional

from bs4 import BeautifulSoup

UNKNOWN = "unknown"


def _meta(soup: BeautifulSoup, *keys: str) -> Optional[str]:
    for key in keys:
        for attr in ("property", "name", "itemprop"):
            tag = soup.find("meta", attrs={attr: key})
            if tag and tag.get("content"):
                return tag["content"].strip()
    return None


def _from_jsonld(soup: BeautifulSoup) -> dict:
    found = {}
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            found.setdefault("published", node.get("datePublished"))
            found.setdefault("updated", node.get("dateModified"))
            author = node.get("author")
            if isinstance(author, dict):
                found.setdefault("author", author.get("name"))
            elif isinstance(author, str):
                found.setdefault("author", author)
            elif isinstance(author, list) and author:
                a0 = author[0]
                found.setdefault("author", a0.get("name") if isinstance(a0, dict) else a0)
            pub = node.get("publisher")
            if isinstance(pub, dict):
                found.setdefault("org", pub.get("name"))
    return {k: v for k, v in found.items() if v}


def extract_metadata(html: str, markdown: str, crawl_meta: Optional[dict] = None) -> dict:
    soup = BeautifulSoup(html or "", "lxml")
    jsonld = _from_jsonld(soup)
    crawl_meta = crawl_meta or {}

    published = jsonld.get("published") or _meta(
        soup, "article:published_time", "datePublished", "publish-date", "date")
    updated = jsonld.get("updated") or _meta(
        soup, "article:modified_time", "dateModified", "og:updated_time", "lastmod")
    author = jsonld.get("author") or _meta(soup, "author", "article:author") or crawl_meta.get("author")
    org = jsonld.get("org") or _meta(soup, "og:site_name") or crawl_meta.get("site_name")
    title = (soup.title.get_text(strip=True) if soup.title else None) or crawl_meta.get("title")

    return {
        "title": title or UNKNOWN,
        "published": published or UNKNOWN,
        "updated": updated or UNKNOWN,
        "author": author or UNKNOWN,
        "org": org or UNKNOWN,
        "char_count": len(markdown or ""),
    }
