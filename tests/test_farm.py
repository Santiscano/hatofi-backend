from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models.batchModel import Batch, BatchStatusEnum
from app.models.userModel import Role, RoleEnum, User
from main import app


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine)


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
        farmer_role = Role(name=RoleEnum.FARMER, description="Farmer")
        investor_role = Role(name=RoleEnum.INVESTOR, description="Investor")
        db.add_all([farmer_role, investor_role])
        db.flush()
        db.add_all(
            [
                User(
                    full_name="Farmer",
                    email="farmer@example.com",
                    hashed_password="hash",
                    role=farmer_role,
                ),
                User(
                    full_name="Investor",
                    email="investor@example.com",
                    hashed_password="hash",
                    role=investor_role,
                ),
            ]
        )
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)


def auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user_id)})}"}


def test_farmer_can_create_and_update_owned_farm(client: TestClient) -> None:
    headers = auth_headers(1)
    response = client.post(
        "/farms",
        json={
            "name": "Hatofi",
            "description": "Primary farm",
            "location": "Antioquia",
            "capacity_head_count": 100,
            "capacity_current_head_count": 10,
        },
        headers=headers,
    )
    assert response.status_code == 201
    farm_id = response.json()["id"]

    assert client.patch(
        f"/farms/{farm_id}/capacity/max",
        json={"value": 120},
        headers=headers,
    ).status_code == 200
    assert client.patch(
        f"/farms/{farm_id}/capacity/current",
        json={"value": 20},
        headers=headers,
    ).status_code == 200
    details = client.patch(
        f"/farms/{farm_id}/details",
        json={"name": "Hatofi Updated", "location": "Caldas"},
        headers=headers,
    )
    assert details.status_code == 200
    assert details.json()["user_id"] == 1
    assert details.json()["name"] == "Hatofi Updated"
    assert details.json()["location"] == "Caldas"

    invalid_current = client.patch(
        f"/farms/{farm_id}/capacity/current",
        json={"value": 121},
        headers=headers,
    )
    assert invalid_current.status_code == 400


def test_user_can_list_only_owned_farms(client: TestClient) -> None:
    client.post(
        "/farms",
        json={"name": "B Finca", "location": "Caldas", "capacity_head_count": 20},
        headers=auth_headers(1),
    )
    client.post(
        "/farms",
        json={"name": "A Finca", "location": "Antioquia", "capacity_head_count": 10},
        headers=auth_headers(1),
    )
    client.post(
        "/farms",
        json={"name": "Otra Finca", "location": "Meta", "capacity_head_count": 5},
        headers=auth_headers(2),
    )

    response = client.get("/farms", headers=auth_headers(1))

    assert response.status_code == 200
    assert [farm["name"] for farm in response.json()] == ["A Finca", "B Finca"]


def test_only_farmer_owner_can_manage_farm(client: TestClient) -> None:
    create_response = client.post(
        "/farms",
        json={
            "name": "Owned farm",
            "location": "Antioquia",
            "capacity_head_count": 10,
        },
        headers=auth_headers(1),
    )
    farm_id = create_response.json()["id"]

    assert client.post(
        "/farms",
        json={"name": "Forbidden", "location": "Caldas", "capacity_head_count": 1},
        headers=auth_headers(2),
    ).status_code == 403
    assert client.patch(
        f"/farms/{farm_id}/details",
        json={"name": "Hijacked"},
        headers=auth_headers(2),
    ).status_code == 404


def test_farm_cannot_be_deleted_with_active_batches(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/farms",
        json={"name": "Farm", "location": "Antioquia", "capacity_head_count": 10},
        headers=auth_headers(1),
    )
    farm_id = create_response.json()["id"]

    with TestingSessionLocal() as db:
        db.add(
            Batch(
                title="Active batch",
                code="ACTIVE-001",
                target_amount=1000,
                price_per_share=100,
                estimated_roi_percentage=10,
                duration_months=18,
                funding_start_date=datetime(2026, 1, 1),
                funding_end_date=datetime(2026, 2, 1),
                farm_id=farm_id,
                status=BatchStatusEnum.FUNDING,
            )
        )
        db.commit()

    response = client.delete(f"/farms/{farm_id}", headers=auth_headers(1))
    assert response.status_code == 409


def test_farm_can_be_deleted_when_batches_are_closed_or_cancelled(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/farms",
        json={"name": "Farm", "location": "Antioquia", "capacity_head_count": 10},
        headers=auth_headers(1),
    )
    farm_id = create_response.json()["id"]

    with TestingSessionLocal() as db:
        for suffix, batch_status in (
            ("CLOSED", BatchStatusEnum.CLOSED),
            ("CANCELLED", BatchStatusEnum.CANCELLED),
        ):
            db.add(
                Batch(
                    title=f"{suffix} batch",
                    code=f"{suffix}-001",
                    target_amount=1000,
                    price_per_share=100,
                    estimated_roi_percentage=10,
                    duration_months=18,
                    funding_start_date=datetime(2026, 1, 1),
                    funding_end_date=datetime(2026, 2, 1),
                    farm_id=farm_id,
                    status=batch_status,
                )
            )
        db.commit()

    response = client.delete(f"/farms/{farm_id}", headers=auth_headers(1))
    assert response.status_code == 204
