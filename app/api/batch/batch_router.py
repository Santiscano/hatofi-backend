from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth.auth_token import get_current_user
from app.api.batch.batch_services import BatchService
from app.core.database import get_db
from app.models.userModel import User
from app.models.batchModel import BatchCategoryEnum, BatchStatusEnum
from app.schemas.batchSchema import (
    BatchCreate,
    BatchResponse,
    BatchStatusUpdate,
    BatchUpdate,
)

router = APIRouter(prefix="/batches", tags=["Batches"])


@router.get("/farm/{farm_id}", response_model=list[BatchResponse])
def list_farm_batches(
    farm_id: int,
    status_filter: BatchStatusEnum | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BatchResponse]:
    return BatchService.list_by_farm(db, farm_id, current_user, status_filter)


@router.get("/open", response_model=list[BatchResponse])
def list_open_batches(
    category: BatchCategoryEnum | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[BatchResponse]:
    return BatchService.list_by_status(db, BatchStatusEnum.FUNDING, category)

@router.get("/closed", response_model=list[BatchResponse])
def list_closed_batches(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[BatchResponse]:
    return BatchService.list_by_status(db, BatchStatusEnum.CLOSED)

@router.post("", response_model=BatchResponse, status_code=201)
def create_batch(
    batch: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchResponse:
    return BatchService.create_batch(db, batch, current_user)


@router.patch("/{batch_id}", response_model=BatchResponse)
def update_batch(
    batch_id: int,
    batch: BatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchResponse:
    return BatchService.update_batch(db, batch_id, batch, current_user)


@router.patch("/{batch_id}/status", response_model=BatchResponse)
def update_batch_status(
    batch_id: int,
    status_update: BatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchResponse:
    return BatchService.update_status(db, batch_id, status_update, current_user)
