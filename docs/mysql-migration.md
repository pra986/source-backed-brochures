# MySQL migration plan - not implemented

The release uses sqlite3 directly. Changing a connection string will not make it a MySQL application.

1. Add a maintained MySQL driver or a SQLAlchemy adapter and external configuration. Keep credentials out of source.
2. Convert DDL types and placeholders to the selected driver, choose InnoDB and preserve all primary/foreign/unique constraints. Store timestamps consistently and keep INR amounts integer.
3. Replace SQLite `BEGIN IMMEDIATE` with a transaction that locks the preview and target car row using the appropriate `SELECT ... FOR UPDATE` strategy. Handle deadlocks and duplicate-key races deterministically.
4. Keep the unique preview-to-booking relationship. On a duplicate confirmation race, retrieve the existing booking for the authenticated user; do not decrement stock twice.
5. Port cancellation with an owned booking row lock, a single state transition and one stock restoration.
6. Introduce versioned migrations and seed only missing synthetic inventory; never reset customer data on startup.
7. Run the full unit/API suite and concurrent last-unit, same-preview and cancellation tests against a disposable MySQL service. Add that service to CI before claiming compatibility.
8. Add connection pooling, backup/restore verification and deployment-level access controls appropriate to the hosting environment.
