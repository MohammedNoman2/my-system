"""
ShiftService — خدمة إدارة الورديات النقدية
تتحكم في فتح وإغلاق الورديات وحساب الفوارق
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cash_shift import CashShift, ShiftStatus
from app.models.financial import FinancialTransaction, PaymentMethod, TransactionType
from app.services.counter_service import get_next_reference_number


class ShiftRequiredException(HTTPException):
    """Raised when a cash voucher is created without an open shift."""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لا توجد وردية نقدية مفتوحة. يجب فتح وردية قبل إصدار سندات نقدية.",
        )


async def open_shift(
    db: AsyncSession,
    user_id: int,
    starting_balance: Decimal,
) -> CashShift:
    """فتح وردية نقدية جديدة — يرفض إذا كانت هناك وردية مفتوحة مسبقاً."""
    # التحقق من عدم وجود وردية مفتوحة
    stmt = select(CashShift).where(
        CashShift.user_id == user_id,
        CashShift.status == ShiftStatus.OPEN,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"لديك وردية مفتوحة بالفعل: {existing.shift_number}. يرجى إغلاقها أولاً.",
        )

    shift_number = await get_next_reference_number(db, "SH")
    shift = CashShift(
        shift_number=shift_number,
        user_id=user_id,
        starting_balance=starting_balance,
        opened_at=datetime.now(timezone.utc),
        status=ShiftStatus.OPEN,
    )
    db.add(shift)
    await db.flush()
    return shift


async def get_active_shift(
    db: AsyncSession,
    user_id: int,
    raise_if_none: bool = False,
) -> Optional[CashShift]:
    """جلب الوردية المفتوحة الحالية للمستخدم."""
    stmt = select(CashShift).where(
        CashShift.user_id == user_id,
        CashShift.status == ShiftStatus.OPEN,
    )
    res = await db.execute(stmt)
    shift = res.scalar_one_or_none()
    if not shift and raise_if_none:
        raise ShiftRequiredException()
    return shift


async def close_shift(
    db: AsyncSession,
    shift_id: int,
    user_id: int,
    actual_cash: Decimal,
    notes: Optional[str] = None,
) -> CashShift:
    """إغلاق الوردية وحساب الفارق بين الرصيد الدفتري والفعلي."""
    # قفل الصف تشاؤمياً
    stmt = select(CashShift).where(
        CashShift.id == shift_id,
        CashShift.user_id == user_id,
    ).with_for_update()
    res = await db.execute(stmt)
    shift = res.scalar_one_or_none()

    if not shift:
        raise HTTPException(status_code=404, detail="الوردية غير موجودة أو لا تخصك")
    if shift.status == ShiftStatus.CLOSED:
        raise HTTPException(status_code=400, detail="الوردية مغلقة مسبقاً")

    # حساب إجمالي المقبوضات والمدفوعات النقدية خلال الوردية
    cash_in_stmt = select(
        func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.0000"))
    ).where(
        FinancialTransaction.shift_id == shift_id,
        FinancialTransaction.type == TransactionType.PAYMENT_IN,
        FinancialTransaction.payment_method == PaymentMethod.CASH,
        FinancialTransaction.is_void == False,
        FinancialTransaction.currency == "YER",
    )
    cash_out_stmt = select(
        func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.0000"))
    ).where(
        FinancialTransaction.shift_id == shift_id,
        FinancialTransaction.type.in_([TransactionType.PAYMENT_OUT, TransactionType.EXPENSE]),
        FinancialTransaction.payment_method == PaymentMethod.CASH,
        FinancialTransaction.is_void == False,
        FinancialTransaction.currency == "YER",
    )

    cash_in = (await db.execute(cash_in_stmt)).scalar() or Decimal("0.0000")
    cash_out = (await db.execute(cash_out_stmt)).scalar() or Decimal("0.0000")

    # ending_system = starting + cash_in - cash_out
    ending_system = (
        Decimal(str(shift.starting_balance))
        + Decimal(str(cash_in))
        - Decimal(str(cash_out))
    ).quantize(Decimal("0.0001"))

    difference = (Decimal(str(actual_cash)) - ending_system).quantize(Decimal("0.0001"))

    shift.ending_balance_system = ending_system
    shift.ending_balance_actual = Decimal(str(actual_cash)).quantize(Decimal("0.0001"))
    shift.difference = difference
    shift.closed_at = datetime.now(timezone.utc)
    shift.status = ShiftStatus.CLOSED
    shift.closing_notes = notes

    await db.flush()
    return shift
