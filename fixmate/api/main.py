"""FastAPI application entry point — wires the whole HTTP surface together.

This module builds the single ``app`` object that the web server runs. Its job
is small and declarative: refuse to boot in an unsafe auth configuration, then
mount every feature's router so its endpoints become reachable. The actual
request handling lives in the ``routers/`` package; this file just assembles it.

Run locally with: ``uvicorn fixmate.api.main:app --reload``.
"""

from fastapi import FastAPI

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
