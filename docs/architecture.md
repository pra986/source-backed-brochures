# Architecture and invariants

## Read path

The browser sends a filter request or a chat message. Offline regex routing or the optional model produces a typed `Plan`. Its allowed actions are only search, compare, details and help. Pydantic rejects extra fields and unknown action names. Query values go into parameterized SQL. The server constructs all inventory responses from database records; the model cannot write SQL or return a displayed price. The UI exposes tool name and arguments for inspection.

Chat is intentionally stateless: pronouns such as "compare those" have no hidden context. Explicit IDs and filters are required. A model can still choose the wrong filters; validation limits tool authority, not semantic error. No free-form generated answer is displayed.

## Write path

1. Registration salts/hashes a password with scrypt; sign-in produces a random session token. Only its SHA-256 hash is stored.
2. An authenticated customer asks for a preview of one catalog ID. Price and inventory version are snapshotted with an expiry. Stock is unchanged.
3. Confirmation requires a true confirmation field, a session and an owned preview.
4. Inside `BEGIN IMMEDIATE`, an existing booking for that preview is returned first. This provides retry safety even after expiry or cancellation.
5. For a new booking, current stock, price, version and expiry are checked. One demo unit is decremented and a version incremented, then the booking snapshot is inserted in the same transaction.
6. Owner-only cancellation increments stock once and marks the booking cancelled atomically. Later cancellations return that state without another increment.

Any price/version change invalidates other old previews even when several units remain. This is a deliberately conservative conflict rule: ask the user to review new information rather than silently confirming against stale state. There are no real holds, sales or payments.

## State and security

Inventory and booking records are authoritative; text is not. Sessions are opaque, HttpOnly and SameSite=Strict. Secure cookies are optional for localhost but required with HTTPS in a shared deployment. Authenticated IDs come from the server session, never request body user IDs. Lists and mutations filter by the current user. Same-origin writes and JSON content types are required. TrustedHostMiddleware limits host headers. API validation errors omit input values so passwords are not echoed.

SQLite transactions serialize writes. A future MySQL adapter must use an equivalent row-lock/uniqueness strategy. The only unique booking operation key is the preview ID, scoped by owned-preview lookup. Creating a new preview is a genuinely new operation, not a replay of an old one.
