from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, hash_token
from app.models import AuthSession, User, UserRole, UserStatus


def test_registration_verification_admin_approval_and_sign_in(
    client: TestClient,
    db_session: Session,
    csrf_headers: dict[str, str],
    monkeypatch,
) -> None:
    email_messages: list[dict[str, str]] = []

    def capture_email(*, recipient: str, subject: str, action_url: str) -> None:
        email_messages.append(
            {"recipient": recipient, "subject": subject, "action_url": action_url}
        )

    monkeypatch.setattr("app.api.v1.auth.send_action_email", capture_email)

    registration = client.post(
        "/api/v1/auth/register",
        headers=csrf_headers,
        json={"email": "staff@example.com", "password": "correct horse battery"},
    )
    assert registration.status_code == 202
    assert email_messages[0]["recipient"] == "staff@example.com"
    verification_token = parse_qs(urlparse(email_messages[0]["action_url"]).query)["token"][0]

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("administrator password"),
        role=UserRole.ADMINISTRATOR,
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    session_token = "seeded-admin-session"
    db_session.add(
        AuthSession(
            token_hash=hash_token(session_token),
            user_id=admin.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db_session.commit()

    verified = client.post(
        "/api/v1/auth/verify-email",
        headers=csrf_headers,
        json={"token": verification_token},
    )
    assert verified.status_code == 200

    unapproved_login = client.post(
        "/api/v1/auth/login",
        headers=csrf_headers,
        json={"email": "staff@example.com", "password": "correct horse battery"},
    )
    assert unapproved_login.status_code == 403

    client.cookies.set(settings.session_cookie_name, session_token)
    pending = client.get("/api/v1/admin/users/pending")
    assert pending.status_code == 200
    assert [user["email"] for user in pending.json()] == ["staff@example.com"]

    approval = client.patch(
        f"/api/v1/admin/users/{pending.json()[0]['id']}/role",
        headers=csrf_headers,
        json={"role": "receptionist"},
    )
    assert approval.status_code == 200
    assert approval.json()["role"] == "receptionist"
    assert approval.json()["status"] == "active"

    client.cookies.delete(settings.session_cookie_name)
    wrong_role_login = client.post(
        "/api/v1/auth/login",
        headers=csrf_headers,
        json={
            "email": "staff@example.com",
            "password": "correct horse battery",
            "selected_role": "housekeeping_staff",
        },
    )
    assert wrong_role_login.status_code == 403
    assert settings.session_cookie_name not in client.cookies

    login = client.post(
        "/api/v1/auth/login",
        headers=csrf_headers,
        json={
            "email": "staff@example.com",
            "password": "correct horse battery",
            "selected_role": "receptionist",
        },
    )
    assert login.status_code == 200
    assert login.json()["role"] == "receptionist"
    assert settings.session_cookie_name in client.cookies

    user = db_session.scalar(select(User).where(User.email == "staff@example.com"))
    assert user is not None
    assert db_session.scalar(
        select(AuthSession.id).where(AuthSession.user_id == user.id)
    ) is not None
    assert client.get("/api/v1/admin/users/pending").status_code == 403

    original_session = client.cookies.get(settings.session_cookie_name)
    refreshed = client.post("/api/v1/auth/refresh", headers=csrf_headers)
    assert refreshed.status_code == 200
    assert client.cookies.get(settings.session_cookie_name) != original_session
    assert client.get("/api/v1/auth/me").status_code == 200

    logout = client.post("/api/v1/auth/logout", headers=csrf_headers)
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_database_readiness_check(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


def test_password_reset_is_single_use_and_revokes_sessions(
    client: TestClient,
    db_session: Session,
    csrf_headers: dict[str, str],
    monkeypatch,
) -> None:
    email_messages: list[dict[str, str]] = []

    def capture_email(*, recipient: str, subject: str, action_url: str) -> None:
        email_messages.append(
            {"recipient": recipient, "subject": subject, "action_url": action_url}
        )

    monkeypatch.setattr("app.api.v1.auth.send_action_email", capture_email)
    user = User(
        email="staff@example.com",
        password_hash=hash_password("original password"),
        role=UserRole.HOUSEKEEPING_STAFF,
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(
        AuthSession(
            token_hash=hash_token("old-session"),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db_session.commit()

    requested = client.post(
        "/api/v1/auth/forgot-password",
        headers=csrf_headers,
        json={"email": "staff@example.com"},
    )
    assert requested.status_code == 202
    assert requested.json()["message"] == (
        "If an account matches that email, instructions will be sent shortly."
    )
    reset_token = parse_qs(urlparse(email_messages[0]["action_url"]).query)["token"][0]

    reset = client.post(
        "/api/v1/auth/reset-password",
        headers=csrf_headers,
        json={"token": reset_token, "password": "updated password 123"},
    )
    assert reset.status_code == 200
    assert db_session.scalar(
        select(AuthSession.id).where(AuthSession.user_id == user.id)
    ) is None

    replay = client.post(
        "/api/v1/auth/reset-password",
        headers=csrf_headers,
        json={"token": reset_token, "password": "another password 123"},
    )
    assert replay.status_code == 400

    login = client.post(
        "/api/v1/auth/login",
        headers=csrf_headers,
        json={"email": "staff@example.com", "password": "updated password 123"},
    )
    assert login.status_code == 200
