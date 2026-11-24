# Digest Duplicate Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, chosen) or superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `python main.py` becomes idempotent per day — a duplicate run finds the existing digest issue and publishes nothing.

**Architecture:** Query helper `find_issue_by_title` in `publisher.py` (same pagination contract as `site.fetch_issues`), guard at the top of `main()` before `fetch_stories`.

**Tech Stack:** Python, requests, pytest.

**Spec:** `docs/superpowers/specs/2026-11-24-digest-dedup-guard-design.md`

## Global Constraints

- Auth unchanged: `ACCESS_TOKEN` env, `Authorization: token` header, `verify=certifi.where()`.
- Exact title match: `Daily Hacker News DD/MM/YYYY` (output of `get_date()`).
- Guard error = `RuntimeError` (loud), never a silent pass-through to `create_issue`.

## Review Focus

1. PR entries inside issue pages must not truncate the lookup — raw page length stops pagination (regression of the known bug class). *Pinned in Task 1.*
2. Guard runs before `fetch_stories` — no HN fetch when skipping. *Pinned in Task 2.*
3. Non-200 from the lookup raises; it must not fall through to `create_issue`. *Pinned in Task 1.*

---

### Task 1: `find_issue_by_title`

**Files:**
- Modify: `daily_hackernews/publisher.py`
- Test: `tests/test_publisher.py`

**Interfaces:**
- Produces: `find_issue_by_title(title: str) -> int | None` — exact-match lookup over `daily-digest` issues, `Authorization: token` header, paginates while `len(raw) == 100`, counts raw pages (PRs included), filters `pull_request` keys, returns issue `number` or `None`. Raises `RuntimeError` on non-200 status.

Steps:
- [ ] Write failing tests: found→number via page 1 with PRs interleaved; not found → None; multi-page lookup; non-200 → RuntimeError.
- [ ] Run `venv/bin/pytest tests/test_publisher.py -q` — expect FAIL.
- [ ] Implement.
- [ ] Run full `venv/bin/pytest tests/ -q` — expect PASS.
- [ ] Commit `feat: find existing digest issue by exact title`.

### Task 2: Guard in `main()`

**Files:**
- Modify: `daily_hackernews/main.py`
- Test: new `tests/test_dedup_guard.py`

**Interfaces:**
- Consumes: Task 1 `find_issue_by_title`; existing `get_date`, `fetch_stories`, `render_digest`, `create_issue`, `lock_issue`.
- Produces: idempotent `main()` — when the lookup hits, logs and returns **before** `fetch_stories`.

Steps:
- [ ] Write failing tests: existing digest (#639) → `fetch_stories` and `create_issue` are never called, `lock_issue` never called; missing digest → normal pipeline calls all four.
- [ ] Run `venv/bin/pytest tests/test_dedup_guard.py -q` — expect FAIL.
- [ ] Implement (guard line + early return; move `date = get_date()` before the lookup).
- [ ] Run `venv/bin/pytest tests/ -q` — expect PASS.
- [ ] Commit `feat: skip digest creation when today's issue exists`.
