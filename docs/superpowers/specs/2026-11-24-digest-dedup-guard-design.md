# Digest duplicate guard — short design

Date: 2026-11-24

## Intent

A duplicate run of the Daily workflow on the same day (schedule + manual
dispatch — as on 24/11 with #638/#639) creates duplicate digest issues. Add a
fuse: the run skips digest creation when an issue with today's title already
exists.

## Goals / non-goals

- Goal: idempotent `python main.py` — second run same day publishes nothing.
- Non-goal: dedup of *historical* duplicates (#571/#573-style cleanup stays manual).
- Non-goal: `concurrency:` group (simultaneous-run race) — TOCTOU window of
  seconds accepted as negligible.
- Non-goal: locking an existing but unlocked issue during the guard — YAGNI.

## Approach (picked)

Guard in code, in `daily_hackernews/main.py`, backed by a query helper in
`daily_hackernews/publisher.py`:

- `publisher.find_issue_by_title(title: str) -> int | None` — lists
  `daily-digest`-labeled issues via `GITHUB_API_URL` (same pagination as
  `site.fetch_issues`: raw page length stops the loop, PRs filtered), exact
  title match, returns the issue number. Raises `RuntimeError` on non-200
  (consistent with `create_issue`'s "raises on failure" contract — a guard
  error must not silently recreate a duplicate).
- `main.py`: right after computing `date`, before `fetch_stories`:
  `find_issue_by_title(f"Daily Hacker News {date}")` → hit → log
  `Digest for {date} already exists (#N). Skipping.` → return. The site build
  (deploy job) is unaffected: it is already idempotent via the manifest.

## Alternatives rejected

- YAML guard step with `gh` CLI — logic in workflow YAML, untestable, same cost.
- `concurrency` group alone — only shields simultaneously-started runs; a
  schedule-vs-manual dispatch hours apart still duplicates.

## Constraints

- Token and auth unchanged (`ACCESS_TOKEN`).
- Title format `Daily Hacker News DD/MM/YYYY` is the identity anchor (matches
  the site page parser's expectations).
