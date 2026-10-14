from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.batchModel import BatchCategoryEnum, BatchStatusEnum


class BatchCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = None
    category: BatchCategoryEnum
    target_amount: float = Field(gt=0)
    duration_months: int = Field(gt=0)
    funding_start_date: datetime
    farm_id: int = Field(gt=0)


class BatchUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    category: BatchCategoryEnum | None = None
    target_amount: float | None = Field(default=None, gt=0)
    duration_months: int | None = Field(default=None, gt=0)
    funding_start_date: datetime | None = None
    funding_end_date: datetime | None = None


class BatchStatusUpdate(BaseModel):
    status: BatchStatusEnum


class BatchResponse(BaseModel):
    id: int
    title: str
    code: str
    description: str | None = None
    category: BatchCategoryEnum
    target_amount: float
    collected_amount: float
    price_per_share: float
    estimated_roi_percentage: float
    duration_months: int
    funding_start_date: datetime
    funding_end_date: datetime | None = None
    status: BatchStatusEnum
    farm_id: int

    model_config = ConfigDict(from_attributes=True)
