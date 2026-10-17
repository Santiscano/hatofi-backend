from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.batchModel import Batch, BatchStatusEnum
from app.models.investmentBatchModel import InvestmentBatch
from app.models.userModel import RoleEnum, User
from app.schemas.investmentBatchSchema import (
    InvestmentAmountUpdate,
    InvestmentCreate,
)
from app.core.config import STELLAR_ENABLED
from app.integrations.stellar_service import ensure_confirmed_transaction


class InvestmentService:
    @staticmethod
    def _get_open_batch(db: Session, batch_id: int) -> Batch:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El lote no existe.",
            )
        if batch.status != BatchStatusEnum.FUNDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El lote no está abierto para inversiones.",
            )
        return batch

    @staticmethod
    def _ensure_investor(user: User) -> None:
        if user.role.name != RoleEnum.INVESTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los usuarios con rol de inversor pueden invertir.",
            )

    @staticmethod
    def _ensure_available_amount(batch: Batch, amount: Decimal) -> None:
        remaining = Decimal(str(batch.target_amount)) - Decimal(
            str(batch.collected_amount or 0)
        ) # calcula el monto restante disponible para inversión
        if amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El monto supera el saldo disponible del lote ({remaining}).",
            )

    @staticmethod
    def invest(
        db: Session, investment: InvestmentCreate, current_user: User
    ) -> InvestmentBatch:
        """Crear una nueva inversión para el usuario actual en el lote especificado."""
        InvestmentService._ensure_investor(current_user)
        batch = InvestmentService._get_open_batch(db, investment.batch_id)
        existing = (
            db.query(InvestmentBatch)
            .filter(
                InvestmentBatch.user_id == current_user.id,
                InvestmentBatch.batch_id == batch.id,
            )
            .first()
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una inversión para este lote; utiliza el endpoint de incremento.",
            )
        InvestmentService._ensure_available_amount(batch, investment.amount)
        if STELLAR_ENABLED and (
            investment.wallet_address is None or investment.transaction_hash is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La inversión requiere wallet y hash de transacción Stellar.",
            )
        if investment.transaction_hash is not None:
            duplicate = (
                db.query(InvestmentBatch)
                .filter(InvestmentBatch.transaction_hash == investment.transaction_hash)
                .first()
            )
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La transacción Stellar ya fue registrada.",
                )
            try:
                ensure_confirmed_transaction(investment.transaction_hash)
            except (RuntimeError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La transacción Stellar no está confirmada: {exc}",
                ) from exc
        record = InvestmentBatch(
            user_id=current_user.id,
            batch_id=batch.id,
            amount=investment.amount,
            wallet_address=investment.wallet_address,
            transaction_hash=investment.transaction_hash,
        )
        batch.collected_amount = Decimal(str(batch.collected_amount or 0)) + investment.amount
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def increase(
        db: Session,
        batch_id: int,
        update: InvestmentAmountUpdate,
        current_user: User,
    ) -> InvestmentBatch:
        InvestmentService._ensure_investor(current_user)
        batch = InvestmentService._get_open_batch(db, batch_id)
        record = (
            db.query(InvestmentBatch)
            .filter(
                InvestmentBatch.user_id == current_user.id,
                InvestmentBatch.batch_id == batch.id,
            )
            .first()
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe una inversión del usuario en este lote.",
            )
        InvestmentService._ensure_available_amount(batch, update.amount)
        record.amount = Decimal(str(record.amount)) + update.amount
        batch.collected_amount = Decimal(str(batch.collected_amount or 0)) + update.amount
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def list_mine(db: Session, current_user: User) -> list[InvestmentBatch]:
        return (
            db.query(InvestmentBatch)
            .filter(InvestmentBatch.user_id == current_user.id)
            .join(InvestmentBatch.batch)
            .order_by(InvestmentBatch.created_at.desc())
            .all()
        )

    @staticmethod
    def get_mine(
        db: Session, batch_id: int, current_user: User
    ) -> InvestmentBatch:
        """Obtener la inversión del usuario actual en un lote específico."""
        record = (
            db.query(InvestmentBatch)
            .filter(
                InvestmentBatch.user_id == current_user.id,
                InvestmentBatch.batch_id == batch_id,
            )
            .first()
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La inversión no existe.",
            )
        return record

    @staticmethod
    def summary(db: Session, current_user: User) -> dict[str, object]:
        """Obtener un resumen de las inversiones del usuario actual.
        Devuelve un diccionario con:
        - open_investments: número de inversiones abiertas (lotes no cerrados)
        - closed_investments: número de inversiones cerradas (lotes cerrados)
        - open_amount: monto total invertido en lotes abiertos
        - closed_amount: monto total invertido en lotes cerrados
        """
        records = InvestmentService.list_mine(db, current_user)
        open_records = [
            record for record in records
            if record.batch.status not in {
                BatchStatusEnum.CLOSED,
                BatchStatusEnum.CANCELLED,
            }
        ]
        closed_records = [
            record for record in records
            if record.batch.status == BatchStatusEnum.CLOSED
        ]
        return {
            "open_investments": len(open_records),
            "closed_investments": len(closed_records),
            "open_amount": sum((Decimal(str(r.amount)) for r in open_records), Decimal("0")),
            "closed_amount": sum((Decimal(str(r.amount)) for r in closed_records), Decimal("0")),
        }

    @staticmethod
    def list_batch_investors(
        db: Session, batch_id: int, current_user: User
    ) -> list[InvestmentBatch]:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El lote no existe.",
            )
        if (
            current_user.role.name != RoleEnum.ADMIN
            and batch.farm.user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para consultar los inversores de este lote.",
            )
        return (
            db.query(InvestmentBatch)
            .filter(InvestmentBatch.batch_id == batch_id)
            .order_by(InvestmentBatch.created_at.asc())
            .all()
        )
