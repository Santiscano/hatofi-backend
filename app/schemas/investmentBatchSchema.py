from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.batchModel import BatchStatusEnum


class InvestmentCreate(BaseModel):
    batch_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    wallet_address: str | None = Field(default=None, min_length=56, max_length=56)
    transaction_hash: str | None = Field(default=None, min_length=64, max_length=128)


class InvestmentAmountUpdate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class InvestmentResponse(BaseModel):
    user_id: int
    batch_id: int
    amount: Decimal
    batch_status: BatchStatusEnum
    created_at: datetime
    updated_at: datetime
    wallet_address: str | None = None
    transaction_hash: str | None = None

    model_config = ConfigDict(from_attributes=True)


class InvestmentSummary(BaseModel):
    open_investments: int
    closed_investments: int
    open_amount: Decimal
    closed_amount: Decimal


class BatchInvestorResponse(BaseModel):
    user_id: int
    batch_id: int
    amount: Decimal

    model_config = ConfigDict(from_attributes=True)
