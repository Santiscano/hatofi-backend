import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.cattleModel import Cattle
    from app.models.farmModel import Farm
    from app.models.investmentBatchModel import InvestmentBatch


class BatchStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"               # En borrador / configuración
    FUNDING = "FUNDING"           # Abierto a inversión DeFi
    FUNDED = "FUNDED"             # Meta alcanzada, listo para compra
    BUYING_PROCESS = "BUYING_PROCESS" # Proceso de compra del ganado (1-2 meses)
    IN_PROGRESS = "IN_PROGRESS"   # Ganado comprado y entregado al ganadero (15-18 meses)
    READY_FOR_SALE = "READY_FOR_SALE"  # Período cumplido, listo para comercializar
    CLOSED = "CLOSED"             # Ganado vendido y retornos liquidados a inversores
    CANCELLED = "CANCELLED"       # No alcanzó la meta o cancelado


class BatchCategoryEnum(str, enum.Enum):
    CEBA_INTENSIVA = "CEBA_INTENSIVA"
    CRIA_LEVANTE = "CRIA_LEVANTE"


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)  # ej. LOTE-2026-01
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[BatchCategoryEnum] = mapped_column(
        SQLEnum(BatchCategoryEnum, name="batch_category_enum"),
        default=BatchCategoryEnum.CEBA_INTENSIVA,
        server_default=BatchCategoryEnum.CEBA_INTENSIVA.value,
        nullable=False,
    )

    # Métricas Financieras (Usamos Numeric/Decimal para manejo preciso de dinero/crypto)
    target_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)  # Meta de recaudación
    collected_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0.00) # Monto recaudado hasta el momento
    price_per_share: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False) # Precio por acción o unidad de inversión (ej. 1 acción = $100)
    estimated_roi_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.00)  # ej. 15.50%

    # Tiempos del Proyecto
    duration_months: Mapped[int] = mapped_column(nullable=False)  # ej. 15 o 18 meses
    funding_start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False) # fecha de inicio de la campaña de inversión
    funding_end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, default=None) # fecha de cierre de la campaña de inversión
    estimated_settlement_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True) # fecha estimada de liquidación de retornos a inversores (después de venta)

    # Estado y Datos Blockchain / DeFi
    status: Mapped[BatchStatusEnum] = mapped_column(
        SQLEnum(BatchStatusEnum, name="batch_status_enum"),
        default=BatchStatusEnum.DRAFT,
        nullable=False
    )
    smart_contract_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    blockchain_tx_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Llaves Foráneas
    farm_id: Mapped[int] = mapped_column(Integer, ForeignKey("farms.id"), nullable=False)

    # Relaciones
    farm: Mapped["Farm"] = relationship("Farm", back_populates="batches")
    investments: Mapped[list["InvestmentBatch"]] = relationship(
        "InvestmentBatch",
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    cattle: Mapped[list["Cattle"]] = relationship(
        "Cattle",
        back_populates="batch",
        cascade="all, delete-orphan",
    )
