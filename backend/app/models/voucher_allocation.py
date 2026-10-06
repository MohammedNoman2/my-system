"""
VoucherAllocation Model — تخصيص السداد المرن
يربط السند المالي بالتذاكر المراد تسديدها مع دعم تعدد العملات
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.accounting import AccountCurrency


class VoucherAllocation(Base):
    __tablename__ = "voucher_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # FK to financial_transactions
    voucher_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("financial_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # FK to bookings (nullable — unallocated amount = credit on account)
    booking_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # المبلغ المخصوم بعملة السند المستلم
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # عملة الحجز الأصلية
    target_currency: Mapped[AccountCurrency] = mapped_column(
        Enum(AccountCurrency, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # سعر الصرف المعتمد (سعر سند ÷ سعر تذكرة)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("1.000000"), nullable=False
    )

    # المبلغ المسدّد فعلياً من رصيد التذكرة بعملتها الأصلية
    allocated_in_booking_currency: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    voucher = relationship("FinancialTransaction", back_populates="allocations")
    booking = relationship("Booking", back_populates="voucher_allocations")

    def __repr__(self) -> str:
        return (
            f"<VoucherAllocation vid={self.voucher_id} bid={self.booking_id} "
            f"amount={self.allocated_amount} rate={self.exchange_rate}>"
        )
