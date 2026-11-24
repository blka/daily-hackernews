# Incremental Pages Site Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the daily deploy job from re-fetching the whole 520+ issue archive unauthenticated: fetch with `GITHUB_TOKEN` (retry on rate limit) and rebuild only what changed since the last deploy (manifest + `actions/cache`).

**Architecture:** `site.py` gains a manifest (`site/manifest.json`, written by the full build too) — `{page_path, number, title, date, body}` per built page. Each run: load manifest from the restored cache, fetch issues newest-first with early stop at the oldest manifest number, render only new pages or dates whose new issue number beats the manifest entry, rewrite the index from all manifest entries. Any missing/broken state falls back to today's full rebuild.

**Tech Stack:** Python 3.10 (workflow) / 3.14 (local venv), `requests`, pytest, `actions/cache@v4`.

**Spec:** `docs/superpowers/specs/2026-11-24-incremental-site-build-design.md`

**Branch:** `feat/incremental-site-build`, PR to `master`.

## Global Constraints

- Public site HTML, CSS and URL layout must stay identical to current `master` — existing `tests/test_site.py` must pass unmodified.
- `manifest.json` contains only public issue data — never secrets, never the token.
- Token comes from `GITHUB_TOKEN` env (read in `main()`); never printed or logged.
- Full-rebuild path must keep working unchanged — it is the fallback for every broken state (missing/corrupt manifest, missing page files, cache miss).
- Python 3.10 compatible (workflow runs 3.10; local venv is 3.14).
- Conventional commits (`feat:`, `refactor:`, `test:`), no scope needed.

## Review Focus

1. Corrupt/missing `manifest.json` (bad JSON, missing keys, duplicate dates) → site must still deploy via full rebuild, not crash. *Pinned: `test_load_manifest_returns_none_on_*` (Task 2), `test_main_falls_back_to_full_rebuild` (Task 6).*
2. Manifest entry whose page file is missing (partial cache) → full rebuild, no 404 pages on the live site. *Pinned: `test_main_falls_back_when_page_files_missing` (Task 6).*
3. Rate-limit 403/429 even with token → bounded retries (4 attempts, sleep capped at 120s), then loud failure for Actions to report. *Pinned: `test_retry_on_rate_limit_then_success`, `test_no_infinite_retry_on_permanent_403` (Task 3).*
4. New same-date issue on a date already in the manifest → newer number regenerates the page, one page per date still holds (case #571/#573). *Pinned: `test_same_date_newer_number_overrides_manifest` (Task 5).*
5. PR entries inside issues pages → stop condition must count raw page length; PRs must not truncate the fetch (regression of the past pagination bug). *Pinned: `test_early_stop_counts_raw_page_with_pr` (Task 4).*

---

### Task 1: Extract shared page/index rendering helpers

**Files:**
- Modify: `daily_hackernews/site.py` (`build_site`, new helpers)
- Test: `tests/test_site.py` (no new tests — existing suite proves the refactor; run it)

**Interfaces:**
- Consumes: existing `build_site` internals (`_page`, `_body_to_html`).
- Produces:
  - `_write_digest_page(title: str, body: str, date: tuple[str, str, str], out_dir: str) -> str` — writes `digests/YYYY-MM-DD.html`, returns `page_path`.
  - `_render_index(page_writes: list[tuple[str, str, str]], latest: dict | None, out_dir: str) -> None` — renders `index.html` with: h1, optional latest section (`latest["page_path"]`, `latest["title"]`, `latest["body"]`), collapsed archive grouped by year. `page_writes` items: `(page_path, year, title)`, newest first.

- [ ] **Step 1: Extract `digests/` page rendering and index rendering from `build_site` into `_write_digest_page` and `_render_index`; call them from `build_site`.**

`build_site` body becomes: digest dedup (unchanged) →
```python
page_writes = [(_write_digest_page(d["title"], d["body"], d["date"], out_dir), d["date"][0], d["title"]) for d in unique]
latest = {"page_path": page_writes[0][0], "title": page_writes[0][2], "body": unique[0]["body"]} if page_writes else None
_render_index(page_writes, latest, out_dir)
```

- [ ] **Step 2: Run the full site test suite**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: PASS (all existing tests unmodified, byte-identical output)

- [ ] **Step 3: Commit**

```bash
git add daily_hackernews/site.py
git commit -m "refactor: extract shared digest page and index rendering helpers"
```

---

### Task 2: Manifest write (full build) + load

**Files:**
- Modify: `daily_hackernews/site.py`
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: Task 1 `unique` digest list (dicts with `date` tuple, `title`, `body`, `number`).
- Produces:
  - `MANIFEST_PATH = "manifest.json"`
  - Entry shape (used everywhere downstream): `{"page_path": str, "number": int, "title": str, "date": str, "body": str}` where `date` is ISO `YYYY-MM-DD`.
  - `write_manifest(out_dir: str, entries: list[dict]) -> None` — writes `{"pages": entries}` as JSON to `out_dir/manifest.json`.
  - `load_manifest(out_dir: str) -> list[dict] | None` — returns entries newest-first, or `None` when file missing, invalid JSON, not a `{"pages": [...]}` dict, any entry missing/ill-typed (`number` not int, others not str), or duplicate `date` values.
- `build_site(issues, out_dir)` gains one behavior: after rendering pages it calls `write_manifest` with entries newest-first (same order as `page_writes`).

- [ ] **Step 1: Write failing tests in `tests/test_site.py` (new class `TestManifest`)**

```python
class TestManifest:
    def _manifest(self, tmp_path):
        import json
        return json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    def test_full_build_writes_manifest(self, tmp_path):
        issues = [_issue("05/10/2026", "# a", number=2), _issue("04/10/2026", "# b", number=1)]
        build_site(issues, str(tmp_path))
        data = self._manifest(tmp_path)
        assert [e["date"] for e in data["pages"]] == ["2026-10-05", "2026-10-04"]
        entry = data["pages"][0]
        assert entry == {
            "page_path": "digests/2026-10-05.html",
            "number": 2,
            "title": "Daily Hacker News 05/10/2026",
            "date": "2026-10-05",
            "body": "# a",
        }

    def test_full_build_dedup_kept_in_manifest(self, tmp_path):
        issues = [_issue("04/10/2026", "# OLD", number=100), _issue("04/10/2026", "# NEW", number=200)]
        build_site(issues, str(tmp_path))
        assert len(self._manifest(tmp_path)["pages"]) == 1
        assert self._manifest(tmp_path)["pages"][0]["number"] == 200

    def test_load_manifest_roundtrip(self, tmp_path):
        issues = [_issue("04/10/2026", "# b", number=1)]
        build_site(issues, str(tmp_path))
        assert load_manifest(str(tmp_path)) == self._manifest(tmp_path)["pages"]

    def test_load_manifest_returns_none_on_missing(self, tmp_path):
        assert load_manifest(str(tmp_path)) is None

    def test_load_manifest_returns_none_on_corrupt(self, tmp_path):
        (tmp_path / "manifest.json").write_text("not json{", encoding="utf-8")
        assert load_manifest(str(tmp_path)) is None

    def test_load_manifest_returns_none_on_bad_entries(self, tmp_path):
        (tmp_path / "manifest.json").write_text('{"pages": [{"page_path": "x"}]}', encoding="utf-8")
        assert load_manifest(str(tmp_path)) is None
        (tmp_path / "manifest.json").write_text(
            '{"pages": [{"page_path": "a", "number": 1, "title": "t", "date": "2026-10-04", "body": "b"},'
            '{"page_path": "c", "number": 1, "title": "t", "date": "2026-10-04", "body": "b"}]}',
            encoding="utf-8")
        assert load_manifest(str(tmp_path)) is None  # duplicate dates
```

Add `load_manifest` to the imports from `daily_hackernews.site`.

- [ ] **Step 2: Run tests, expect FAIL**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: FAIL — nothing writes/reads `manifest.json` yet

- [ ] **Step 3: Implement `write_manifest`, `load_manifest`, and the `write_manifest` call at the end of `build_site`**

Entries inside `build_site`, in the `page_writes` order:
```python
entries = [{"page_path": p, "number": d["number"], "title": d["title"],
            "date": "-".join(d["date"]), "body": d["body"]} for (p, _, _), d in zip(page_writes, unique)]
write_manifest(out_dir, entries)
```

- [ ] **Step 4: Run full site suite, expect PASS**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: PASS (all classes)

- [ ] **Step 5: Commit**

```bash
git add tests/test_site.py daily_hackernews/site.py
git commit -m "feat: write site manifest during build and read it back"
```

---

### Task 3: Authenticated API fetch with bounded retries

**Files:**
- Modify: `daily_hackernews/site.py` (`fetch_issues`, new `_api_get`)
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: `requests`, module-level `time` (add `import time`).
- Produces:
  - `_api_get(url: str, params: dict, token: str | None) -> requests.Response` — sends `Accept: application/vnd.github+json`, plus `Authorization: Bearer <token>` when token is not None. On HTTPError with status 403/429 retries up to 3 times (4 requests total), sleeping `min(max(int(reset) - now, 1), 120)` when `X-RateLimit-Reset` present, else `5 * 2**attempt`; re-raises on other statuses or after the last attempt.
  - `fetch_issues(token: str | None = None) -> list[dict]` — same pagination as today, calls `_api_get`, returns `resp.json()` page contents extended as today.

- [ ] **Step 1: Write failing tests (new class `TestFetchAuth`) in `tests/test_site.py`**

```python
class TestFetchAuth:
    def _resp(self, data, status=200, headers=None):
        import requests
        class R:
            def __init__(self):
                self.status_code = status
                self.headers = headers or {}
            def json(self): return data
            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.exceptions.HTTPError(f"{self.status_code}", response=type("X", (), {"status_code": self.status_code})())
        return R()

    def test_token_sends_authorization_header(self, monkeypatch):
        import daily_hackernews.site as site
        seen = {}
        def fake_get(url, **kwargs):
            seen.update(kwargs)
            return self._resp([])
        monkeypatch.setattr(site.requests, "get", fake_get)
        site.fetch_issues(token="T0K3N")
        assert seen["headers"]["Authorization"] == "Bearer T0K3N"

    def test_no_token_omits_authorization(self, monkeypatch):
        import daily_hackernews.site as site
        seen = {}
        def fake_get(url, **kwargs):
            seen.update(kwargs)
            return self._resp([])
        monkeypatch.setattr(site.requests, "get", fake_get)
        site.fetch_issues()
        assert "Authorization" not in seen["headers"]

    def test_retry_on_rate_limit_then_success(self, monkeypatch):
        import daily_hackernews.site as site
        issues = [_issue("01/10/2026", "# x", number=n) for n in range(50)]
        calls, sleeps = [], []
        def fake_get(url, **kwargs):
            calls.append(1)
            return self._resp([], status=403) if len(calls) == 1 else self._resp(issues)
        monkeypatch.setattr(site.requests, "get", fake_get)
        monkeypatch.setattr(site.time, "sleep", sleeps.append)
        result = site.fetch_issues(token="T")
        assert len(calls) == 2 and len(sleeps) == 1 and len(result) == 50

    def test_limited_retry_then_loud_failure(self, monkeypatch):
        import daily_hackernews.site as site
        import pytest
        calls, sleeps = [], []
        def fake_get(url, **kwargs):
            calls.append(1)
            return self._resp([], status=403)
        monkeypatch.setattr(site.requests, "get", fake_get)
        monkeypatch.setattr(site.time, "sleep", sleeps.append)
        with pytest.raises(Exception):
            site.fetch_issues(token="T")
        assert len(calls) == 4 and len(sleeps) == 3
```

- [ ] **Step 2: Run tests, expect FAIL**

Run: `venv/bin/pytest tests/test_site.py::TestFetchAuth -v`
Expected: FAIL — token not sent / no retry logic

- [ ] **Step 3: Implement `_api_get` and switch `fetch_issues` to it (token param, same pagination)**

- [ ] **Step 4: Run tests, expect PASS**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: PASS (all classes — `TestFetchIssues` still green)

- [ ] **Step 5: Commit**

```bash
git add tests/test_site.py daily_hackernews/site.py
git commit -m "feat: authenticated GitHub API fetch with bounded rate-limit retries"
```

---

### Task 4: Early stop on fetch

**Files:**
- Modify: `daily_hackernews/site.py` (`fetch_issues`)
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: Task 3 `fetch_issues(token)`.
- Produces: `fetch_issues(token: str | None = None, stop_below: int | None = None) -> list[dict]` — after each page: break when `len(raw) < 100` **or** any raw issue number `<= stop_below`. Issues already on the threshold page are returned; the build layer filters them. Relies on GitHub's newest-first issue ordering.

- [ ] **Step 1: Write failing tests (extend `TestFetchIssues`)**

```python
    def test_early_stop_reduces_pages(self, monkeypatch):
        import daily_hackernews.site as site
        page1 = [_issue("05/10/2026", "# x", number=n) for n in range(300, 200, -1)]
        page2 = [_issue("04/10/2026", "# y", number=n) for n in range(200, 100, -1)]
        calls = []
        def fake_get(url, **kwargs):
            calls.append(kwargs["params"]["page"])
            import daily_hackernews.site as s
            class FakeResp:
                def json(self): return page1 if kwargs["params"]["page"] == 1 else page2
                def raise_for_status(self): pass
            return FakeResp()
        monkeypatch.setattr(site.requests, "get", fake_get)
        result = site.fetch_issues(stop_below=150)
        assert calls == [1, 2]
        assert {i["number"] for i in result} == set(range(100, 301))

    def test_no_early_stop_when_none(self, monkeypatch):
        # existing behavior: without stop_below both pages are fetched (regression guard)
        ...  # reuse fake from test_pagination_continues_past_pr_page; assert stop_below=None fetches all pages
```

`test_no_early_stop_when_none` may duplicate the existing pagination test's fake — fine, keep it small and self-contained.

- [ ] **Step 2: Run tests, expect FAIL**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: FAIL — `stop_below` not accepted yet

- [ ] **Step 3: Implement the stop check in `fetch_issues` (raw `len(raw)` semantics — PRs count, they don't shrink the page)**

```python
        if len(raw) < 100:
            break
        if stop_below is not None and any(i.get("number", 0) or 0 <= stop_below for i in raw):
            break
```

- [ ] **Step 4: Also pin the raw-page-counting guard under stop_below (Review Focus #5)**

Add to `TestFetchIssues`:
```python
    def test_early_stop_counts_raw_page_with_pr(self, monkeypatch):
        # page 1: only a PR (number 50-99 range) — raw length < 100 stops pagination
        import daily_hackernews.site as site
        calls = []
        pr_page = [{"number": 99, "title": "PR", "pull_request": {"url": "x"}}]
        def fake_get(url, **kwargs):
            calls.append(1)
            class FakeResp:
                def json(self): return pr_page
                def raise_for_status(self): pass
            return FakeResp()
        monkeypatch.setattr(site.requests, "get", fake_get)
        result = site.fetch_issues(stop_below=150)
        assert len(calls) == 1  # raw page shorter than 100 → stop, no page 2
        assert result == []
```

- [ ] **Step 5: Run tests, expect PASS, commit**

Run: `venv/bin/pytest tests/test_site.py -v`

```bash
git add tests/test_site.py daily_hackernews/site.py
git commit -m "feat: early-stop issue fetch at last manifest number"
```

---

### Task 5: Incremental build

**Files:**
- Modify: `daily_hackernews/site.py`
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: Task 1 `_write_digest_page`, `_render_index`; Task 2 `write_manifest`, entry shape.
- Produces: `build_incremental(issues: list[dict], entries: list[dict], out_dir: str) -> None` — renders only new/overriding pages, writes updated manifest, rewrites `index.html` from the merged entries.

- [ ] **Step 1: Write failing tests (new class `TestIncremental`). Common pattern: full build via `build_site` first, then call `build_incremental` with a new issue batch.**

```python
class TestIncremental:
    def _entries(self, tmp_path):
        import json
        return json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["pages"]

    def test_new_date_adds_page_and_manifest_entry(self, tmp_path):
        build_site([_issue("04/10/2026", "# old", number=100)], str(tmp_path))
        build_incremental([_issue("05/10/2026", "# new", number=200)], self._entries(tmp_path), str(tmp_path))
        assert "# new" in (tmp_path / "digests" / "2026-10-05.html").read_text(encoding="utf-8")
        entries = self._entries(tmp_path)
        assert len(entries) == 2
        assert entries[0]["date"] == "2026-10-05"  # newest first

    def test_same_date_newer_number_overrides_manifest(self, tmp_path):
        build_site([_issue("04/10/2026", "# old", number=100)], str(tmp_path))
        build_incremental([_issue("04/10/2026", "# new", number=200)], self._entries(tmp_path), str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        assert "# new" in page and "# old" not in page
        assert self._entries(tmp_path)[0]["number"] == 200

    def test_below_manifest_number_issue_is_skipped(self, tmp_path):
        build_site([_issue("05/10/2026", "# a", number=10), _issue("04/10/2026", "# b", number=100)], str(tmp_path))
        build_incremental([_issue("04/10/2026", "# dup", number=50)], self._entries(tmp_path), str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        assert "# b" in page and "# dup" not in page
        assert len(self._entries(tmp_path)) == 2

    def test_index_rebuilt_from_manifest_plus_new(self, tmp_path):
        build_site([_issue("04/10/2026", "# old", number=100)], str(tmp_path))
        build_incremental([_issue("05/10/2026", "# new", number=200)], self._entries(tmp_path), str(tmp_path))
        index = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "05/10/2026" in index and "04/10/2026" in index
        assert index.index("2026-10-05.html") < index.index("2026-10-04.html")
        assert "# new" in index  # latest digest body on index
        assert index.count("<details") == 1
```

- [ ] **Step 2: Run tests, expect FAIL**

Run: `venv/bin/pytest tests/test_site.py::TestIncremental -v`
Expected: FAIL — `build_incremental` not defined

- [ ] **Step 3: Implement `build_incremental` — this algorithm is the core of the feature**

```python
def build_incremental(issues: list[dict], entries: list[dict], out_dir: str) -> None:
    """Render only issues not covered by the manifest; update manifest + index.

    Semantics: within the new batch the highest issue number wins a date;
    a new issue beats the manifest only when its number is higher than the
    manifest entry's number; anything at or below the oldest manifest number
    is historical and skipped.
    """
    digests = [
        {"date": parse_issue_date(i["title"]), "title": i["title"],
         "body": i["body"] or "", "number": i.get("number", 0) or 0}
        for i in issues if parse_issue_date(i["title"]) is not None
    ]
    digests.sort(key=lambda d: (d["date"], d["number"]), reverse=True)
    winners: dict = {}
    for d in digests:
        winners.setdefault(d["date"], d)

    min_number = min(e["number"] for e in entries)
    by_date = {e["date"]: e for e in entries}
    for d in winners.values():
        date_iso = "-".join(d["date"])
        if d["number"] <= min_number:
            continue
        man = by_date.get(date_iso)
        if man is not None and d["number"] <= man["number"]:
            continue
        page_path = _write_digest_page(d["title"], d["body"], d["date"], out_dir)
        by_date[date_iso] = {"page_path": page_path, "number": d["number"],
                             "title": d["title"], "date": date_iso, "body": d["body"]}

    merged = sorted(by_date.values(), key=lambda e: e["date"], reverse=True)
    write_manifest(out_dir, merged)
    page_writes = [(e["page_path"], e["date"][:4], e["title"]) for e in merged]
    latest = {"page_path": page_writes[0][0], "title": page_writes[0][2],
              "body": merged[0]["body"]} if merged else None
    _render_index(page_writes, latest, out_dir)
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: PASS (all classes)

- [ ] **Step 5: Commit**

```bash
git add tests/test_site.py daily_hackernews/site.py
git commit -m "feat: incremental site build driven by manifest"
```

---

### Task 6: Orchestration with fallback in `main()`

**Files:**
- Modify: `daily_hackernews/site.py` (`main`, new `_manifest_pages_exist`)
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: Task 2 `load_manifest`; Task 4 `fetch_issues(token, stop_below)`; Task 5 `build_incremental`; existing `build_site`.
- Produces: `main(out_dir: str = "site") -> None` — reads `GITHUB_TOKEN` from env (never logged). Flow:
  1. `entries = load_manifest(out_dir)`; `None` → full path.
  2. `_manifest_pages_exist(entries, out_dir) -> bool` (every `page_path` exists on disk) → false → full path.
  3. Incremental: `fetch_issues(token=token, stop_below=min(e["number"] for e in entries))`, `build_incremental(issues, entries, out_dir)`.
  4. Full: `fetch_issues(token=token)`, `build_site(issues, out_dir)`.

- [ ] **Step 1: Write failing tests (new class `TestMainFlow`) — monkeypatch only `fetch_issues`, everything else runs real**

```python
class TestMainFlow:
    def test_full_rebuild_when_no_manifest(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site
        seen = {}
        def fake_fetch(token=None, stop_below=None):
            seen["stop_below"] = stop_below
            return [_issue("04/10/2026", "# x", number=1)]
        monkeypatch.setattr(site, "fetch_issues", fake_fetch)
        site.main(str(tmp_path))
        assert seen["stop_below"] is None           # full path: no early stop
        assert (tmp_path / "manifest.json").exists()

    def test_incremental_run_uses_manifest(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site
        monkeypatch.setattr(site, "fetch_issues", lambda token=None, stop_below=None: [_issue("04/10/2026", "# x", number=1)])
        site.main(str(tmp_path))                    # full build seeds manifest + pages
        before = (tmp_path / "digests" / "2026-10-04.html").read_bytes()
        captured = {}
        def fake_fetch2(token=None, stop_below=None):
            captured["stop_below"] = stop_below
            return [_issue("05/10/2026", "# y", number=2)]
        monkeypatch.setattr(site, "fetch_issues", fake_fetch2)
        site.main(str(tmp_path))
        assert captured["stop_below"] == 1          # oldest manifest number
        assert (tmp_path / "digests" / "2026-10-05.html").exists()
        assert (tmp_path / "digests" / "2026-10-04.html").read_bytes() == before  # old page untouched
        assert (tmp_path / "index.html").read_text(encoding="utf-8").count("2026-10-04.html") >= 1

    def test_main_falls_back_to_full_rebuild(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site
        (tmp_path / "manifest.json").write_text("garbage", encoding="utf-8")
        seen = {}
        def fake_fetch(token=None, stop_below=None):
            seen["stop_below"] = stop_below
            return [_issue("04/10/2026", "# x", number=1)]
        monkeypatch.setattr(site, "fetch_issues", fake_fetch)
        site.main(str(tmp_path))
        assert seen["stop_below"] is None

    def test_main_falls_back_when_page_files_missing(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site
        monkeypatch.setattr(site, "fetch_issues", lambda token=None, stop_below=None: [_issue("04/10/2026", "# x", number=1)])
        site.main(str(tmp_path))
        (tmp_path / "digests" / "2026-10-04.html").unlink()
        seen = {}
        def fake_fetch2(token=None, stop_below=None):
            seen["stop_below"] = stop_below
            return []
        monkeypatch.setattr(site, "fetch_issues", fake_fetch2)
        site.main(str(tmp_path))
        assert seen["stop_below"] is None
```

Note: `test_incremental_run_uses_manifest` seeds via a first `main()` call with `fetch_issues` monkeypatched — no real API traffic in tests.

- [ ] **Step 2: Run tests, expect FAIL**

Run: `venv/bin/pytest tests/test_site.py::TestMainFlow -v`
Expected: FAIL — `main()` has no manifest/incremental logic yet

- [ ] **Step 3: Implement `main` + `_manifest_pages_exist` (token from `os.environ.get("GITHUB_TOKEN")`; keep the two existing print lines)**

- [ ] **Step 4: Run whole suite, expect PASS**

Run: `venv/bin/pytest tests/ -v`
Expected: PASS (all files — this is the final python change)

- [ ] **Step 5: Commit**

```bash
git add tests/test_site.py daily_hackernews/site.py
git commit -m "feat: orchestrator with manifest-driven incremental build and full-rebuild fallback"
```

---

### Task 7: Workflow changes — token + site cache

**Files:**
- Modify: `.github/workflows/daily.yml:38-41` (deploy job)

**Interfaces:**
- Consumes: Task 6 `main()` reading `GITHUB_TOKEN` env; `site/` dir as cache and artifact source.
- Produces: deploy job steps: restore cache → build with token → the existing configure/upload/deploy steps.

- [ ] **Step 1: Update the deploy job steps**

Replace the build step (line 40-41) with:

```yaml
      - name: Restore site cache
        uses: actions/cache@v4
        with:
          path: site
          key: site-${{ github.run_id }}
          restore-keys: site-
      - name: Build site from issues
        run: python -m daily_hackernews.site site
        env:
          GITHUB_TOKEN: ${{ github.token }}
```

Everything else (configure-pages, upload-pages-artifact with `path: site`, deploy-pages) stays exactly as is.

- [ ] **Step 2: Verify YAML parses**

Run: `venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml')); print('yaml ok')"`
Expected: `yaml ok` (if PyYAML missing in venv: `venv/bin/pip install pyyaml` first — dev-only, do NOT add to requirements.txt)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "feat: site cache and authenticated build token in deploy job"
```

---

### Task 8: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `venv/bin/pytest tests/ -v`
Expected: PASS, all files

- [ ] **Step 2: Live smoke (READ-ONLY GitHub API calls — needs explicit user confirmation in-session before running)**

```bash
GITHUB_TOKEN=$(gh auth token) venv/bin/python -m daily_hackernews.site /tmp/dhn-smoke     # full build (real API)
GITHUB_TOKEN=$(gh auth token) venv/bin/python -m daily_hackernews.site /tmp/dhn-smoke     # second run: incremental
```

Expected: first run fetches all pages and writes `/tmp/dhn-smoke/manifest.json`; second run prints a small fetch count (only pages until the oldest manifest number) and leaves `digests/*.html` byte-identical except none missing. `manifest.json` contains no secrets (`grep -v` token check).

- [ ] **Step 3: Commit check + push branch is a separate, user-confirmed step (pushing = external action; ask first)**

---

## Self-review notes

- Spec coverage: token+retry (T3), early stop (T4), manifest write/load/validation (T2), incremental semantics (T5), fallbacks (T6), workflow cache+token (T7), live verification (T8) — all spec requirements have a task.
- `build_site` signature unchanged → all existing 70 tests stay authoritative for byte-compatible output.
- Known accepted simplification: `_api_get` retries on every 403/429 (not only rate-limit ones) — rare non-rate-limit 403s just waste up to 3 retries; acceptable at 6 requests/day.
- Manifest ordering contract: entries newest-first everywhere (write and load); `build_incremental` re-sorts defensively.
