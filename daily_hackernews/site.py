"""Build the static digest site (GitHub Pages) from daily-digest issues.

Usage: python -m daily_hackernews.site [output_dir]  (default: ./site)
"""

from __future__ import annotations

import html
import json
import os
import re
import sys

import requests
from markdown import markdown
import nh3

REPO_ISSUES_URL = "https://api.github.com/repos/blka/daily-hackernews/issues"

_DATE_RE = re.compile(r"Daily Hacker News (\d{2}[/\-]\d{2}[/\-]\d{4})")

_CSS = """
body { font-family: -apple-system, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }
h1, h2 { margin-top: 0; }
a { color: #0366d6; }
hr { border: none; border-top: 1px solid #ddd; }
blockquote { color: #555; border-left: 3px solid #ddd; margin: 0; padding-left: 1rem; }
code { background: #f6f8fa; padding: 0.1em 0.3em; border-radius: 3px; }
nav { margin: 0 0 1rem; }
"""

# Digests render h1-h6, lists, code, blockquote and links — nothing else is needed.
_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "a", "strong", "em", "code", "pre", "blockquote", "hr",
    "ul", "ol", "li", "br",
    "table", "thead", "tbody", "th", "tr", "td",
    "del", "span",
}


def parse_issue_date(title: str) -> tuple[str, str, str] | None:
    """Extract (year, month, day) from an issue title, or None."""
    m = _DATE_RE.search(title)
    if not m:
        return None
    day, month, year = re.split(r"/|-", m.group(1))
    return year, month, day


def issue_date(title: str) -> str:
    """Return the raw DD/MM/YYYY date from an issue title."""
    m = _DATE_RE.search(title)
    return m.group(1) if m else ""


def _body_to_html(body: str) -> str:
    """Escape the raw markdown, convert to HTML, sanitize the output."""
    raw = markdown(html.escape(body, quote=False), extensions=["extra"])
    return nh3.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https", "mailto"},
    )


def fetch_issues() -> list[dict]:
    """Fetch all issues labeled daily-digest, newest first."""
    issues: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            REPO_ISSUES_URL,
            params={"labels": "daily-digest", "per_page": 100, "page": page},
            timeout=30,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        raw = resp.json()
        issues.extend(i for i in raw if "pull_request" not in i)
        # Count the raw response: PRs filtered out would shrink a full page
        # and stop the fetch early.
        if len(raw) < 100:
            break
        page += 1
    return issues


def _write_digest_page(title: str, body: str, date: tuple[str, str, str], out_dir: str) -> str:
    """Write digests/<YYYY>-<MM>-<DD>.html into out_dir, return the page_path."""
    year, month, day = date
    page_path = f"digests/{year}-{month}-{day}.html"
    page = _page(f"<h1>{html.escape(title, quote=False)}</h1>\n{_body_to_html(body)}")
    os.makedirs(os.path.join(out_dir, "digests"), exist_ok=True)
    with open(os.path.join(out_dir, page_path), "w", encoding="utf-8") as f:
        f.write(page)
    return page_path


def _render_index(page_writes: list[tuple[str, str, str]], latest: dict | None, out_dir: str) -> None:
    """Render index.html: optional latest digest, then the collapsed archive."""
    index = "<h1>Daily Hacker News</h1>\n"
    if latest:
        page_path, title = latest["page_path"], latest["title"]
        index += f'\n<h2><a href="{page_path}">{html.escape(title, quote=False)}</a></h2>'
        index += "\n" + _body_to_html(latest["body"])

    # Collapsed archive, grouped by year — keeps the index short.
    index += '\n<hr>\n<details>\n<summary>Archive — all days</summary>\n'
    by_year: dict[str, list[str]] = {}
    for page_path, year, title in page_writes:
        by_year.setdefault(year, []).append(
            f'<li><a href="{page_path}">{html.escape(title, quote=False)}</a></li>'
        )
    for year in by_year:
        index += f"\n<strong>{year}</strong>\n<ul>" + "".join(by_year[year]) + "</ul>"
    index += "\n</details>\n"
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(_page(index))


MANIFEST_PATH = "manifest.json"
# One entry per built page: public issue data only.
_ENTRY_KEYS = {"page_path": str, "number": int, "title": str, "date": str, "body": str}


def write_manifest(out_dir: str, entries: list[dict]) -> None:
    """Write {"pages": entries} to out_dir/manifest.json."""
    with open(os.path.join(out_dir, MANIFEST_PATH), "w", encoding="utf-8") as f:
        json.dump({"pages": entries}, f, ensure_ascii=False)


def load_manifest(out_dir: str) -> list[dict] | None:
    """Read manifest.json back, or None when missing/corrupt."""
    try:
        with open(os.path.join(out_dir, MANIFEST_PATH), encoding="utf-8") as f:
            data = json.load(f)
        entries = data["pages"]
        if not isinstance(entries, list):
            return None
        for e in entries:
            if not isinstance(e, dict):
                return None
            for key, typ in _ENTRY_KEYS.items():
                if isinstance(typ, dict) or not isinstance(e.get(key), typ) or isinstance(e.get(key), bool):
                    return None
        dates = [e["date"] for e in entries]
        if len(set(dates)) != len(dates):
            return None
        return entries
    except (OSError, ValueError, KeyError, TypeError):
        return None


def build_site(issues: list[dict], out_dir: str) -> None:
    """Render index.html and digests/<YYYY>-<MM>-<DD>.html into out_dir."""
    digests = [
        {"date": parse_issue_date(i["title"]), "title": i["title"], "html_url": i["html_url"], "body": i["body"] or "", "number": i.get("number", 0) or 0}
        for i in issues
        if parse_issue_date(i["title"]) is not None
    ]
    # Newest first, then keep one issue per date — a repeated daily run produces
    # two issues with the same date, and one page must survive per date.
    digests.sort(key=lambda d: (d["date"], d["number"]), reverse=True)
    seen: set = set()
    unique = []
    for d in digests:
        if d["date"] in seen:
            continue
        seen.add(d["date"])
        unique.append(d)

    page_writes = [(_write_digest_page(d["title"], d["body"], d["date"], out_dir), d["date"][0], d["title"]) for d in unique]
    latest = {"page_path": page_writes[0][0], "title": page_writes[0][2], "body": unique[0]["body"]} if page_writes else None
    _render_index(page_writes, latest, out_dir)

    entries = [{"page_path": p, "number": d["number"], "title": d["title"],
                "date": "-".join(d["date"]), "body": d["body"]} for (p, _, _), d in zip(page_writes, unique)]
    write_manifest(out_dir, entries)


def _page(body_html: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Daily Hacker News</title>"
        f"<style>{_CSS}</style></head><body>\n"
        f"{body_html}\n</body></html>\n"
    )


def main(out_dir: str = "site") -> None:
    issues = fetch_issues()
    print(f"Fetched {len(issues)} digest issues")
    build_site(issues, out_dir)
    print(f"Site built in {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "site")