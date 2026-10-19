import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.userModel import Role, RoleEnum


ROLES_FILE = Path(__file__).with_name("data") / "roles.json"


def _load_roles() -> list[dict[str, Any]]:
    with ROLES_FILE.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("The roles seed file must contain a JSON array.")
    return data


def seed_roles(db: Session) -> dict[str, int]:
    """Insert or update roles from JSON without deleting existing roles."""
    roles = _load_roles()
    created = 0
    updated = 0

    try:
        for role_data in roles:
            role_id = role_data["id"]
            role_name = RoleEnum(role_data["name"])
            role = db.query(Role).filter(Role.id == role_id).first()

            if role is None:
                role = db.query(Role).filter(Role.name == role_name).first()

            if role is None:
                db.add(
                    Role(
                        id=role_id,
                        name=role_name,
                        description=role_data.get("description"),
                    )
                )
                created += 1
                continue

            role.name = role_name
            role.description = role_data.get("description")
            updated += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"created": created, "updated": updated, "total": len(roles)}
