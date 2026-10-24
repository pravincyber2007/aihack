import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    valid_csrf_token,
    verify_password,
)


def test_password_hash_and_verification() -> None:
    hashed = hash_password("a long test password")
    assert hashed != "a long test password"
    assert verify_password("a long test password", hashed)
    assert not verify_password("the wrong password", hashed)


def test_tokens_are_random_and_csrf_requires_a_match() -> None:
    first = new_token()
    second = new_token()
    assert first != second
    assert hash_token(first) != first
    assert valid_csrf_token("same", "same")
    assert not valid_csrf_token("cookie", "header")
    assert not valid_csrf_token(None, "header")


def test_settings_parse_origins_and_require_secure_production_cookies() -> None:
    settings = Settings(cors_origins="http://localhost:5173,https://portal.example.com")
    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://portal.example.com",
    ]
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        Settings(app_env="production", session_cookie_secure=False)
