from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.auth.auth_token import get_current_user
from app.api.farm.farm_services import FarmService
from app.core.database import get_db
from app.models.userModel import User
from app.schemas.farmSchema import (
    FarmCapacityUpdate,
    FarmCreate,
    FarmDetailsUpdate,
    FarmResponse,
)

router = APIRouter(prefix="/farms", tags=["Farms"])


@router.get("", response_model=list[FarmResponse])
def list_farms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FarmResponse]:
    return FarmService.list_farms(db, current_user)


@router.post("", response_model=FarmResponse, status_code=status.HTTP_201_CREATED)
def create_farm(
    farm: FarmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    return FarmService.create_farm(db, farm, current_user)


@router.patch(
    "/{farm_id}/capacity/max",
    response_model=FarmResponse,
)
def update_max_capacity(
    farm_id: int,
    update: FarmCapacityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    return FarmService.update_max_capacity(db, farm_id, update, current_user)


@router.patch(
    "/{farm_id}/capacity/current",
    response_model=FarmResponse,
)
def update_current_capacity(
    farm_id: int,
    update: FarmCapacityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    return FarmService.update_current_capacity(db, farm_id, update, current_user)


@router.patch("/{farm_id}/details", response_model=FarmResponse)
def update_farm_details(
    farm_id: int,
    update: FarmDetailsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    return FarmService.update_details(db, farm_id, update, current_user)


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(
    farm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    FarmService.delete_farm(db, farm_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
