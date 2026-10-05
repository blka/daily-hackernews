"""Build the static digest site (GitHub Pages) from daily-digest issues.

Usage: python -m daily_hackernews.site [output_dir]  (default: ./site)
"""

from __future__ import annotations

import html
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
    digests = unique

    os.makedirs(os.path.join(out_dir, "digests"), exist_ok=True)

    page_writes = []
    for d in digests:
        year, month, day = d["date"]
        page_path = f"digests/{year}-{month}-{day}.html"
        page = _page(f"<h1>{html.escape(d['title'], quote=False)}</h1>\n{_body_to_html(d['body'])}")
        with open(os.path.join(out_dir, page_path), "w", encoding="utf-8") as f:
            f.write(page)
        page_writes.append((page_path, year, d["title"]))

    latest = page_writes[0] if page_writes else None
    index = "<h1>Daily Hacker News</h1>\n"
    if latest:
        page_path, year, title = latest
        index += f'\n<h2><a href="{page_path}">{html.escape(title, quote=False)}</a></h2>'
        index += "\n" + _body_to_html(digests[0]["body"])

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