# Interview demo and questions

## Three-minute demonstration

1. Explain the business problem: showroom questions must use current records; a chat message must not silently create an order.
2. Ask `Show automatic cars under 12 lakh` and inspect the tool arguments and exact catalog prices.
3. Compare CAR-001 and CAR-002. Explain which facts are unavailable rather than inventing mileage or ratings.
4. Sign in with a test identity, preview a request, acknowledge the demo notice and explicitly confirm.
5. Open My requests and cancel. Show the automated replay, stale-price and last-unit tests.
6. Explain the local-demo scope, synthetic data and AI assistance. Live paid AI quality, real customer use and production deployment are separate claims.

## Questions

- Why typed tool routing? The model can choose a read operation but cannot invent a displayed price, run SQL or create a booking. A wrong filter remains possible and is visible in the trace.
- Why preview and confirm? The user must review the exact car/price; a preview is not a stock hold. Confirmation validates current state.
- What happens when two customers request the last unit? SQLite serializes the write transaction. One confirms; the other receives an availability/conflict result.
- What makes a retry safe? The owned preview is the operation key and bookings.preview_id is unique. A repeated confirm returns the existing row.
- Can cancellation replay inflate stock? The state change and restoration are atomic; cancelled state is returned on a repeat.
- Where is identity enforced? The backend resolves an opaque cookie session and scopes all booking access to that user ID.
- Why not MySQL yet? SQLite provides a runnable demo. MySQL needs a real adapter and row-lock semantics, not just a renamed URL.
- What did AI help with? Explain that this implementation and its documentation were produced with AI assistance; demonstrate your own understanding and later modifications.
