# Contribution and provenance record

This was implemented with AI assistance for Pranil Deshmukh. It is course-inspired and adapted to a showroom domain; it should not be described as unaided authorship.

Implemented: independent FastAPI/Python package, fictional catalog, typed read-only tool routing, database-backed comparisons, local registration/sessions, explicit booking previews, transactional stock and stale-price checks, replay-safe confirmation/cancellation, browser UI and speech-synthesis button, automated verification and documentation.

The design changes the course's airline fare lookup into an inventory-backed request workflow. It does not copy course source or include paid videos/slides. Unlike the course's multimodal airline demo, this release does not generate destination images or call a hosted speech API. SQLite works locally; MySQL migration remains planned.

Before interviews, run the app, inspect the tool plan, read db.py's confirmation/cancellation transactions and implement a small change you understand. Point to actual test results rather than claiming unmeasured production reliability.
