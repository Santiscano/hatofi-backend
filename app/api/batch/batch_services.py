from uuid import uuid4
from datetime import timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.batchModel import Batch, BatchCategoryEnum, BatchStatusEnum
from app.models.farmModel import Farm
from app.models.userModel import RoleEnum, User
from app.schemas.batchSchema import BatchCreate, BatchStatusUpdate, BatchUpdate
from app.core.config import STELLAR_ENABLED
from app.integrations.stellar_service import create_batch_on_chain


ALLOWED_STATUS_TRANSITIONS: dict[BatchStatusEnum, set[BatchStatusEnum]] = {
    BatchStatusEnum.DRAFT: {
        BatchStatusEnum.FUNDING,
        BatchStatusEnum.CANCELLED,
    },
    BatchStatusEnum.FUNDING: {BatchStatusEnum.FUNDED},
    BatchStatusEnum.FUNDED: {BatchStatusEnum.BUYING_PROCESS},
    BatchStatusEnum.BUYING_PROCESS: {BatchStatusEnum.IN_PROGRESS},
    BatchStatusEnum.IN_PROGRESS: {BatchStatusEnum.READY_FOR_SALE},
    BatchStatusEnum.READY_FOR_SALE: {BatchStatusEnum.CLOSED},
    BatchStatusEnum.CLOSED: set(),
    BatchStatusEnum.CANCELLED: set(),
}


class BatchService:
    @staticmethod
    def _generate_code() -> str:
        return f"BATCH-{uuid4().hex.upper()}"

    @staticmethod
    def _get_batch(db: Session, batch_id: int) -> Batch:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El lote no existe.",
            )
        return batch

    @staticmethod
    def _can_manage_batch(batch: Batch, current_user: User) -> bool:
        return current_user.role.name == RoleEnum.ADMIN or (
            batch.farm.user_id == current_user.id
        )

    @staticmethod
    def _ensure_can_manage(batch: Batch, current_user: User) -> None:
        if not BatchService._can_manage_batch(batch, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para administrar este lote.",
            )

    @staticmethod
    def list_by_farm(
        db: Session,
        farm_id: int,
        current_user: User,
        batch_status: BatchStatusEnum | None = None,
    ) -> list[Batch]:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        if farm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La finca no existe.",
            )
        if current_user.role.name != RoleEnum.ADMIN and farm.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el propietario de la finca puede consultar sus lotes.",
            )

        query = db.query(Batch).filter(Batch.farm_id == farm_id)
        if batch_status is not None:
            query = query.filter(Batch.status == batch_status)
        return query.order_by(Batch.created_at.desc(), Batch.id.desc()).all()

    @staticmethod
    def create_batch(
        db: Session, batch_create: BatchCreate, current_user: User
    ) -> Batch:
        farm = db.query(Farm).filter(Farm.id == batch_create.farm_id).first()
        if farm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La finca no existe.",
            )
        if (
            current_user.role.name != RoleEnum.ADMIN
            and farm.user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el propietario de la finca o un administrador puede crear lotes.",
            )
        if STELLAR_ENABLED and not batch_create.farmer_address:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La dirección Stellar del farmer es obligatoria para crear el batch.",
            )

        batch = Batch(
            title=batch_create.title,
            description=batch_create.description,
            category=batch_create.category,
            target_amount=batch_create.target_amount,
            duration_months=batch_create.duration_months,
            funding_start_date=batch_create.funding_start_date,
            farm_id=batch_create.farm_id,
            code=BatchService._generate_code(),
            status=BatchStatusEnum.DRAFT,
            price_per_share=batch_create.price_per_share,
            estimated_roi_percentage=batch_create.estimated_roi_percentage,
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        if STELLAR_ENABLED:
            funding_start = batch.funding_start_date
            if funding_start.tzinfo is None:
                funding_start = funding_start.replace(tzinfo=timezone.utc)
            try:
                tx_hash = create_batch_on_chain(
                    batch_id=batch.id,
                    farm_id=batch.farm_id,
                    code=batch.code,
                    title=batch.title,
                    description=batch.description,
                    category=batch.category.value,
                    target_amount=batch.target_amount,
                    price_per_share=batch.price_per_share,
                    estimated_roi_percentage=batch.estimated_roi_percentage,
                    duration_months=batch.duration_months,
                    funding_start_timestamp=int(funding_start.timestamp()),
                    funding_end_timestamp=(
                        int(batch.funding_end_date.timestamp())
                        if batch.funding_end_date
                        else 0
                    ),
                    farmer_address=batch_create.farmer_address,
                )
            except (RuntimeError, ValueError) as exc:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"No se pudo publicar el batch en Stellar: {exc}",
                ) from exc
            batch.blockchain_tx_hash = tx_hash
            db.commit()
            db.refresh(batch)
        return batch

    @staticmethod
    def update_batch(
        db: Session,
        batch_id: int,
        batch_update: BatchUpdate,
        current_user: User,
    ) -> Batch:
        batch = BatchService._get_batch(db, batch_id)
        BatchService._ensure_can_manage(batch, current_user)
        if batch.status != BatchStatusEnum.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se puede editar un lote en estado DRAFT.",
            )

        for field, value in batch_update.model_dump(exclude_unset=True).items():
            setattr(batch, field, value)
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def update_status(
        db: Session,
        batch_id: int,
        status_update: BatchStatusUpdate,
        current_user: User,
    ) -> Batch:
        batch = BatchService._get_batch(db, batch_id)
        BatchService._ensure_can_manage(batch, current_user)
        allowed_statuses = ALLOWED_STATUS_TRANSITIONS[batch.status]
        if status_update.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"No se puede cambiar el lote de {batch.status.value} "
                    f"a {status_update.status.value}."
                ),
            )
        batch.status = status_update.status
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def list_by_status(
        db: Session,
        batch_status: BatchStatusEnum,
        category: BatchCategoryEnum | None = None,
    ) -> list[Batch]:
        query = db.query(Batch).filter(Batch.status == batch_status)
        if category is not None:
            query = query.filter(Batch.category == category)
        return query.order_by(Batch.created_at.desc()).all()
