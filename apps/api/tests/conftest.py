from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    settings.assignment_worker_enabled = False
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(client: TestClient) -> Generator[Session, None, None]:
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        yield db
    finally:
        db.close()
        db_generator.close()


@pytest.fixture
def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


PASSWORD = "correct horse battery"


@pytest.fixture
def make_user(db_session: Session):
    from app.core.security import hash_password
    from app.models import User, UserRole, UserStatus

    def factory(
        email: str,
        role: UserRole | None,
        *,
        status: UserStatus = UserStatus.ACTIVE,
        floor: int | None = None,
        available: bool = False,
    ) -> User:
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            role=role,
            status=status,
            email_verified=True,
            floor=floor,
            is_available=available,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return factory


@pytest.fixture
def login_as(client: TestClient, csrf_headers: dict[str, str]):
    def sign_in(email: str) -> None:
        client.cookies.delete(settings.session_cookie_name)
        response = client.post(
            "/api/v1/auth/login",
            headers=csrf_headers,
            json={"email": email, "password": PASSWORD},
        )
        assert response.status_code == 200, response.text

    return sign_in
