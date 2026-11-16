# Observed verification - 16 November 2026

## Executed

- Python 3.12, supplied workspace runtime dependencies.
- `python3 -m unittest discover -s tests -v`: **30 tests passed**, 0 failures.
- Parser and same-origin link extraction; unsupported input, credential/port and private/mixed DNS rejection.
- Mock transport verifies pinned TCP destination, preserved TLS hostname, redirect revalidation, redirect cap, HTML type and body-byte limits.
- Offline demo, partial-page failure, no-evidence failure, cache refresh and isolation of synthetic/live cache namespaces.
- SQLite persistence across Store instances and immutability of saved snapshots.
- Known/unknown/malformed AI evidence selection; mocked provider response and provider failure handling.
- FastAPI in-process request, history, replay, Markdown and JSON export, missing run, invalid export format, missing AI configuration, UI document and health routes.
- JavaScript syntax: `node --check` passed.
- Python wheel built and installed in a separate virtual environment using the supplied system dependencies (no independent network dependency resolution). Installed package was exercised from outside the source directory.

## Not established

The browser automation package could not launch a usable Chromium process in this execution environment: the system binary failed at its process-singleton socket initialization. Therefore browser interactions, responsive layout, screenshot QA and visual output are **not verified**. The attempted browser flow is not counted among passing checks.

No paid key was supplied, so live hosted AI inference is not tested. Public-site compatibility has not been benchmarked. Docker image, GitHub Actions matrix and cloud deployment have not been run. There are no quality, latency, cost or real-user metrics to claim.

The current runtime emits a Starlette/httpx integration deprecation warning during TestClient setup; tests still pass. A clean dependency-resolution run on a normal machine and the CI matrix should be completed before a public release.
