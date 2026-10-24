import hashlib
import hmac
import secrets

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def valid_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    return bool(
        cookie_token
        and header_token
        and hmac.compare_digest(cookie_token, header_token)
    )
