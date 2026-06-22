"""Central application configuration.

This module defines every tunable knob FixMate reads at startup — database
URLs, the LLM backend to use, object-storage credentials, and auth settings.
Values come from (in order of precedence) real environment variables, then a
local ``.env`` file, then the hard-coded defaults below. Those defaults are
deliberately wired for the local Docker Compose stack (see
``docker-compose.yml`` / ``setup-instructions.md``) so a fresh clone runs
without any configuration.

Everything else in the codebase imports the single shared ``settings`` instance
created at the bottom of this file rather than reading ``os.environ`` directly,
so there is exactly one place that defines what is configurable.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated configuration loaded once at import time.

    Subclassing pydantic's ``BaseSettings`` means each attribute below is read
    from the matching environment variable (case-insensitive, e.g.
    ``DATABASE_URL`` -> ``database_url``) and coerced to the annotated type, so a
    misconfigured value fails loudly at boot instead of deep inside a request.

    Attribute groups:
      - ``database_*``: Postgres connection strings. ``database_url`` is the
        owner/superuser used for migrations; ``database_app_url`` is the limited
        role the app runs queries as so Row-Level Security actually applies.
      - ``redis_url``: Celery broker / result backend for async workers.
      - ``s3_*``: MinIO (local) or S3 (cloud) object storage for PDFs/figures.
      - ``llm_provider`` + ``ollama_*`` / ``anthropic_*``: which LLM backend to
        use and how to reach it (see ``fixmate/llm/factory.py``).
      - ``dev_auth`` / ``dev_auto_login`` / ``env``: local-only auth shortcuts,
        guarded so they can never be enabled in a real deployment.
      - ``keycloak_*`` / ``oidc_*``: production OIDC token validation (Phase 9).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://fixmate:fixmate@localhost:5432/fixmate"
    # Non-superuser role (no BYPASSRLS) the application connects as; RLS
    # policies only bite when not connected as the table owner/superuser.
    database_app_url: str = "postgresql+asyncpg://fixmate_app:fixmate_app@localhost:5432/fixmate"
    redis_url: str = "redis://localhost:6379/0"
    # Staging directory for uploaded PDFs awaiting ingestion. The API writes the
    # bytes here and hands the Celery worker only the *filename*; the worker
    # resolves it back to a full path under this same directory. Keeping it a
    # plain (repo-relative) path means the host API and a containerized worker can
    # share it via one bind mount without passing host-absolute paths across the
    # OS boundary (the worker sets UPLOAD_DIR=/uploads in docker-compose).
    upload_dir: str = ".fixmate-uploads"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "fixmate"
    s3_secret_key: str = "fixmate123"
    s3_bucket: str = "fixmate"
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = "qwen3:4b"
    ollama_embedding_model: str = "bge-m3"
    # How long Ollama keeps a model resident after a request. "-1" = never unload,
    # so the embedding and generation models stay loaded and no query pays a cold
    # model load (the dominant retrieval latency on the 4 GB profile — see the
    # OLLAMA_KEEP_ALIVE note in docker-compose.yml). Sent on every Ollama request
    # so it also applies to an Ollama running outside Compose (native Windows).
    # A duration string ("5m") or a number of seconds; "-1" means keep forever.
    ollama_keep_alive: str = "-1"

    @property
    def ollama_keep_alive_param(self) -> str | int:
        """The ``keep_alive`` value coerced to the type Ollama's JSON API expects.

        Ollama's ``/api/embed`` rejects a *string* integer ("-1") with HTTP 400 —
        the sentinel must be sent as a JSON number — while duration strings like
        "5m" must stay strings. This returns an ``int`` for whole-number values
        (including the "-1" = never-unload sentinel) and the raw string otherwise.
        """
        raw = self.ollama_keep_alive.strip()
        if raw.lstrip("-").isdigit():
            return int(raw)
        return raw
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    dev_auth: bool = True
    # Dev convenience (local only): when true alongside dev_auth, the web client
    # auto-signs-in as an admin of the demo tenant via /dev/auto-login, skipping
    # the manual org/user UUID entry. Never honoured unless dev_auth is also true.
    dev_auto_login: bool = False
    # Org name the dev auto-login resolves to (matches scripts/seed_demo.py).
    dev_demo_org: str = "FixMate Demo"
    # Deployment environment. The API refuses to boot when dev_auth is true here
    # outside "local" (header auth must never reach a real deployment — Phase 6.1).
    env: str = "local"
    # Keycloak OIDC (Phase 9). Used only when dev_auth is false: Bearer tokens are
    # validated against the realm's JWKS. issuer/jwks_uri are derived from these.
    keycloak_base_url: str = "http://localhost:8080"
    keycloak_realm: str = "fixmate"
    oidc_client_id: str = "fixmate-api"
    # Keycloak access tokens carry aud=account by default, not the client id, so
    # audience verification is off unless an explicit aud mapper is configured.
    oidc_verify_audience: bool = False


# The one shared, process-wide configuration object. Import this, not the class.
settings = Settings()
