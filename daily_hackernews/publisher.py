"""Publish digest as a GitHub Issue."""

from __future__ import annotations

import json
import os

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

    resp = requests.put(
        f"{issue_url}/lock", json=payload, headers=headers, verify=certifi.where(), timeout=30
    )
    return resp.status_code == 204