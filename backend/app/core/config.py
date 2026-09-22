from functools import lru_cache
from pathlib import Path

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
    media_root: str = "./data/report-images"
    public_app_url: str = "http://localhost:4200"
    royal_tyres_logo_path: str = ""
    royal_tyres_company_details: str = "Royal Tyres · Technical Services"
    royal_tyres_pdf_disclaimer: str = (
        "This report records inspection findings at the time of assessment."
    )
    request_rate_limit_per_minute: int = 120
    report_retention_days: int = 2555
    password_reset_minutes: int = 30
    max_delivery_attempts: int = 3
    delivery_retry_minutes: int = 5
    microsoft_tenant_id: str = "common"
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:8000/api/v1/auth/microsoft/callback"
    jwt_secret_file: str = ""
    smtp_password_file: str = ""
    microsoft_client_secret_file: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]

    def model_post_init(self, __context) -> None:
        for file_field, value_field in (
            ("jwt_secret_file", "jwt_secret"),
            ("smtp_password_file", "smtp_password"),
            ("microsoft_client_secret_file", "microsoft_client_secret"),
        ):
            path = getattr(self, file_field)
            if path:
                setattr(
                    self, value_field, Path(path).read_text(encoding="utf-8").strip()
                )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
