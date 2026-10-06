from datetime import datetime
import enum
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"
    ACCOUNTANT = "accountant"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda obj: [e.value for e in obj]),
        default=UserRole.EMPLOYEE,
        nullable=False
    )
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    bookings = relationship("Booking", back_populates="employee", foreign_keys="Booking.employee_id")
    financial_transactions = relationship(
        "FinancialTransaction",
        back_populates="creator",
        foreign_keys="FinancialTransaction.created_by",
    )

