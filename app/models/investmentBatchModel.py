from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.batchModel import BatchStatusEnum


if TYPE_CHECKING:
    from app.models.batchModel import Batch
    from app.models.userModel import User


class InvestmentBatch(Base):
    """Association between an investor and an investment batch."""

    __tablename__ = "investment_batches"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("batches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    amount: Mapped[float] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    wallet_address: Mapped[str | None] = mapped_column(String(56), nullable=True)
    transaction_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    investor: Mapped["User"] = relationship("User", back_populates="investments")
    batch: Mapped["Batch"] = relationship("Batch", back_populates="investments")

    @property
    def batch_status(self) -> BatchStatusEnum:
        return self.batch.status
