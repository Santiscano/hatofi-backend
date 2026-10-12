from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from main import app
from app.models.userModel import Role, RoleEnum


TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        db.add(Role(name=RoleEnum.FARMER, description="Test role"))
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)


def registration_payload() -> dict:
    return {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "password": "correct-horse-battery",
        "confirm_password": "correct-horse-battery",
        "role_id": 1,
        "terms_accepted": True,
    }


def test_register_login_and_protected_endpoint(client: TestClient) -> None:
    register_response = client.post("/auth/register", json=registration_payload())
    assert register_response.status_code == 201
    assert register_response.json()["email"] == "ada@example.com"
    assert "hashed_password" not in register_response.json()

    login_response = client.post(
        "/auth/login",
        data={"username": "ada@example.com", "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["token_type"] == "bearer"
    token = login_data["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=headers).json()["email"] == "ada@example.com"


def test_registration_and_login_errors_are_reported(client: TestClient) -> None:
    assert client.post("/auth/register", json=registration_payload()).status_code == 201
    duplicate = client.post("/auth/register", json=registration_payload())
    assert duplicate.status_code == 400

    invalid_login = client.post(
        "/auth/login",
        data={"username": "ada@example.com", "password": "wrong-password"},
    )
    assert invalid_login.status_code == 401


def test_protected_endpoint_rejects_missing_or_invalid_token(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    ).status_code == 401
