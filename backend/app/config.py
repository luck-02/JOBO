from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Offres : "demo" ou "france_travail"
    offers_provider: str = "demo"
    france_travail_client_id: str = ""
    france_travail_client_secret: str = ""

    # Rédaction : "demo" ou "anthropic"
    writer_provider: str = "demo"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"

    # Fiche entreprise : "demo" ou "annuaire"
    company_provider: str = "annuaire"

    database_url: str = "sqlite:///./data/app.db"
    storage_dir: str = "./data/files"

    daily_generation_limit: int = 5
    max_cv_iterations: int = 3
    cors_origins: str = "http://localhost:3000"
    cv_accent_color: str = "#1d4ed8"
