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
    """Escape the raw markdown, then convert to HTML."""
    return markdown(html.escape(body, quote=False), extensions=["extra"])


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
        batch = [i for i in resp.json() if "pull_request" not in i]
        issues.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return issues


def build_site(issues: list[dict], out_dir: str) -> None:
    """Render index.html and digests/<YYYY>-<MM>-<DD>.html into out_dir."""
    digests = [
        {"date": parse_issue_date(i["title"]), "title": i["title"], "html_url": i["html_url"], "body": i["body"] or ""}
        for i in issues
        if parse_issue_date(i["title"]) is not None
    ]
    # newest first (titles sort by day/month/year strings)
    digests.sort(key=lambda d: d["date"], reverse=True)

    os.makedirs(os.path.join(out_dir, "digests"), exist_ok=True)

    index_links = []
    for d in digests:
        year, month, day = d["date"]
        page_path = f"digests/{year}-{month}-{day}.html"
        page = _page(f"<h1>{d['title']}</h1>\n{_body_to_html(d['body'])}")
        with open(os.path.join(out_dir, page_path), "w") as f:
            f.write(page)
        index_links.append((page_path, d["title"]))

    latest = digests[0] if digests else None
    index = "<h1>Daily Hacker News</h1>\n<nav>"
    index += "".join(f'\n<a href="{p}">{t}</a>' for p, t in index_links)
    index += "</nav>\n"
    if latest:
        year, month, day = latest["date"]
        index += f'\n<h2><a href="digests/{year}-{month}-{day}.html">{latest["title"]}</a></h2>'
        index += "\n" + _body_to_html(latest["body"])
    with open(os.path.join(out_dir, "index.html"), "w") as f:
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