import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.farmModel import Farm
    from app.models.investmentBatchModel import InvestmentBatch

# 1. Definimos el Enum para los roles disponibles
class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    DEVELOPER = "develop"
    INVESTOR = "user_investment"
    FARMER = "user_farmer"


# 2. Modelo ORM para la tabla 'roles'
class Role(Base):
    __tablename__ = "roles"

    id              : Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    name            : Mapped[RoleEnum]      = mapped_column(SQLEnum(RoleEnum, name="role_enum"), unique=True, nullable=False) # SQLEnum mapea el Enum de Python a un tipo ENUM o VARCHAR en PostgreSQL
    description     : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    users           : Mapped[list["User"]]  = relationship("User", back_populates="role") # Relación inversa: Un rol puede pertenecer a muchos usuarios (@OneToMany)


# Sintaxis moderna de SQLAlchemy 2.0 utilizando Mapped y mapped_column
class User(Base):
    __tablename__ = "users"

    id              : Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name       : Mapped[str]       = mapped_column(String(100), nullable=False)
    email           : Mapped[str]       = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password : Mapped[str]       = mapped_column(String(255), nullable=False)
    terms_accepted  : Mapped[bool]       = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    is_active       : Mapped[bool]      = mapped_column(Boolean, default=True)
    created_at      : Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    role_id         : Mapped[int]       = mapped_column(Integer, ForeignKey("roles.id"), nullable=False) # Clave Foránea (FK) apuntando a la tabla 'roles' (@ManyToOne)
    role            : Mapped["Role"]    = relationship("Role", back_populates="users") # Objeto de relación para acceder a las propiedades del Rol directamente en Python

    # relaciones con otras tablas
    farms: Mapped[list["Farm"]] = relationship(
        "Farm",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    investments: Mapped[list["InvestmentBatch"]] = relationship(
        "InvestmentBatch",
        back_populates="investor",
        cascade="all, delete-orphan",
    )