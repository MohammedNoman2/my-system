from datetime import date, datetime
from decimal import Decimal
import enum
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class TransactionType(str, enum.Enum):
    PAYMENT_IN = "payment_in"    # سند قبض
    PAYMENT_OUT = "payment_out"  # سند صرف / دفع
    EXPENSE = "expense"          # مصروفات عامة


class EntityType(str, enum.Enum):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    NONE = "none"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CHECK = "check"


class FinancialTransaction(Base, TimestampMixin):
    __tablename__ = "financial_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, values_callable=lambda obj: [e.value for e in obj]),
        index=True,
        nullable=False,
    )
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, values_callable=lambda obj: [e.value for e in obj]),
        default=EntityType.NONE,
        nullable=False,
    )
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="YER", nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda obj: [e.value for e in obj]),
        default=PaymentMethod.CASH,
        nullable=False,
    )
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expense_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)

    booking_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True
    )

    # ─── Shift FK ───────────────────────────────────────────────────────────
    # nullable=True for backward-compat; new cash vouchers require shift_id
    shift_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("cash_shifts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ─── Void / Cancellation Fields ─────────────────────────────────────────
    is_void: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # رقم قيد العكس المرتبط
    reversal_je_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="financial_transactions")
    voided_by = relationship("User", foreign_keys=[voided_by_id])
    booking = relationship("Booking", back_populates="financial_transactions")
    shift = relationship("CashShift", back_populates="vouchers")
    allocations: Mapped[List["VoucherAllocation"]] = relationship(  # type: ignore[name-defined]
        "VoucherAllocation", back_populates="voucher", cascade="all, delete-orphan"
    )
