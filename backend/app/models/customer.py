from typing import Optional
from decimal import Decimal
from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    passport_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True, nullable=True)
    id_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True, nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    # Relationships
    bookings = relationship("Booking", back_populates="customer")
