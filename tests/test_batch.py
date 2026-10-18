from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models.farmModel import Farm
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
        roles = {
            role: Role(name=role, description=role.value)
            for role in (RoleEnum.ADMIN, RoleEnum.FARMER, RoleEnum.INVESTOR)
        }
        db.add_all(roles.values())
        db.flush()
        db.add_all(
            [
                User(
                    full_name="Admin",
                    email="admin@example.com",
                    hashed_password="hash",
                    role=roles[RoleEnum.ADMIN],
                ),
                User(
                    full_name="Farmer",
                    email="farmer@example.com",
                    hashed_password="hash",
                    role=roles[RoleEnum.FARMER],
                ),
                User(
                    full_name="Investor",
                    email="investor@example.com",
                    hashed_password="hash",
                    role=roles[RoleEnum.INVESTOR],
                ),
            ]
        )
        db.flush()
        db.add(
            Farm(
                name="Farm",
                location="Antioquia",
                capacity_head_count=100,
                capacity_current_head_count=0,
                user_id=2,
            )
        )
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)


def auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user_id)})}"}


def batch_payload() -> dict:
    return {
        "title": "Lote inicial",
        "description": "Lote de prueba",
        "category": "CEBA_INTENSIVA",
        "target_amount": 10000,
        "duration_months": 18,
        "funding_start_date": "2026-11-01T00:00:00",
        "farm_id": 1,
    }


def test_owner_can_create_edit_and_change_batch_status(
    client: TestClient,
) -> None:
    response = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "DRAFT"
    assert data["category"] == "CEBA_INTENSIVA"
    assert data["code"].startswith("BATCH-")
    batch_id = data["id"]

    update = client.patch(
        f"/batches/{batch_id}",
        json={"description": "Descripción actualizada"},
        headers=auth_headers(2),
    )
    assert update.status_code == 200
    assert update.json()["description"] == "Descripción actualizada"

    for next_status in (
        "FUNDING",
        "FUNDED",
        "BUYING_PROCESS",
        "IN_PROGRESS",
        "READY_FOR_SALE",
        "CLOSED",
    ):
        status_response = client.patch(
            f"/batches/{batch_id}/status",
            json={"status": next_status},
            headers=auth_headers(2),
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == next_status

    locked_update = client.patch(
        f"/batches/{batch_id}",
        json={"title": "No debe cambiar"},
        headers=auth_headers(2),
    )
    assert locked_update.status_code == 409


def test_admin_can_edit_and_owner_rules_are_enforced(client: TestClient) -> None:
    created = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    batch_id = created.json()["id"]

    admin_update = client.patch(
        f"/batches/{batch_id}",
        json={"title": "Editado por admin"},
        headers=auth_headers(1),
    )
    assert admin_update.status_code == 200

    investor_create = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(3)
    )
    assert investor_create.status_code == 403


def test_batch_category_can_be_cria_levante(client: TestClient) -> None:
    payload = batch_payload()
    payload["category"] = "CRIA_LEVANTE"

    response = client.post(
        "/batches", json=payload, headers=auth_headers(2)
    )

    assert response.status_code == 201
    assert response.json()["category"] == "CRIA_LEVANTE"


def test_status_transitions_reject_invalid_jumps_and_allow_cancel(
    client: TestClient,
) -> None:
    created = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    batch_id = created.json()["id"]

    invalid = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "FUNDED"},
        headers=auth_headers(2),
    )
    assert invalid.status_code == 409

    cancelled = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "CANCELLED"},
        headers=auth_headers(2),
    )
    assert cancelled.status_code == 200

    terminal_jump = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "FUNDING"},
        headers=auth_headers(2),
    )
    assert terminal_jump.status_code == 409


def test_owner_can_list_batches_for_farm_and_filter_by_status(
    client: TestClient,
) -> None:
    first = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    second_payload = batch_payload()
    second_payload["title"] = "Lote financiado"
    second = client.post(
        "/batches", json=second_payload, headers=auth_headers(2)
    )
    assert first.status_code == 201
    assert second.status_code == 201

    first_id = first.json()["id"]
    updated = client.patch(
        f"/batches/{first_id}/status",
        json={"status": "FUNDING"},
        headers=auth_headers(2),
    )
    assert updated.status_code == 200

    response = client.get("/batches/farm/1", headers=auth_headers(2))
    assert response.status_code == 200
    assert [batch["id"] for batch in response.json()] == [
        second.json()["id"],
        first_id,
    ]

    filtered = client.get(
        "/batches/farm/1?status=FUNDING",
        headers=auth_headers(2),
    )
    assert filtered.status_code == 200
    assert [batch["id"] for batch in filtered.json()] == [first_id]


def test_farmer_cannot_list_another_farms_batches(client: TestClient) -> None:
    with TestingSessionLocal() as db:
        db.add(
            Farm(
                name="Otra finca",
                location="Córdoba",
                capacity_head_count=80,
                capacity_current_head_count=0,
                user_id=1,
            )
        )
        db.commit()

    response = client.get("/batches/farm/2", headers=auth_headers(2))
    assert response.status_code == 403

def test_investor_can_invest_increase_and_query_summary(
    client: TestClient,
) -> None:
    created = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    batch_id = created.json()["id"]
    with TestingSessionLocal() as db:
        batch = db.query(Batch).filter(Batch.id == batch_id).one()
        batch.status = BatchStatusEnum.FUNDING
        db.commit()

    investment = client.post(
        "/investments",
        json={"batch_id": batch_id, "amount": "6000.00"},
        headers=auth_headers(3),
    )
    assert investment.status_code == 201
    assert investment.json()["amount"] == "6000.00"
    assert investment.json()["batch_status"] == "FUNDING"

    increased = client.patch(
        f"/investments/{batch_id}/amount",
        json={"amount": "2000.00"},
        headers=auth_headers(3),
    )
    assert increased.status_code == 200
    assert increased.json()["amount"] == "8000.00"

    listed = client.get("/investments/me", headers=auth_headers(3))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    summary = client.get("/investments/me/summary", headers=auth_headers(3))
    assert summary.status_code == 200
    assert summary.json()["open_investments"] == 1
    assert summary.json()["open_amount"] == "8000.00"


def test_investor_can_invest_ten_usdc(
    client: TestClient,
) -> None:
    created = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    batch_id = created.json()["id"]
    with TestingSessionLocal() as db:
        batch = db.query(Batch).filter(Batch.id == batch_id).one()
        batch.status = BatchStatusEnum.FUNDING
        db.commit()

    investment = client.post(
        "/investments",
        json={"batch_id": batch_id, "amount": "10.00"},
        headers=auth_headers(3),
    )

    assert investment.status_code == 201
    assert investment.json()["amount"] == "10.00"


def test_investment_rejects_duplicate_and_amount_above_remaining(
    client: TestClient,
) -> None:
    created = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    batch_id = created.json()["id"]
    with TestingSessionLocal() as db:
        batch = db.query(Batch).filter(Batch.id == batch_id).one()
        batch.status = BatchStatusEnum.FUNDING
        db.commit()

    first = client.post(
        "/investments",
        json={"batch_id": batch_id, "amount": "10000.01"},
        headers=auth_headers(3),
    )
    assert first.status_code == 400

    valid = client.post(
        "/investments",
        json={"batch_id": batch_id, "amount": "10000.00"},
        headers=auth_headers(3),
    )
    assert valid.status_code == 201

    duplicate = client.post(
        "/investments",
        json={"batch_id": batch_id, "amount": "1.00"},
        headers=auth_headers(3),
    )
    assert duplicate.status_code == 409


def test_closed_batch_is_listed_and_investment_summary_is_closed(
    client: TestClient,
) -> None:
    created = client.post(
        "/batches", json=batch_payload(), headers=auth_headers(2)
    )
    batch_id = created.json()["id"]
    with TestingSessionLocal() as db:
        batch = db.query(Batch).filter(Batch.id == batch_id).one()
        batch.status = BatchStatusEnum.FUNDING
        db.commit()

    assert client.post(
        "/investments",
        json={"batch_id": batch_id, "amount": "1000.00"},
        headers=auth_headers(3),
    ).status_code == 201

    with TestingSessionLocal() as db:
        batch = db.query(Batch).filter(Batch.id == batch_id).one()
        batch.status = BatchStatusEnum.CLOSED
        db.commit()

    closed = client.get("/batches/closed", headers=auth_headers(3))
    assert closed.status_code == 200
    assert any(item["id"] == batch_id for item in closed.json())

    summary = client.get("/investments/me/summary", headers=auth_headers(3))
    assert summary.json()["closed_investments"] == 1
    assert summary.json()["closed_amount"] == "1000.00"
