"""
CashShift Model — نموذج الورديات النقدية
يتتبع فتح وإغلاق ورديات الصندوق لكل موظف/محاسب
"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShiftStatus(str, PyEnum):
    OPEN = "open"
    CLOSED = "closed"


class CashShift(Base):
    __tablename__ = "cash_shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shift_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # العهدة الافتتاحية (العمود الأساسي يمثل YER للتوافق مع السجلات السابقة)
    starting_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    starting_balance_sar: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    starting_balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    # الرصيد الدفتري المحسوب آلياً عند الإغلاق لكل عملة
    ending_balance_system: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    ending_balance_system_sar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    ending_balance_system_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    # الرصيد الفعلي المدخل عند الجرد لكل عملة
    ending_balance_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    ending_balance_actual_sar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    ending_balance_actual_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    # فارق العجز أو الفائض (actual - system) لكل عملة
    difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    difference_sar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    difference_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ShiftStatus.OPEN,
        nullable=False,
        index=True,
    )
    closing_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    vouchers = relationship("FinancialTransaction", back_populates="shift")

    __table_args__ = (
        Index("ix_cash_shift_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<CashShift {self.shift_number} user={self.user_id} status={self.status}>"
