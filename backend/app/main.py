import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routers import accounts, auth, dashboard, imports, transactions

settings = get_settings()
if settings.environment == "production" and len(settings.jwt_secret) < 32:
    raise RuntimeError("JWT_SECRET must be set to a random string of at least 32 characters.")
if not settings.jwt_secret:
    settings.jwt_secret = "dev-only-insecure-secret-change-me-0000000000"

log = logging.getLogger("koshio")

app = FastAPI(
    title="Koshio API",
    # Hide the interactive API docs in production.
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None, openapi_url=None if settings.environment == "production" else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"  # financial data should not be cached
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Log the error type and path only, never request bodies (they hold financial data).
    log.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server."})


@app.get("/health")
def health():
    return {"status": "ok"}


for r in (auth.router, accounts.router, transactions.router, dashboard.router, imports.router):
    app.include_router(r)
