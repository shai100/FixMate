from fastapi import FastAPI

from fixmate.api.routers import ask, conversations, documents, equipment
from fixmate.core.settings import settings


def _guard_auth_config() -> None:
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


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "env": settings.env}
