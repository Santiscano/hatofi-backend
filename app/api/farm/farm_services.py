from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.batchModel import Batch, BatchStatusEnum
from app.models.farmModel import Farm
from app.models.userModel import RoleEnum, User
from app.schemas.farmSchema import (
    FarmCapacityUpdate,
    FarmCreate,
    FarmDetailsUpdate,
)


class FarmService:
    @staticmethod
    def list_farms(db: Session, current_user: User) -> list[Farm]:
        return (
            db.query(Farm)
            .filter(Farm.user_id == current_user.id)
            .order_by(Farm.name.asc())
            .all()
        )

    @staticmethod
    def _get_owned_farm(db: Session, farm_id: int, current_user: User) -> Farm:
        farm = (
            db.query(Farm)
            .filter(Farm.id == farm_id, Farm.user_id == current_user.id)
            .first()
        )
        if farm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La finca no existe o no pertenece al usuario autenticado.",
            )
        return farm

    @staticmethod
    def create_farm(
        db: Session, farm_create: FarmCreate, current_user: User
    ) -> Farm:
        if current_user.role.name != RoleEnum.FARMER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los usuarios con rol de granjero pueden crear fincas.",
            )
        if (
            farm_create.capacity_current_head_count
            > farm_create.capacity_head_count
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad actual no puede superar la capacidad máxima.",
            )

        farm = Farm(**farm_create.model_dump(), user_id=current_user.id)
        db.add(farm)
        db.commit()
        db.refresh(farm)
        return farm

    @staticmethod
    def update_max_capacity(
        db: Session,
        farm_id: int,
        update: FarmCapacityUpdate,
        current_user: User,
    ) -> Farm:
        farm = FarmService._get_owned_farm(db, farm_id, current_user)
        if update.value < farm.capacity_current_head_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La capacidad máxima no puede ser menor que la cantidad actual.",
            )
        farm.capacity_head_count = update.value
        db.commit()
        db.refresh(farm)
        return farm

    @staticmethod
    def update_current_capacity(
        db: Session,
        farm_id: int,
        update: FarmCapacityUpdate,
        current_user: User,
    ) -> Farm:
        farm = FarmService._get_owned_farm(db, farm_id, current_user)
        if update.value > farm.capacity_head_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad actual no puede superar la capacidad máxima.",
            )
        farm.capacity_current_head_count = update.value
        db.commit()
        db.refresh(farm)
        return farm

    @staticmethod
    def update_details(
        db: Session,
        farm_id: int,
        update: FarmDetailsUpdate,
        current_user: User,
    ) -> Farm:
        farm = FarmService._get_owned_farm(db, farm_id, current_user)
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(farm, field, value)
        db.commit()
        db.refresh(farm)
        return farm

    @staticmethod
    def delete_farm(db: Session, farm_id: int, current_user: User) -> None:
        farm = FarmService._get_owned_farm(db, farm_id, current_user)
        active_batch = (
            db.query(Batch)
            .filter(
                Batch.farm_id == farm.id,
                Batch.status.notin_(
                    [BatchStatusEnum.CLOSED, BatchStatusEnum.CANCELLED]
                ),
            )
            .first()
        )
        if active_batch is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar la finca porque tiene lotes activos.",
            )
        db.delete(farm)
        db.commit()
