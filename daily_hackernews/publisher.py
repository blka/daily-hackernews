"""Publish digest as a GitHub Issue."""

from __future__ import annotations

import json
import os
import re

import certifi
import requests

GITHUB_API_URL = "https://api.github.com/repos/blka/daily-hackernews/issues"


def create_issue(title: str, body: str, labels: list[str] | None = None) -> str:
    """Create a GitHub Issue and return its URL.

    Raises on non-201 status.
    """
    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise RuntimeError("ACCESS_TOKEN environment variable is not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {token}",
    }
    payload = {
        "title": title,
        "body": body,
        "labels": labels or ["daily-digest"],
    }

    resp = requests.post(
        GITHUB_API_URL, json=payload, headers=headers, verify=certifi.where(), timeout=30
    )
    if resp.status_code != 201:
        raise RuntimeError(
            f"Failed to create issue: {resp.status_code} {resp.text}"
        )

    data = json.loads(resp.text)
    return data["html_url"]


def find_issue_by_title(title: str) -> int | None:
    """Return the number of an existing daily-digest issue with this exact
    title, or None.

    Raises on a non-200 response: a guard error must be loud, not a silent
    pass-through to duplicate creation.
    """
    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise RuntimeError("ACCESS_TOKEN environment variable is not set")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}",
    }
    page = 1
    while True:
        resp = requests.get(
            GITHUB_API_URL,
            params={"labels": "daily-digest", "per_page": 100, "page": page},
            headers=headers,
            verify=certifi.where(),
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to list issues: {resp.status_code} {resp.text}")
        raw = resp.json()
        issues = [i for i in raw if "pull_request" not in i]
        for issue in issues:
            if issue.get("title") == title:
                return issue["number"]
        # Count the raw response: PRs filtered out would shrink a full page
        # and stop the lookup early.
        if len(raw) < 100:
            return None
        page += 1


def lock_issue(issue_url: str) -> bool:
    """Lock a GitHub Issue. Returns True on success."""
    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise RuntimeError("ACCESS_TOKEN environment variable is not set")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}",
    }
    payload = {"lock_reason": "too heated"}

    m = re.match(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)/?$", issue_url)
    if not m:
        return False
    api_url = f"https://api.github.com/repos/{m.group(1)}/issues/{m.group(2)}/lock"

    resp = requests.put(
        api_url, json=payload, headers=headers, verify=certifi.where(), timeout=30
    )
    return resp.status_code == 204