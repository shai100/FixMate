"""FastAPI application entry point — wires the whole HTTP surface together.

This module builds the single ``app`` object that the web server runs. Its job
is small and declarative: refuse to boot in an unsafe auth configuration, then
mount every feature's router so its endpoints become reachable. The actual
request handling lives in the ``routers/`` package; this file just assembles it.

Run locally with: ``uvicorn fixmate.api.main:app --reload``.
"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fixmate.api.routers import (
    admin,
    ask,
    conversations,
    curation,
    dev,
    documents,
    equipment,
    feedback,
)
from fixmate.core.settings import settings

logger = logging.getLogger("fixmate.api")


def _guard_auth_config() -> None:
    """Fail fast at import time if dev auth is enabled outside ``local``.

    Dev auth trusts plain ``X-Org-Id``/``X-Role`` headers, which anyone could
    forge. Crashing on boot is far safer than silently accepting spoofable
    identities in staging/production.
    """
    # Header-based dev auth must never run in a real deployment (Phase 6.1):
    # refuse to boot rather than silently accept spoofable X-Org-Id headers.
    if settings.dev_auth and settings.env != "local":
        raise RuntimeError(
            f"DEV_AUTH=true is forbidden when ENV={settings.env!r}; set DEV_AUTH=false "
            "and configure OIDC (Phase 9)."
        )


_guard_auth_config()

app = FastAPI(title="FixMate API", version="0.1.0")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn any uncaught error into a logged, informative JSON response.

    FastAPI's default for an unhandled exception is a bare ``500 Internal Server
    Error`` with no body — which hides *why* a request failed (e.g. the Ollama
    model isn't pulled, a retrieval query blew up, the DB rejected a value). That
    forced engineers to dig through server logs to debug a failed answer.

    How it works: every unhandled exception is logged in full (with traceback)
    under the ``fixmate.api`` logger, then converted to a structured 500 body
    carrying the exception ``type`` and ``message``. On the local/dev profile we
    also include the traceback so the cause is visible right in the API response;
    in staging/production we omit it (it can leak internals) but still log it.
    The structured body shape is ``{"error": {"type", "message", "path"}}``.

    Note: ``HTTPException`` (404/422/etc.) is handled by FastAPI's own handler and
    never reaches here, so deliberate 4xx responses keep their original detail.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    detail = {
        "type": type(exc).__name__,
        "message": str(exc) or repr(exc),
        "path": request.url.path,
    }
    # Tracebacks can expose internal structure; only return them on the local
    # dev profile, where seeing the cause inline is the whole point. They are
    # always written to the server log regardless of environment.
    if settings.env == "local":
        detail["traceback"] = traceback.format_exc().splitlines()
    return JSONResponse(status_code=500, content={"error": detail})


app.include_router(conversations.router)
app.include_router(ask.router)
app.include_router(equipment.router)
app.include_router(documents.router)
app.include_router(feedback.router)
app.include_router(curation.queue_router)
app.include_router(curation.fixes_router)
app.include_router(admin.router)
app.include_router(dev.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness probe for load balancers / ``scripts/healthcheck.py``."""
    return {"status": "ok", "env": settings.env}
