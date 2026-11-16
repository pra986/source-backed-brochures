# Implementation record

This is an AI-assisted independent implementation for Pranil Deshmukh's portfolio. It is inspired by a course exercise, not presented as an unaided original invention. No copied course source is included.

Implemented in this collaboration:

- A Python package and FastAPI application with an accessible, responsive local web interface.
- Deterministic link prioritization instead of relying on model-selected fetch destinations.
- Validated public addresses, pinned peers, redirect checks, bounded download size and page counts.
- Source-linked extractive output, optional model evidence selection and rejection of unknown IDs.
- Immutable SQLite run snapshots, TTL cache, explicit refresh and demo/live cache isolation.
- Saved history, Markdown/JSON downloads, print support and a fictional offline fixture.
- Automated parser, URL, storage, engine, API and provider-contract checks.
- CI configuration, Docker recipe, interview notes and reproducible local setup.

Not yet established: paid-provider quality, real-site compatibility across a benchmark, browser visual verification, Docker build, hosted deployment, GitHub Actions run or the user's independent comprehension of this code. See evaluation/results.md for updated observed checks.

Before an interview, run the app yourself, study each function, explain a failed case and implement a change you understand. Describe this as an AI-assisted course-inspired portfolio build and point to the exact features and test evidence.
