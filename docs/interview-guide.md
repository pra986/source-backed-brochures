# Interview walkthrough

## Two-minute demo

1. Explain that a scraped brochure can invent facts and lose provenance.
2. Generate the fictional demo and inspect the linked source excerpts.
3. Run it again and show cache hits; refresh and show a fresh snapshot.
4. Reopen the first saved run and download its JSON evidence.
5. Explain optional AI selection, and why invalid evidence IDs are rejected.
6. Show a test for an unknown ID and a private-address fetch.

## Questions to prepare

- Why does the model only select IDs? This makes output provenance verifiable, at the expense of free-form marketing prose. It does not prove source truth.
- Why separate source cache and saved runs? Refresh changes the cache, while an old run must retain its own inputs and output.
- How is SSRF reduced? Validate schemes, ports and all DNS results; pin a public TCP peer and verify TLS hostname; revalidate redirects. A production egress policy is still needed.
- Why SQLite? Local single-user persistence with no external service. Multi-user operation requires identity, access checks and appropriate concurrency design.
- What is actually tested? Deterministic behavior and API contracts. Hosted AI quality and broad website compatibility require separate live evaluation.
- What changes from the course? Independent application packaging, constrained selection, safe fetching, provenance, persistence, UI and verification.

## Honest resume description after personal review

Built an AI-assisted, course-inspired company brochure application using Python and FastAPI, with source-linked excerpts, cached website snapshots and automated verification. Do not claim production deployment or personal unaided authorship.
