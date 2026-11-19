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


SUPPORTED_SHIFT_CURRENCIES = ("YER", "SAR", "USD")


async def compute_shift_currency_totals(db: AsyncSession, shift: CashShift) -> dict:
    """حساب المقبوضات والمصروفات النقدية والرصيد الدفتري لكل عملة (YER, SAR, USD) في الوردية."""
    stmt = (
        select(
            FinancialTransaction.currency,
            FinancialTransaction.type,
            func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.0000")),
        )
        .where(
            FinancialTransaction.shift_id == shift.id,
            FinancialTransaction.payment_method == PaymentMethod.CASH,
            FinancialTransaction.is_void == False,
        )
        .group_by(FinancialTransaction.currency, FinancialTransaction.type)
    )
    rows = (await db.execute(stmt)).all()

    totals_in = {c: Decimal("0.0000") for c in SUPPORTED_SHIFT_CURRENCIES}
    totals_out = {c: Decimal("0.0000") for c in SUPPORTED_SHIFT_CURRENCIES}
    for curr, tx_type, amt in rows:
        curr_u = (curr or "YER").upper()
        if curr_u not in totals_in:
            continue
        val = Decimal(str(amt or 0)).quantize(Decimal("0.0001"))
        if tx_type == TransactionType.PAYMENT_IN:
            totals_in[curr_u] += val
        elif tx_type in (TransactionType.PAYMENT_OUT, TransactionType.EXPENSE):
            totals_out[curr_u] += val

    starting_map = {
        "YER": Decimal(str(shift.starting_balance or 0)).quantize(Decimal("0.0001")),
        "SAR": Decimal(str(getattr(shift, "starting_balance_sar", 0) or 0)).quantize(Decimal("0.0001")),
        "USD": Decimal(str(getattr(shift, "starting_balance_usd", 0) or 0)).quantize(Decimal("0.0001")),
    }

    result = {}
    for curr in SUPPORTED_SHIFT_CURRENCIES:
        start_val = starting_map[curr]
        in_val = totals_in[curr]
        out_val = totals_out[curr]
        sys_val = (start_val + in_val - out_val).quantize(Decimal("0.0001"))
        result[curr] = {
            "starting": start_val,
            "total_in": in_val,
            "total_out": out_val,
            "system_balance": sys_val,
        }
    return result


async def open_shift(
    db: AsyncSession,
    user_id: int,
    starting_balance: Decimal,
    starting_balance_sar: Decimal = Decimal("0.0000"),
    starting_balance_usd: Decimal = Decimal("0.0000"),
) -> CashShift:
    """فتح وردية نقدية جديدة متعددة العملات — يرفض إذا كانت هناك وردية مفتوحة مسبقاً."""
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
        starting_balance=Decimal(str(starting_balance)).quantize(Decimal("0.0001")),
        starting_balance_sar=Decimal(str(starting_balance_sar or 0)).quantize(Decimal("0.0001")),
        starting_balance_usd=Decimal(str(starting_balance_usd or 0)).quantize(Decimal("0.0001")),
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
    actual_cash_sar: Optional[Decimal] = None,
    actual_cash_usd: Optional[Decimal] = None,
) -> CashShift:
    """إغلاق الوردية وحساب الفارق بين الرصيد الدفتري والفعلي لكل عملة (YER, SAR, USD)."""
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

    by_curr = await compute_shift_currency_totals(db, shift)

    sys_yer = by_curr["YER"]["system_balance"]
    sys_sar = by_curr["SAR"]["system_balance"]
    sys_usd = by_curr["USD"]["system_balance"]

    act_yer = Decimal(str(actual_cash)).quantize(Decimal("0.0001"))
    act_sar = Decimal(str(actual_cash_sar if actual_cash_sar is not None else 0)).quantize(Decimal("0.0001"))
    act_usd = Decimal(str(actual_cash_usd if actual_cash_usd is not None else 0)).quantize(Decimal("0.0001"))

    shift.ending_balance_system = sys_yer
    shift.ending_balance_actual = act_yer
    shift.difference = (act_yer - sys_yer).quantize(Decimal("0.0001"))

    shift.ending_balance_system_sar = sys_sar
    shift.ending_balance_actual_sar = act_sar
    shift.difference_sar = (act_sar - sys_sar).quantize(Decimal("0.0001"))

    shift.ending_balance_system_usd = sys_usd
    shift.ending_balance_actual_usd = act_usd
    shift.difference_usd = (act_usd - sys_usd).quantize(Decimal("0.0001"))

    shift.closed_at = datetime.now(timezone.utc)
    shift.status = ShiftStatus.CLOSED
    shift.closing_notes = notes

    await db.flush()
    return shift
