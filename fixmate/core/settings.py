from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://fixmate:fixmate@localhost:5432/fixmate"
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


settings = Settings()
