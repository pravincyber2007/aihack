from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env", extra="ignore", enable_decoding=False
    )

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]
    session_cookie_secure: bool = False
    session_cookie_name: str = "staff_session"
    session_lifetime_hours: int = 24
    csrf_cookie_name: str = "staff_csrf"
    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    smtp_from_email: str = "no-reply@example.test"
    # Background loop that expires unanswered offers and retries unassigned tasks.
    assignment_worker_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def require_secure_production_cookies(self) -> "Settings":
        if self.app_env == "production" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS cannot include a wildcard")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
