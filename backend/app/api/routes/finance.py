"""
Finance Routes — الترقية المعمارية الكاملة للمنظومة المالية
يشمل: الورديات، تخصيص السداد المتعدد العملات، القيود العكسية، حماية التزامن
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_accountant_or_admin
from app.core.database import get_db
from app.models.accounting import AccountCurrency
from app.models.booking import Booking, BookingStatus
from app.models.cash_shift import CashShift, ShiftStatus
from app.models.customer import Customer
from app.models.financial import (
    EntityType,
    FinancialTransaction,
    PaymentMethod,
    TransactionType,
)
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.models.settings import Settings
from app.models.voucher_allocation import VoucherAllocation
from app.schemas.financial import (
    ExpenseCreate,
    FinancialTransactionResponse,
    LedgerEntryResponse,
    PaymentVoucherCreate,
    ReceiptVoucherCreate,
)
from app.services.accounting_service import (
    create_journal_entry,
    get_account_by_code,
    get_cash_balance_with_lock,
    get_entity_account,
    get_entity_balance,
    get_exchange_rate_to_yer,
    init_chart_of_accounts,
)
from app.services.counter_service import get_next_reference_number
from app.services.shift_service import (
    ShiftRequiredException,
    close_shift,
    get_active_shift,
    open_shift,
)
from app.utils.audit import log_audit_event

router = APIRouter(prefix="/finance", tags=["Finance"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas (inline for simplicity)
# ─────────────────────────────────────────────────────────────────────────────

class OpenShiftRequest(BaseModel):
    starting_balance: Decimal = Field(ge=0, description="العهدة النقدية الافتتاحية بالريال اليمني")


class CloseShiftRequest(BaseModel):
    shift_id: int
    actual_cash: Decimal = Field(ge=0, description="النقدية الفعلية عند الجرد")
    notes: Optional[str] = None


class AllocationItem(BaseModel):
    booking_id: int
    allocated_amount: Decimal = Field(gt=0)
    exchange_rate: Decimal = Field(default=Decimal("1.000000"), gt=0)


class ReceiptVoucherV2Create(BaseModel):
    """سند قبض مع دعم تعدد التخصيصات والعملات المتقاطعة"""
    entity_type: EntityType
    entity_id: int
    total_amount: Decimal = Field(gt=0)
    currency: str = "YER"
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    transaction_date: date = Field(default_factory=date.today)
    # قائمة تخصيصات التذاكر (اختيارية — الفائض يبقى رصيد دائن)
    allocations: List[AllocationItem] = Field(default_factory=list)


class VoidVoucherRequest(BaseModel):
    void_reason: str = Field(min_length=5, description="سبب الإلغاء (إلزامي)")


# ─────────────────────────────────────────────────────────────────────────────
# 1. SHIFT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/shifts/open", status_code=status.HTTP_201_CREATED)
async def open_cash_shift(
    data: OpenShiftRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """فتح وردية نقدية جديدة — متاح للجميع (موظف/محاسب/مدير)."""
    shift = await open_shift(db, current_user.id, data.starting_balance)
    await log_audit_event(db, "INSERT", "cash_shifts", user=current_user,
                          record_id=shift.id, new_data={"shift_number": shift.shift_number}, request=request)
    await db.commit()
    return {
        "message": "تم فتح الوردية بنجاح",
        "shift_id": shift.id,
        "shift_number": shift.shift_number,
        "started_at": shift.opened_at.isoformat(),
        "starting_balance": float(shift.starting_balance),
    }


@router.get("/shifts/active")
async def get_active_shift_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """جلب حالة الوردية الحالية للمستخدم."""
    shift = await get_active_shift(db, current_user.id)
    if not shift:
        return {"active": False, "shift": None}

    # حساب إجمالي المقبوضات والمصروفات خلال الوردية
    cash_in = await db.execute(
        select(func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0")))
        .where(FinancialTransaction.shift_id == shift.id,
               FinancialTransaction.type == TransactionType.PAYMENT_IN,
               FinancialTransaction.payment_method == PaymentMethod.CASH,
               FinancialTransaction.currency == "YER",
               FinancialTransaction.is_void == False)
    )
    cash_out = await db.execute(
        select(func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0")))
        .where(FinancialTransaction.shift_id == shift.id,
               FinancialTransaction.type.in_([TransactionType.PAYMENT_OUT, TransactionType.EXPENSE]),
               FinancialTransaction.payment_method == PaymentMethod.CASH,
               FinancialTransaction.currency == "YER",
               FinancialTransaction.is_void == False)
    )
    total_in = cash_in.scalar() or Decimal("0")
    total_out = cash_out.scalar() or Decimal("0")

    return {
        "active": True,
        "shift": {
            "id": shift.id,
            "shift_number": shift.shift_number,
            "opened_at": shift.opened_at.isoformat(),
            "starting_balance": float(shift.starting_balance),
            "total_in": float(total_in),
            "total_out": float(total_out),
            "current_system_balance": float(Decimal(str(shift.starting_balance)) + Decimal(str(total_in)) - Decimal(str(total_out))),
        }
    }


@router.post("/shifts/close")
async def close_cash_shift(
    data: CloseShiftRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """إغلاق الوردية وحساب الفارق."""
    shift = await close_shift(db, data.shift_id, current_user.id, data.actual_cash, data.notes)
    await log_audit_event(db, "UPDATE", "cash_shifts", user=current_user, record_id=shift.id,
                          new_data={"status": "closed", "difference": float(shift.difference or 0)}, request=request)
    await db.commit()
    return {
        "message": "تم إغلاق الوردية بنجاح",
        "shift_number": shift.shift_number,
        "starting_balance": float(shift.starting_balance),
        "ending_balance_system": float(shift.ending_balance_system),
        "ending_balance_actual": float(shift.ending_balance_actual),
        "difference": float(shift.difference),
        "closed_at": shift.closed_at.isoformat(),
    }


@router.get("/shifts/history")
async def list_shifts(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """قائمة الورديات السابقة (محاسب/مدير فقط)."""
    stmt = select(CashShift).order_by(desc(CashShift.opened_at)).limit(limit)
    res = await db.execute(stmt)
    shifts = res.scalars().all()
    return [
        {
            "id": s.id, "shift_number": s.shift_number, "user_id": s.user_id,
            "status": s.status.value, "opened_at": s.opened_at.isoformat(),
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
            "starting_balance": float(s.starting_balance),
            "ending_balance_system": float(s.ending_balance_system) if s.ending_balance_system else None,
            "ending_balance_actual": float(s.ending_balance_actual) if s.ending_balance_actual else None,
            "difference": float(s.difference) if s.difference else None,
        }
        for s in shifts
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 2. RECEIPT VOUCHER — Multi-Allocation + Cross-Currency
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/receipt-voucher", status_code=status.HTTP_201_CREATED)
async def create_receipt_voucher(
    data: ReceiptVoucherCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """سند قبض بسيط (متوافق مع الـ API القديم)."""
    await init_chart_of_accounts(db)
    ref_num = await get_next_reference_number(db, "RC")

    # Shift check for CASH payments
    shift_id = None
    if data.payment_method == PaymentMethod.CASH:
        shift = await get_active_shift(db, current_user.id, raise_if_none=False)
        if shift:
            shift_id = shift.id

    entity_name = ""
    if data.entity_type == EntityType.CUSTOMER:
        customer = (await db.execute(select(Customer).where(Customer.id == data.entity_id))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="العميل غير موجود")
        entity_name = customer.name
    elif data.entity_type == EntityType.SUPPLIER:
        supplier = (await db.execute(select(Supplier).where(Supplier.id == data.entity_id))).scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="المورد غير موجود")
        entity_name = supplier.name

    if data.booking_id:
        booking = (await db.execute(select(Booking).where(Booking.id == data.booking_id))).scalar_one_or_none()
        if booking:
            if data.amount > booking.remaining_amount:
                raise HTTPException(status_code=400,
                    detail=f"المبلغ ({data.amount}) أكبر من المتبقي على الحجز ({booking.remaining_amount})")
            booking.paid_amount += data.amount
            booking.remaining_amount -= data.amount
            if booking.status == BookingStatus.PENDING and booking.paid_amount > 0:
                booking.status = BookingStatus.CONFIRMED

    tx = FinancialTransaction(
        transaction_id=ref_num, type=TransactionType.PAYMENT_IN,
        entity_type=data.entity_type, entity_id=data.entity_id,
        amount=data.amount, currency=data.currency,
        payment_method=data.payment_method, reference_number=data.reference_number,
        notes=data.notes, transaction_date=data.transaction_date,
        booking_id=data.booking_id, created_by=current_user.id, shift_id=shift_id,
    )
    db.add(tx)

    je_ref = await get_next_reference_number(db, "JE")
    cash_acc = await get_account_by_code(db, f"1101-{data.currency}")
    if data.entity_type == EntityType.CUSTOMER:
        entity_acc = await get_entity_account(db, "customer", data.entity_id, data.currency, entity_name)
    else:
        entity_acc = await get_entity_account(db, "supplier", data.entity_id, data.currency, entity_name)

    await create_journal_entry(session=db, entry_number=je_ref, reference_type="RECEIPT",
        reference_id=ref_num, currency=data.currency,
        description=f"سند قبض {ref_num} من {entity_name}",
        lines_data=[
            {"account_id": cash_acc.id, "debit": data.amount, "credit": Decimal("0.0000")},
            {"account_id": entity_acc.id, "debit": Decimal("0.0000"), "credit": data.amount},
        ])

    if data.entity_type == EntityType.CUSTOMER:
        customer.balance = await get_entity_balance(db, "customer", customer.id)
    elif data.entity_type == EntityType.SUPPLIER:
        supplier.balance = await get_entity_balance(db, "supplier", supplier.id)

    await log_audit_event(db, "INSERT", "financial_transactions", user=current_user,
        new_data={"transaction_id": ref_num, "type": "payment_in", "amount": float(data.amount)}, request=request)
    await db.commit()
    return {"message": "تم إنشاء سند القبض بنجاح", "transaction_id": ref_num}


@router.post("/receipt-voucher/v2", status_code=status.HTTP_201_CREATED)
async def create_receipt_voucher_v2(
    data: ReceiptVoucherV2Create,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    سند قبض متقدم مع:
    - تخصيص متعدد للتذاكر
    - دعم تسوية العملات المتقاطعة
    - فروق صرف تلقائية لحساب 4901/5901-YER
    - ربط الوردية النقدية
    """
    await init_chart_of_accounts(db)

    # ─── Shift Check ───────────────────────────────────────────────────────
    shift_id = None
    if data.payment_method == PaymentMethod.CASH:
        shift = await get_active_shift(db, current_user.id, raise_if_none=False)
        if shift:
            shift_id = shift.id

    # ─── Validate totals ───────────────────────────────────────────────────
    total_allocated = sum(a.allocated_amount for a in data.allocations)
    if total_allocated > data.total_amount + Decimal("0.01"):
        raise HTTPException(status_code=400,
            detail=f"إجمالي التخصيصات ({total_allocated}) أكبر من مبلغ السند ({data.total_amount})")

    # ─── Entity Resolution ────────────────────────────────────────────────
    entity_name = ""
    customer = supplier = None
    if data.entity_type == EntityType.CUSTOMER:
        customer = (await db.execute(select(Customer).where(Customer.id == data.entity_id))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="العميل غير موجود")
        entity_name = customer.name
    elif data.entity_type == EntityType.SUPPLIER:
        supplier = (await db.execute(select(Supplier).where(Supplier.id == data.entity_id))).scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="المورد غير موجود")
        entity_name = supplier.name

    ref_num = await get_next_reference_number(db, "RC")

    # ─── Create FinancialTransaction ─────────────────────────────────────
    tx = FinancialTransaction(
        transaction_id=ref_num, type=TransactionType.PAYMENT_IN,
        entity_type=data.entity_type, entity_id=data.entity_id,
        amount=data.total_amount, currency=data.currency,
        payment_method=data.payment_method, reference_number=data.reference_number,
        notes=data.notes, transaction_date=data.transaction_date,
        created_by=current_user.id, shift_id=shift_id,
    )
    db.add(tx)
    await db.flush()

    # ─── Process Allocations ─────────────────────────────────────────────
    je_lines = []
    cash_acc = await get_account_by_code(db, f"1101-{data.currency}")
    voucher_rate_to_yer = await get_exchange_rate_to_yer(db, data.currency)
    cash_debit_base = (data.total_amount * voucher_rate_to_yer).quantize(Decimal("0.0001"))
    
    je_lines.append({
        "account_id": cash_acc.id, 
        "debit": data.total_amount, 
        "credit": Decimal("0.0000"),
        "debit_base": cash_debit_base,
        "credit_base": Decimal("0.0000")
    })

    total_credit_base = Decimal("0.0000")

    for alloc_item in data.allocations:
        booking = (await db.execute(select(Booking).where(Booking.id == alloc_item.booking_id))).scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail=f"الحجز #{alloc_item.booking_id} غير موجود")

        booking_currency = booking.currency
        # سعر الصرف: عملة السند → عملة الحجز
        rate = alloc_item.exchange_rate
        allocated_in_booking_curr = (alloc_item.allocated_amount * rate).quantize(Decimal("0.0001"))

        # التحقق من عدم تجاوز المتبقي
        if allocated_in_booking_curr > booking.remaining_amount + Decimal("0.05"):
            raise HTTPException(status_code=400,
                detail=f"الحجز #{booking.ticket_number}: المبلغ المخصص ({allocated_in_booking_curr} {booking_currency}) "
                       f"يتجاوز المتبقي ({booking.remaining_amount} {booking_currency})")

        # تحديث الحجز
        booking.paid_amount = (Decimal(str(booking.paid_amount)) + allocated_in_booking_curr).quantize(Decimal("0.0001"))
        booking.remaining_amount = max(
            Decimal("0.0000"),
            (Decimal(str(booking.remaining_amount)) - allocated_in_booking_curr).quantize(Decimal("0.0001"))
        )
        if booking.status == BookingStatus.PENDING and booking.paid_amount > 0:
            booking.status = BookingStatus.CONFIRMED

        # تسجيل التخصيص
        alloc = VoucherAllocation(
            voucher_id=tx.id,
            booking_id=booking.id,
            allocated_amount=alloc_item.allocated_amount,
            target_currency=AccountCurrency(booking_currency),
            exchange_rate=rate,
            allocated_in_booking_currency=allocated_in_booking_curr,
        )
        db.add(alloc)

        # قيد دائن لحساب العميل بعملة الحجز
        cust_acc = await get_entity_account(db, "customer" if data.entity_type == EntityType.CUSTOMER else "supplier",
                                            data.entity_id, booking_currency, entity_name)
        # debit_base and credit_base via FX
        booking_rate_to_yer = await get_exchange_rate_to_yer(db, booking_currency)
        credit_base = (allocated_in_booking_curr * booking_rate_to_yer).quantize(Decimal("0.0001"))
        total_credit_base += credit_base
        je_lines.append({
            "account_id": cust_acc.id,
            "debit": Decimal("0.0000"),
            "credit": allocated_in_booking_curr,
            "debit_base": Decimal("0.0000"),
            "credit_base": credit_base,
        })

    # الفائض (تحت الحساب) يُقيَّد للحساب العام
    unallocated = (data.total_amount - total_allocated).quantize(Decimal("0.0001"))
    if unallocated > Decimal("0.0001"):
        general_cust_acc = await get_entity_account(
            db, "customer" if data.entity_type == EntityType.CUSTOMER else "supplier",
            data.entity_id, data.currency, entity_name)
        unallocated_credit_base = (unallocated * voucher_rate_to_yer).quantize(Decimal("0.0001"))
        total_credit_base += unallocated_credit_base
        je_lines.append({
            "account_id": general_cust_acc.id,
            "debit": Decimal("0.0000"),
            "credit": unallocated,
            "debit_base": Decimal("0.0000"),
            "credit_base": unallocated_credit_base
        })

    # Calculate FX Difference
    fx_diff = (cash_debit_base - total_credit_base).quantize(Decimal("0.0001"))
    if abs(fx_diff) > Decimal("0.0500"):
        fx_local = (abs(fx_diff) / voucher_rate_to_yer).quantize(Decimal("0.0001"))
        if fx_diff > 0:
            fx_acc = await get_account_by_code(db, "4901-YER")
            je_lines.append({
                "account_id": fx_acc.id,
                "debit": Decimal("0.0000"),
                "credit": fx_local,
                "debit_base": Decimal("0.0000"),
                "credit_base": fx_diff
            })
        else:
            fx_acc = await get_account_by_code(db, "5901-YER")
            je_lines.append({
                "account_id": fx_acc.id,
                "debit": fx_local,
                "credit": Decimal("0.0000"),
                "debit_base": abs(fx_diff),
                "credit_base": Decimal("0.0000")
            })

    # ─── Create Balanced Journal Entry ───────────────────────────────────
    je_ref = await get_next_reference_number(db, "JE")
    await create_journal_entry(
        session=db, entry_number=je_ref, reference_type="RECEIPT",
        reference_id=ref_num, currency=data.currency,
        description=f"سند قبض {ref_num} من {entity_name} - {len(data.allocations)} تخصيص(ات)",
        lines_data=je_lines,
    )

    # تحديث رصيد الكيان
    if customer:
        customer.balance = await get_entity_balance(db, "customer", customer.id)
    if supplier:
        supplier.balance = await get_entity_balance(db, "supplier", supplier.id)

    await log_audit_event(db, "INSERT", "financial_transactions", user=current_user,
        new_data={"transaction_id": ref_num, "type": "payment_in",
                  "amount": float(data.total_amount), "allocations": len(data.allocations)}, request=request)
    await db.commit()

    return {
        "message": "تم إنشاء سند القبض بنجاح مع التخصيصات",
        "transaction_id": ref_num,
        "je_reference": je_ref,
        "allocations_count": len(data.allocations),
        "unallocated_balance": float(unallocated),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. PAYMENT VOUCHER — Pessimistic Lock + Insufficient Funds
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/payment-voucher", status_code=status.HTTP_201_CREATED)
async def create_payment_voucher(
    data: PaymentVoucherCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """سند صرف مع حماية تشاؤمية من العجز النقدي."""
    await init_chart_of_accounts(db)

    # ─── Concurrency Guard: Lock cash account and check balance ──────────
    if data.payment_method == PaymentMethod.CASH:
        current_balance = await get_cash_balance_with_lock(db, data.currency)
        if current_balance - Decimal(str(data.amount)) < Decimal("0.0000"):
            raise HTTPException(status_code=400,
                detail=f"رصيد الصندوق ({float(current_balance)} {data.currency}) "
                       f"غير كافٍ لتنفيذ الصرف ({float(data.amount)} {data.currency}). "
                       "تم رفض العملية لمنع العجز النقدي.")

    # Shift check
    shift_id = None
    if data.payment_method == PaymentMethod.CASH:
        shift = await get_active_shift(db, current_user.id, raise_if_none=False)
        if shift:
            shift_id = shift.id

    ref_num = await get_next_reference_number(db, "PY")

    supplier = customer = None
    entity_name = ""
    if data.entity_type == EntityType.SUPPLIER:
        supplier = (await db.execute(select(Supplier).where(Supplier.id == data.entity_id))).scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="المورد غير موجود")
        entity_name = supplier.name
    elif data.entity_type == EntityType.CUSTOMER:
        customer = (await db.execute(select(Customer).where(Customer.id == data.entity_id))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="العميل غير موجود")
        entity_name = customer.name

    tx = FinancialTransaction(
        transaction_id=ref_num, type=TransactionType.PAYMENT_OUT,
        entity_type=data.entity_type, entity_id=data.entity_id,
        amount=data.amount, currency=data.currency,
        payment_method=data.payment_method, reference_number=data.reference_number,
        notes=data.notes, transaction_date=data.transaction_date,
        booking_id=data.booking_id, created_by=current_user.id, shift_id=shift_id,
    )
    db.add(tx)

    je_ref = await get_next_reference_number(db, "JE")
    cash_acc = await get_account_by_code(db, f"1101-{data.currency}")
    if supplier:
        entity_acc = await get_entity_account(db, "supplier", data.entity_id, data.currency, entity_name)
    else:
        entity_acc = await get_entity_account(db, "customer", data.entity_id, data.currency, entity_name)

    await create_journal_entry(session=db, entry_number=je_ref, reference_type="PAYMENT",
        reference_id=ref_num, currency=data.currency,
        description=f"سند صرف {ref_num} إلى {entity_name}",
        lines_data=[
            {"account_id": entity_acc.id, "debit": data.amount, "credit": Decimal("0.0000")},
            {"account_id": cash_acc.id, "debit": Decimal("0.0000"), "credit": data.amount},
        ])

    if supplier:
        supplier.balance = await get_entity_balance(db, "supplier", supplier.id)
    elif customer:
        customer.balance = await get_entity_balance(db, "customer", customer.id)

    await log_audit_event(db, "INSERT", "financial_transactions", user=current_user,
        new_data={"transaction_id": ref_num, "type": "payment_out", "amount": float(data.amount)}, request=request)
    await db.commit()
    return {"message": "تم إنشاء سند الصرف بنجاح", "transaction_id": ref_num}


# ─────────────────────────────────────────────────────────────────────────────
# 4. EXPENSE
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/expense", status_code=status.HTTP_201_CREATED)
async def create_expense(
    data: ExpenseCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await init_chart_of_accounts(db)
    ref_num = await get_next_reference_number(db, "EX")

    # Concurrency guard for cash expenses
    if data.payment_method == PaymentMethod.CASH:
        current_balance = await get_cash_balance_with_lock(db, data.currency)
        if current_balance - Decimal(str(data.amount)) < Decimal("0.0000"):
            raise HTTPException(status_code=400,
                detail=f"رصيد الصندوق ({float(current_balance)} {data.currency}) غير كافٍ للمصروف.")

    shift_id = None
    if data.payment_method == PaymentMethod.CASH:
        shift = await get_active_shift(db, current_user.id, raise_if_none=False)
        if shift:
            shift_id = shift.id

    tx = FinancialTransaction(
        transaction_id=ref_num, type=TransactionType.EXPENSE,
        entity_type=EntityType.NONE, entity_id=None,
        amount=data.amount, currency=data.currency,
        payment_method=data.payment_method, reference_number=data.reference_number,
        expense_type=data.expense_type, notes=data.notes,
        transaction_date=data.transaction_date, created_by=current_user.id,
        shift_id=shift_id,
    )
    db.add(tx)

    je_ref = await get_next_reference_number(db, "JE")
    cash_acc = await get_account_by_code(db, f"1101-{data.currency}")
    exp_acc = await get_account_by_code(db, f"5201-{data.currency}")

    await create_journal_entry(session=db, entry_number=je_ref, reference_type="EXPENSE",
        reference_id=ref_num, currency=data.currency,
        description=f"مصروف {ref_num} ({data.expense_type})",
        lines_data=[
            {"account_id": exp_acc.id, "debit": data.amount, "credit": Decimal("0.0000")},
            {"account_id": cash_acc.id, "debit": Decimal("0.0000"), "credit": data.amount},
        ])

    await log_audit_event(db, "INSERT", "financial_transactions", user=current_user,
        new_data={"transaction_id": ref_num, "type": "expense", "amount": float(data.amount)}, request=request)
    await db.commit()
    return {"message": "تم تسجيل المصروف بنجاح", "transaction_id": ref_num}


# ─────────────────────────────────────────────────────────────────────────────
# 5. VOID VOUCHER — Mirror Reversal Journal Entry
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/vouchers/{voucher_id}/void", status_code=status.HTTP_200_OK)
async def void_voucher(
    voucher_id: int,
    data: VoidVoucherRequest,
    request: Request,
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    إلغاء سند مالي مع توليد قيد عكسي متطابق (Mirror Reversal JE).
    المتطلبات:
      - المستخدم: محاسب أو مدير فقط
      - سبب الإلغاء إلزامي
      - السند يجب ألا يكون ملغى مسبقاً
    """
    from sqlalchemy.orm import selectinload
    from app.models.accounting import JournalEntry, JournalEntryLine, Account

    # جلب السند مع التخصيصات
    stmt = (select(FinancialTransaction)
            .where(FinancialTransaction.id == voucher_id)
            .options(selectinload(FinancialTransaction.allocations)))
    res = await db.execute(stmt)
    voucher = res.scalar_one_or_none()

    if not voucher:
        raise HTTPException(status_code=404, detail="السند غير موجود")
    if voucher.is_void:
        raise HTTPException(status_code=400,
            detail=f"السند {voucher.transaction_id} ملغى مسبقاً في {voucher.voided_at}")

    # ─── Reverse Booking Allocations ────────────────────────────────────
    for alloc in voucher.allocations:
        if alloc.booking_id:
            booking = await db.get(Booking, alloc.booking_id)
            if booking:
                amt = Decimal(str(alloc.allocated_in_booking_currency))
                booking.paid_amount = max(Decimal("0.0000"), Decimal(str(booking.paid_amount)) - amt)
                booking.remaining_amount = Decimal(str(booking.remaining_amount)) + amt
                if booking.paid_amount == Decimal("0.0000") and booking.status == BookingStatus.CONFIRMED:
                    booking.status = BookingStatus.PENDING

    # If simple (no allocations) booking link
    if not voucher.allocations and voucher.booking_id:
        booking = await db.get(Booking, voucher.booking_id)
        if booking:
            amt = Decimal(str(voucher.amount))
            booking.paid_amount = max(Decimal("0.0000"), Decimal(str(booking.paid_amount)) - amt)
            booking.remaining_amount = Decimal(str(booking.remaining_amount)) + amt
            if booking.paid_amount == Decimal("0.0000") and booking.status == BookingStatus.CONFIRMED:
                booking.status = BookingStatus.PENDING

    # ─── Find Original JE ───────────────────────────────────────────────
    orig_je_stmt = (select(JournalEntry)
                    .where(JournalEntry.reference_id == voucher.transaction_id)
                    .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account)))
    orig_je_res = await db.execute(orig_je_stmt)
    original_je = orig_je_res.scalar_one_or_none()

    # ─── Generate Mirror Reversal JE ────────────────────────────────────
    rev_je_number = f"{original_je.entry_number}-REV" if original_je else f"JE-VOID-{voucher_id}"

    reversal_lines = []
    if original_je:
        for line in original_je.lines:
            # Swap debit ↔ credit
            reversal_lines.append({
                "account_id": line.account_id,
                "debit": line.credit,
                "credit": line.debit,
                "debit_base": line.credit_base,
                "credit_base": line.debit_base,
            })
    else:
        # Fallback: simple 2-line reversal
        cash_acc = await get_account_by_code(db, f"1101-{voucher.currency}")
        entity_acc = await get_entity_account(
            db, "customer" if voucher.entity_type == EntityType.CUSTOMER else "supplier",
            voucher.entity_id, voucher.currency)
        if voucher.type == TransactionType.PAYMENT_IN:
            reversal_lines = [
                {"account_id": entity_acc.id, "debit": voucher.amount, "credit": Decimal("0.0000")},
                {"account_id": cash_acc.id, "debit": Decimal("0.0000"), "credit": voucher.amount},
            ]
        else:
            reversal_lines = [
                {"account_id": cash_acc.id, "debit": voucher.amount, "credit": Decimal("0.0000")},
                {"account_id": entity_acc.id, "debit": Decimal("0.0000"), "credit": voucher.amount},
            ]

    await create_journal_entry(
        session=db, entry_number=rev_je_number, reference_type="VOID",
        reference_id=voucher.transaction_id, currency=voucher.currency,
        description=f"قيد عكسي لإلغاء سند {voucher.transaction_id} — السبب: {data.void_reason}",
        lines_data=reversal_lines,
    )

    # ─── Mark Voucher as Void ───────────────────────────────────────────
    voucher.is_void = True
    voucher.voided_at = datetime.now(timezone.utc)
    voucher.voided_by_id = current_user.id
    voucher.void_reason = data.void_reason
    voucher.reversal_je_number = rev_je_number

    # Update entity balance
    if voucher.entity_id:
        if voucher.entity_type == EntityType.CUSTOMER:
            cust = await db.get(Customer, voucher.entity_id)
            if cust:
                cust.balance = await get_entity_balance(db, "customer", cust.id)
        elif voucher.entity_type == EntityType.SUPPLIER:
            supp = await db.get(Supplier, voucher.entity_id)
            if supp:
                supp.balance = await get_entity_balance(db, "supplier", supp.id)

    await log_audit_event(db, "UPDATE", "financial_transactions", user=current_user,
        record_id=voucher.id,
        new_data={"is_void": True, "reversal_je": rev_je_number, "void_reason": data.void_reason},
        request=request)
    await db.commit()

    return {
        "message": f"تم إلغاء السند {voucher.transaction_id} بنجاح",
        "transaction_id": voucher.transaction_id,
        "reversal_je": rev_je_number,
        "voided_at": voucher.voided_at.isoformat(),
    }



# ─────────────────────────────────────────────────────────────────────────────
# 5. VOUCHER SEARCH — البحث في السندات المالية
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/search")
async def search_vouchers(
    q: str = Query(..., min_length=1, description="رقم السند (RC-XXXX أو PY-XXXX) أو جزء منه"),
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    البحث في السندات المالية بالرقم المرجعي.
    يدعم: RC- (سندات قبض) و PY- (سندات صرف).
    """
    from sqlalchemy.orm import selectinload as sil
    term = f"%{q.strip()}%"
    stmt = (
        select(FinancialTransaction)
        .where(FinancialTransaction.transaction_id.ilike(term))
        .options(sil(FinancialTransaction.allocations))
        .order_by(desc(FinancialTransaction.transaction_date))
        .limit(20)
    )
    res = await db.execute(stmt)
    txs = res.scalars().all()

    results = []
    for t in txs:
        entity_name = None
        entity_phone = None
        if t.entity_type == EntityType.CUSTOMER:
            c = await db.get(Customer, t.entity_id)
            if c:
                entity_name = c.name
                entity_phone = c.phone_number
        elif t.entity_type == EntityType.SUPPLIER:
            s = await db.get(Supplier, t.entity_id)
            if s:
                entity_name = s.name
                entity_phone = getattr(s, "phone_number", None)

        allocations_data = []
        for alloc in getattr(t, "allocations", []):
            allocations_data.append({
                "booking_id": alloc.booking_id,
                "allocated_amount": float(alloc.allocated_amount),
                "target_currency": alloc.target_currency.value if hasattr(alloc.target_currency, "value") else alloc.target_currency,
                "exchange_rate": float(alloc.exchange_rate),
                "allocated_in_booking_currency": float(alloc.allocated_in_booking_currency),
            })

        results.append({
            "id": t.id,
            "transaction_id": t.transaction_id,
            "type": t.type.value if hasattr(t.type, "value") else t.type,
            "entity_type": t.entity_type.value if hasattr(t.entity_type, "value") else t.entity_type,
            "entity_id": t.entity_id,
            "entity_name": entity_name,
            "entity_phone": entity_phone,
            "amount": float(t.amount),
            "currency": t.currency,
            "payment_method": t.payment_method.value if hasattr(t.payment_method, "value") else t.payment_method,
            "notes": t.notes,
            "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
            "is_void": getattr(t, "is_void", False),
            "void_reason": getattr(t, "void_reason", None),
            "shift_id": t.shift_id,
            "allocations": allocations_data,
        })

    return {"items": results, "total": len(results)}


@router.get("/voucher/{voucher_id}/print")
async def print_voucher(
    voucher_id: int,
    mode: str = Query("thermal", enum=["thermal", "a4"]),
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """طباعة سند مالي (قبض/صرف) بصيغة HTML."""
    from sqlalchemy.orm import selectinload as sil
    from fastapi.responses import HTMLResponse

    stmt = (
        select(FinancialTransaction)
        .where(FinancialTransaction.id == voucher_id)
        .options(sil(FinancialTransaction.allocations))
    )
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="السند غير موجود")

    entity_name = None
    entity_phone = None
    if tx.entity_type == EntityType.CUSTOMER:
        c = await db.get(Customer, tx.entity_id)
        if c:
            entity_name = c.name
            entity_phone = c.phone_number
    elif tx.entity_type == EntityType.SUPPLIER:
        s = await db.get(Supplier, tx.entity_id)
        if s:
            entity_name = s.name
            entity_phone = getattr(s, "phone_number", None)

    settings_res = await db.execute(select(Settings).limit(1))
    office_settings = settings_res.scalar_one_or_none()

    allocations_data = [
        {
            "booking_id": alloc.booking_id,
            "allocated_amount": float(alloc.allocated_amount),
            "target_currency": alloc.target_currency.value if hasattr(alloc.target_currency, "value") else alloc.target_currency,
            "exchange_rate": float(alloc.exchange_rate),
            "allocated_in_booking_currency": float(alloc.allocated_in_booking_currency),
        }
        for alloc in getattr(tx, "allocations", [])
    ]

    from app.services.print_service import generate_financial_voucher_html
    html = generate_financial_voucher_html(
        voucher=tx,
        entity_name=entity_name or "---",
        entity_phone=entity_phone,
        office_settings=office_settings,
        allocations=allocations_data,
        issued_by_name=current_user.full_name,
        mode=mode,
    )
    return HTMLResponse(content=html)


# ─────────────────────────────────────────────────────────────────────────────
# 6. EXISTING ENDPOINTS (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/transactions")
async def list_transactions(
    tx_type: Optional[TransactionType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FinancialTransaction).order_by(
        desc(FinancialTransaction.transaction_date), desc(FinancialTransaction.id)
    )
    if tx_type:
        stmt = stmt.where(FinancialTransaction.type == tx_type)
    if start_date:
        stmt = stmt.where(FinancialTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(FinancialTransaction.transaction_date <= end_date)
    stmt = stmt.offset(offset).limit(limit)
    res = await db.execute(stmt)
    items = res.scalars().all()
    output = []
    for item in items:
        resp = FinancialTransactionResponse.model_validate(item)
        if item.entity_type == EntityType.CUSTOMER and item.entity_id:
            c = await db.get(Customer, item.entity_id)
            if c:
                resp.entity_name = c.name
        elif item.entity_type == EntityType.SUPPLIER and item.entity_id:
            s = await db.get(Supplier, item.entity_id)
            if s:
                resp.entity_name = s.name
        output.append(resp)
    return output


@router.get("/ledger/customer/{customer_id}")
async def get_customer_ledger(
    customer_id: int,
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ledger_service import get_ledger_statement
    return await get_ledger_statement(db, "customer", customer_id)


@router.get("/ledger/supplier/{supplier_id}")
async def get_supplier_ledger(
    supplier_id: int,
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ledger_service import get_ledger_statement
    return await get_ledger_statement(db, "supplier", supplier_id)

# ─────────────────────────────────────────────────────────────────────────────
# 11. MULTI-CURRENCY LEDGER V3 (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ledger/v3/{entity_type}/{entity_id}")
async def get_ledger_v3(
    entity_type: str,
    entity_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    currency: Optional[str] = None,
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db)
):
    from app.services.ledger_service import get_ledger_statement
    return await get_ledger_statement(db, entity_type, entity_id, from_date, to_date, currency)

@router.get("/ledger/v3/{entity_type}/{entity_id}/export")
async def export_ledger_v3(
    entity_type: str,
    entity_id: int,
    format: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    currency: Optional[str] = None,
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db)
):
    from app.services.ledger_service import get_ledger_statement
    from app.services.export_service import export_ledger_to_excel, export_ledger_to_pdf
    from fastapi.responses import Response
    
    data = await get_ledger_statement(db, entity_type, entity_id, from_date, to_date, currency)
    
    if format.lower() == "excel":
        file_bytes = export_ledger_to_excel(data)
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="ledger-{entity_type}-{entity_id}.xlsx"'}
        )
    elif format.lower() == "pdf":
        file_bytes, is_pdf = export_ledger_to_pdf(data)
        if is_pdf:
            return Response(
                content=file_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="ledger-{entity_type}-{entity_id}.pdf"'}
            )
        else:
            return Response(
                content=file_bytes,
                media_type="text/html; charset=utf-8"
            )
    else:
        raise HTTPException(status_code=400, detail="صيغة التصدير غير مدعومة")
