from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tyre Technical Reporting Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./tyre_reports.db"
    jwt_secret: str = "development-secret-change-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    allowed_origins: str = "http://localhost:4200"
    seed_admin_email: str = "admin@royaltyres.co.za"
    seed_admin_password: str = "ChangeMe123!"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    email_from: str = "technical-reports@royaltyres.co.za"
    email_from_name: str = "Royal Tyres Technical Reports"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
