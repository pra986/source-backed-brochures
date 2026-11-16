# Verification record

- Tested application commit: `522a72585a34ae8bf5aedede9ea109ff420d42e1`.
- [GitHub Actions run 43838539179](https://github.com/pra986/source-backed-brochures/actions/runs/43838539179): **all four jobs passed** — 42 tests on each of Python 3.11, 3.12 and 3.13, plus real Chromium browser smoke.
- Browser checked draft approval gate, source links, task editing, saved approval, Markdown/CSV/JSON downloads, persistence after reload, manual additions clearing approval, revision history, 390px responsive layout and confirmed deletion. No page JavaScript errors were observed.
- Desktop and mobile screenshots were visually reviewed. Screenshots and fictional example downloads are retained in the workflow artifact subject to GitHub retention, not as committed meeting data.
- Local Python 3.12: **42 tests passed**, including a built-package install checked outside the source directory. The local environment inherited runtime dependencies; clean dependency installation was verified separately by CI.
- JavaScript syntax: `node --check` passed.
- Demo fixture: 9 source segments → 4 discussion excerpts, 2 decisions, 3 actions. The suggestion in S006 is not extracted as an action. This fixture is not a representative accuracy benchmark.
- No paid/live AI or audio provider calls were made. Contract mocks do not measure transcription or meeting-summary quality.

This results update changes documentation only; the linked run records the exact tested application commit.
