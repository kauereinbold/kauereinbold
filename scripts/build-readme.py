#!/usr/bin/env python3
"""Regenerate the profile README's dynamic blocks.

Fills marker blocks in README.md:
  <!-- BLOG:START -->    ... <!-- BLOG:END -->
  <!-- OSS:START -->     ... <!-- OSS:END -->

Data sources: GitHub Search (merged PRs), Medium RSS.
(The "Currently" section is maintained by hand.)

Env: GH_TOKEN (required for API), GH_USER (default: kauereinbold),
     MEDIUM_USER (default: kauereinbold).
"""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

USER = os.environ.get("GH_USER", "kauereinbold")
MEDIUM_USER = os.environ.get("MEDIUM_USER", "kauereinbold")
TOKEN = os.environ.get("GH_TOKEN", "")

API = "https://api.github.com"
UA = "profile-readme-builder"


def _req(url, headers=None):
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def get_json(url):
    return json.loads(_req(url))


def clean(s):
    # never emit em/en dashes in generated content (style preference)
    return (s or "").replace("—", "-").replace("–", "-").strip()


def fetch_blog(n=3):
    try:
        xml = _req(f"https://medium.com/feed/@{MEDIUM_USER}")
    except Exception as e:
        print(f"blog fetch failed: {e}", file=sys.stderr)
        return "_No recent posts._"
    root = ET.fromstring(xml)
    items = root.findall(".//item")[:n]
    if not items:
        return "_No recent posts._"
    lines = []
    for it in items:
        title = clean(it.findtext("title"))
        link = (it.findtext("link") or "").split("?")[0].strip()
        lines.append(f"- [{title}]({link})")
    return "\n".join(lines)


def fetch_oss(n=5):
    if not TOKEN:
        return "_Set GH_TOKEN to populate._"
    try:
        url = (f"{API}/search/issues?q=is:pr+author:{USER}+is:merged"
               f"&sort=updated&order=desc&per_page=30")
        data = get_json(url)
    except Exception as e:
        print(f"oss fetch failed: {e}", file=sys.stderr)
        return "_No recent contributions._"
    lines = []
    for it in data.get("items", []):
        owner_repo = it["repository_url"].split("/")[-2:]
        owner, repo = owner_repo[0], "/".join(owner_repo)
        if owner.lower() == USER.lower():
            continue  # external open-source only
        date = (it.get("closed_at") or it.get("updated_at") or "")[:10]
        lines.append(f"- [`{repo}`]({it['html_url']}): {clean(it['title'])} ({date})")
        if len(lines) == n:
            break
    return "\n".join(lines) if lines else "_No recent external contributions._"


def inject(text, key, content):
    start, end = f"<!-- {key}:START -->", f"<!-- {key}:END -->"
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pat.search(text):
        print(f"marker {key} not found in README", file=sys.stderr)
        return text
    return pat.sub(f"{start}\n{content}\n{end}", text)


def main():
    text = README.read_text(encoding="utf-8")
    text = inject(text, "BLOG", fetch_blog())
    text = inject(text, "OSS", fetch_oss())
    README.write_text(text, encoding="utf-8")
    print("README regenerated.")


if __name__ == "__main__":
    main()
