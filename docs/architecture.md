# Architecture and request flow

1. A browser submits a bounded JSON request to FastAPI. It defaults to synthetic demo data and extractive selection.
2. The engine loads a one-hour page cache or fetches a public homepage. TCP connects to an already validated IP; TLS still verifies the requested hostname. Proxies are not used by the website fetcher.
3. HTMLParser removes scripts, styles, navigation and footers. The crawler heuristically prioritizes About, Products, Services, Careers and Team paths. It fetches at most three child pages, with same-origin links/redirects. Homepage redirects may establish a new public origin.
4. Sentence-like excerpts receive stable per-run IDs. Extraction is limited to 60 evidence entries; the selected output is limited to eight.
5. Extractive mode takes the first passages. Optional AI mode returns existing IDs only. The engine rejects unknown or malformed selections and builds the final prose from verbatim excerpts. It never uses unrestricted generated claims.
6. A transaction saves a complete run, including extracted page text, timestamps, hash, evidence, selection, warnings and Markdown. Cache updates do not alter old runs. Demo and live caches are namespaced separately.
7. The UI uses textContent for all source text. It offers history, Markdown/JSON exports and browser printing. Each run can be reopened without re-fetching a site or calling a model.

## Boundaries

SQLite is the source of truth for saved runs. The source cache is only a speed aid. API keys remain server environment variables. Website content is untrusted. A source hash covers the decoded HTML representation, not a certified original binary file. The snapshot contains extracted text, not raw HTML; it can replay the saved output but cannot rerun a future parser on the original bytes.

Timeouts are per socket operation, not an overall crawl deadline. Downloads are size-limited. No background queue, persistent multi-user authorization or distributed limits are implemented. A public deployment requires additional operational controls.
