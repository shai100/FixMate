from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://fixmate:fixmate@localhost:5432/fixmate"
    # Non-superuser role (no BYPASSRLS) the application connects as; RLS
    # policies only bite when not connected as the table owner/superuser.
    database_app_url: str = "postgresql+asyncpg://fixmate_app:fixmate_app@localhost:5432/fixmate"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "fixmate"
    s3_secret_key: str = "fixmate123"
    s3_bucket: str = "fixmate"
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = "qwen3:4b"
    ollama_embedding_model: str = "bge-m3"
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


settings = Settings()
