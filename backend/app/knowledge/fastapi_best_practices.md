# FastAPI Best Practices

## Request/Response Validation
Always define Pydantic models for request bodies and response
schemas instead of accepting raw dicts. This gives automatic
validation, documentation, and clear error messages.

## Error Handling
Raise `HTTPException` with an appropriate status code and a safe,
user-facing `detail` message. Never include stack traces, internal
exception messages, or secrets in the response sent to clients — log
those details server-side instead.

## Dependency Injection
Use FastAPI's `Depends()` for shared logic like authentication,
database sessions, or configuration, rather than duplicating setup
code in every route.

## CORS
Configure `CORSMiddleware` with an explicit list of allowed origins
in production. Avoid `allow_origins=["*"]` combined with
`allow_credentials=True`, as this is a security risk.

## Environment & Secrets
Load configuration (API keys, database URLs) from environment
variables via a dedicated config/settings module, not hardcoded in
route files. Never commit `.env` files to version control.

## Performance
Avoid blocking, synchronous calls (e.g. long CPU-bound work or
blocking I/O) inside `async def` route handlers, as this blocks the
event loop. Use `def` (FastAPI runs it in a thread pool) for
synchronous blocking work, or use async-compatible libraries.

## Project Structure
Separate concerns into routers, services, and models rather than
putting all logic directly in route handler functions. This keeps
routes thin and business logic testable.