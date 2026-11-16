# Verification record - 16 November 2026

## Observed locally

- Python 3.12: 60 unittest checks passed, 0 failures.
- Inventory filters, exact comparisons, missing/unsupported facts and parameterized query behavior.
- Account/password/session handling, logout/expiry, cookie flags, login throttling, owner isolation and origin/host/content-type checks.
- Booking preview without stock reservation; explicit confirmation; stale price/version and expiry rejection.
- Duplicate confirmation/cancellation; persistence across store reopen; simultaneous confirmations of one preview and a race for the final unit.
- Full in-process HTTP registration, preview, confirmation, history and cancellation.
- Offline lakh/crore/range queries; typed mocked AI routing and rejection of write plans.
- Browser JavaScript syntax checked with Node.

## Verified GitHub Actions

- Unit/API/concurrency suite: 60 tests passed on Python 3.11, 3.12 and 3.13.
- Real Chromium browser smoke: passed search, tool trace inspection, filter reset, comparisons, signup, consent enforcement, booking confirmation, cancellation, logout, narrow-screen overflow and no browser JavaScript errors.
- Verified application commit: `c03476c4afc037b4c29f50fc19c1fadc199d9e8d`.
- Successful run: https://github.com/pra986/source-backed-brochures/actions/runs/43835351181
- CI screenshots are attached to that run as showroom-browser-screenshots.
- Browser verification caught and fixed a Reset button/form-method naming conflict before completion.

## CI and live checks

The workflow includes a Python 3.11/3.12/3.13 matrix and a real Chromium smoke job. Their actual outcome is recorded after execution, not assumed from configuration. The browser smoke uses a disposable database and synthetic identity, tests desktop and narrow-screen behavior, and retains screenshots as CI artifacts.

No paid provider key was used. Hosted AI routing quality, browser speech-synthesis behavior, Docker image, MySQL compatibility and production deployment have not been established. A local runtime emits a Starlette/httpx deprecation warning during TestClient setup; deterministic tests still pass. No real user, real price accuracy, latency or cost metrics are claimed.
