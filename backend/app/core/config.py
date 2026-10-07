from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_AUTH_BRANCH_SCOPES: dict[str, list[str]] = {
    "PHX": ["Phoenix", "PHX"],
    "DBN": ["Durban", "Umgeni"],
    "JHB": ["Johannesburg", "JHB", "RTCJHB"],
    "CPT": ["Cape Town", "CPT"],
}


class Settings(BaseSettings):
    app_name: str = "Tyre Technical Reporting Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./tyre_reports.db"
    jwt_secret: str = "development-secret-change-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    auth_enabled: bool = False
    auth_issuer_url: str = "https://192.168.1.236:8010"
    auth_client_id: str = "RT-TechnicalClaim"
    auth_client_secret: str = ""
    auth_redirect_uri: str = "https://192.168.1.236:8020/api/auth/callback"
    auth_ca_file: str = ""
    auth_timeout_seconds: float = 10
    auth_user_links: dict[str, str] = {}
    auth_branch_scopes: dict[str, list[str]] = Field(
        default_factory=lambda: {
            code: aliases.copy() for code, aliases in DEFAULT_AUTH_BRANCH_SCOPES.items()
        }
    )
    allowed_origins: str = "http://localhost:4200"
    seed_admin_email: str = "admin@royaltyres.co.za"
    seed_admin_password: str = "ChangeMe123!"
    seed_claims_admin_email: str = "claims@royaltyres.co.za"
    seed_claims_admin_password: str = ""
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_username: str = "royaladmin@royaltyres.co.za"
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "royaladmin@royaltyres.co.za"
    email_from_name: str = "Royal Tyres Technical Reports"
    public_app_url: str = "http://localhost:4200"
    royal_tyres_logo_path: str = ""
    royal_tyres_report_header_path: str = ""
    royal_tyres_report_footer_path: str = ""
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
    bounce_monitor_enabled: bool = False
    bounce_monitor_mailbox: str = ""
    bounce_monitor_poll_seconds: int = 60
    bounce_monitor_lookback_hours: int = 72
    bounce_monitor_batch_size: int = 25
    bounce_monitor_timeout_seconds: float = 15.0
    jwt_secret_file: str = ""
    smtp_password_file: str = ""
    microsoft_client_secret_file: str = ""
    gemini_api_key_file: str = ""
    customer_json_path: str = "backend/data/customers.json"
    claims_auto_handover_enabled: bool = True
    supplier_json_path: str = "backend/data/suppliers.json"
    sap_customer_endpoint: str = ""
    sap_customer_company_db: str = ""
    sap_customer_search_param: str = ""
    sap_customer_timeout_seconds: float = 8.0
    sap_api_key_header: str = "X-API-Key"
    sap_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    gemini_timeout_seconds: float = 30.0

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
            ("gemini_api_key_file", "gemini_api_key"),
        ):
            path = getattr(self, file_field)
            if path:
                setattr(
                    self, value_field, Path(path).read_text(encoding="utf-8").strip()
                )

    def validate_for_startup(self) -> None:
        if self.auth_enabled:
            if not self.auth_client_secret or not self.auth_ca_file:
                raise RuntimeError(
                    "RT-Auth requires AUTH_CLIENT_SECRET and AUTH_CA_FILE"
                )
            if not all(
                url.startswith("https://")
                for url in (
                    self.auth_issuer_url,
                    self.auth_redirect_uri,
                    self.public_app_url,
                )
            ):
                raise RuntimeError("RT-Auth and app URLs must use HTTPS")
            if (
                len(self.jwt_secret) < 32
                or self.jwt_secret == "development-secret-change-before-deployment"
            ):
                raise RuntimeError(
                    "RT-Auth session encryption requires a strong JWT_SECRET"
                )
            if not Path(self.auth_ca_file).is_file():
                raise RuntimeError("AUTH_CA_FILE must point to the trusted root CA")
        if self.environment != "production":
            return
        errors: list[str] = []
        if self.jwt_secret == "development-secret-change-before-deployment":
            errors.append("JWT_SECRET must be replaced")
        if self.seed_admin_password == "ChangeMe123!":
            errors.append("SEED_ADMIN_PASSWORD must be replaced")
        if self.seed_claims_admin_password == "ChangeMe123!":
            errors.append("SEED_CLAIMS_ADMIN_PASSWORD must be replaced")
        if len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must contain at least 32 characters")
        if self.database_url.startswith("sqlite"):
            errors.append("Production must use PostgreSQL, not SQLite")
        if any("localhost" in origin for origin in self.cors_origins):
            errors.append("ALLOWED_ORIGINS must not contain localhost")
        if self.public_app_url.startswith("http://"):
            errors.append("PUBLIC_APP_URL must use HTTPS")
        if "*" in self.cors_origins:
            errors.append("ALLOWED_ORIGINS must not use a wildcard in production")
        if self.smtp_username and not self.smtp_password:
            errors.append("SMTP_PASSWORD must be configured when SMTP_USERNAME is set")
        if not self.gemini_api_key:
            errors.append("GEMINI_API_KEY must be configured for AI image analysis")
        if errors:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
