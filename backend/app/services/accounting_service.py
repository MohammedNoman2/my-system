from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.config import office_today
from app.models.accounting import (
    Account,
    AccountCurrency,
    AccountType,
    EntityAccountType,
    JournalEntry,
    JournalEntryLine,
)
from app.models.exchange_rate import ExchangeRate


class AccountingMismatchException(Exception):
    """Raised when journal entry debit and credit do not balance within tolerance."""
    pass


async def get_accounting_lock_date(session: AsyncSession) -> Optional[date]:
    """يعيد تاريخ قفل الفترة المحاسبية من جدول الإعدادات، أو None إن لم يُحدَّد."""
    from app.models.settings import Settings
    res = await session.execute(select(Settings).limit(1))
    s = res.scalar_one_or_none()
    if s and s.accounting_lock_date:
        return s.accounting_lock_date
    return None


async def assert_period_open(session: AsyncSession, target_date: Optional[date] = None) -> None:
    """يرفض ترحيل أو عكس أي حركة محاسبية بتاريخ يقع ضمن الفترة المقفلة."""
    lock_date = await get_accounting_lock_date(session)
    if not lock_date:
        return
    effective_date = target_date or office_today()
    if effective_date <= lock_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"الفترة المحاسبية مغلقة حتى تاريخ {lock_date.isoformat()}؛ "
                f"لا يمكن ترحيل أو تعديل قيود بتاريخ {effective_date.isoformat()}."
            ),
        )


# Default Core System Accounts
DEFAULT_ACCOUNTS = [
    # Cash Accounts (ASSET)
    {"code": "1101-YER", "name": "الصندوق الرئيسي - ريال يمني", "type": AccountType.ASSET, "curr": AccountCurrency.YER},
    {"code": "1101-SAR", "name": "الصندوق الرئيسي - ريال سعودي", "type": AccountType.ASSET, "curr": AccountCurrency.SAR},
    {"code": "1101-USD", "name": "الصندوق الرئيسي - دولار أمريكي", "type": AccountType.ASSET, "curr": AccountCurrency.USD},

    # Bank & Exchange Transfer Accounts (ASSET)
    {"code": "1102-YER", "name": "الحسابات البنكية والحوالات - ريال يمني", "type": AccountType.ASSET, "curr": AccountCurrency.YER},
    {"code": "1102-SAR", "name": "الحسابات البنكية والحوالات - ريال سعودي", "type": AccountType.ASSET, "curr": AccountCurrency.SAR},
    {"code": "1102-USD", "name": "الحسابات البنكية والحوالات - دولار أمريكي", "type": AccountType.ASSET, "curr": AccountCurrency.USD},

    # Revenue Accounts (REVENUE)
    {"code": "4101-YER", "name": "إيرادات مبيعات الحجوزات - ريال يمني", "type": AccountType.REVENUE, "curr": AccountCurrency.YER},
    {"code": "4101-SAR", "name": "إيرادات مبيعات الحجوزات - ريال سعودي", "type": AccountType.REVENUE, "curr": AccountCurrency.SAR},
    {"code": "4101-USD", "name": "إيرادات مبيعات الحجوزات - دولار أمريكي", "type": AccountType.REVENUE, "curr": AccountCurrency.USD},

    {"code": "4201-YER", "name": "إيرادات رسوم الإلغاء - ريال يمني", "type": AccountType.REVENUE, "curr": AccountCurrency.YER},
    {"code": "4201-SAR", "name": "إيرادات رسوم الإلغاء - ريال سعودي", "type": AccountType.REVENUE, "curr": AccountCurrency.SAR},
    {"code": "4201-USD", "name": "إيرادات رسوم الإلغاء - دولار أمريكي", "type": AccountType.REVENUE, "curr": AccountCurrency.USD},

    # Cost of Sales Accounts (EXPENSE)
    {"code": "5101-YER", "name": "تكلفة مبيعات الحجوزات - ريال يمني", "type": AccountType.EXPENSE, "curr": AccountCurrency.YER},
    {"code": "5101-SAR", "name": "تكلفة مبيعات الحجوزات - ريال سعودي", "type": AccountType.EXPENSE, "curr": AccountCurrency.SAR},
    {"code": "5101-USD", "name": "تكلفة مبيعات الحجوزات - دولار أمريكي", "type": AccountType.EXPENSE, "curr": AccountCurrency.USD},

    # Operating Expense Accounts (EXPENSE)
    {"code": "5201-YER", "name": "المصروفات التشغيلية - ريال يمني", "type": AccountType.EXPENSE, "curr": AccountCurrency.YER},
    {"code": "5201-SAR", "name": "المصروفات التشغيلية - ريال سعودي", "type": AccountType.EXPENSE, "curr": AccountCurrency.SAR},
    {"code": "5201-USD", "name": "المصروفات التشغيلية - دولار أمريكي", "type": AccountType.EXPENSE, "curr": AccountCurrency.USD},

    # Equity / Retained Earnings Account (EQUITY)
    {"code": "3101-YER", "name": "الأرباح المبقاة / رأس المال الافتتاحي - ريال يمني", "type": AccountType.EQUITY, "curr": AccountCurrency.YER},

    # Rounding / FX Differences (EXPENSE)
    {"code": "5901-YER", "name": "فروقات تقريب العملات (Rounding Differences)", "type": AccountType.EXPENSE, "curr": AccountCurrency.YER},
    {"code": "5901-SAR", "name": "فروقات تقريب العملات - ريال سعودي", "type": AccountType.EXPENSE, "curr": AccountCurrency.SAR},
    {"code": "5901-USD", "name": "فروقات تقريب العملات - دولار أمريكي", "type": AccountType.EXPENSE, "curr": AccountCurrency.USD},
    # FX Gain Accounts (REVENUE)
    {"code": "4901-YER", "name": "أرباح فروق الصرف - ريال يمني", "type": AccountType.REVENUE, "curr": AccountCurrency.YER},
    {"code": "4901-SAR", "name": "أرباح فروق الصرف - ريال سعودي", "type": AccountType.REVENUE, "curr": AccountCurrency.SAR},
    {"code": "4901-USD", "name": "أرباح فروق الصرف - دولار أمريكي", "type": AccountType.REVENUE, "curr": AccountCurrency.USD},
]


async def init_chart_of_accounts(session: AsyncSession) -> None:
    """Initialize system core accounts if not present."""
    for acc_def in DEFAULT_ACCOUNTS:
        stmt = select(Account).where(Account.code == acc_def["code"])
        res = await session.execute(stmt)
        if not res.scalar_one_or_none():
            acc = Account(
                code=acc_def["code"],
                name=acc_def["name"],
                account_type=acc_def["type"],
                currency=acc_def["curr"],
                entity_type=EntityAccountType.NONE,
                entity_id=None,
            )
            session.add(acc)
    await session.flush()


async def get_exchange_rate_to_yer(session: AsyncSession, currency: str) -> Decimal:
    """Fetch active exchange rate from given currency to base currency (YER)."""
    if currency == "YER":
        return Decimal("1.000000")
    
    stmt = (
        select(ExchangeRate.rate)
        .where(ExchangeRate.from_currency == currency, ExchangeRate.to_currency == "YER")
        .order_by(ExchangeRate.updated_at.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    rate = res.scalar_one_or_none()
    if rate:
        return Decimal(str(rate))
    
    # Fallback to standard rates if not configured in DB
    fallbacks = {
        "USD": Decimal("530.000000"),
        "SAR": Decimal("140.000000"),
    }
    return fallbacks.get(currency, Decimal("1.000000"))


async def create_entity_accounts(
    session: AsyncSession,
    entity_type: str,  # 'customer' or 'supplier'
    entity_id: int,
    entity_name: str,
) -> List[Account]:
    """
    Creates sub-accounts for Customer (AR) or Supplier (AP) across all 3 currencies.
    Pattern: {parent_code}-{entity_type[:4].upper()}-{entity_id}-{currency}
    Example: 1201-CUST-15-SAR
    """
    ent_type_enum = (
        EntityAccountType.CUSTOMER if entity_type.lower() == "customer" else EntityAccountType.SUPPLIER
    )
    parent_code = "1201" if ent_type_enum == EntityAccountType.CUSTOMER else "2101"
    acc_type = AccountType.ASSET if ent_type_enum == EntityAccountType.CUSTOMER else AccountType.LIABILITY
    role_ar = "العميل" if ent_type_enum == EntityAccountType.CUSTOMER else "المورد"
    prefix = "CUST" if ent_type_enum == EntityAccountType.CUSTOMER else "SUPP"

    created_accounts = []
    for curr in [AccountCurrency.YER, AccountCurrency.SAR, AccountCurrency.USD]:
        code = f"{parent_code}-{prefix}-{entity_id}-{curr.value}"
        stmt = select(Account).where(Account.code == code)
        res = await session.execute(stmt)
        acc = res.scalar_one_or_none()
        if not acc:
            acc = Account(
                code=code,
                name=f"حساب {role_ar}: {entity_name} ({curr.value})",
                account_type=acc_type,
                currency=curr,
                entity_type=ent_type_enum,
                entity_id=entity_id,
            )
            session.add(acc)
            created_accounts.append(acc)
    await session.flush()
    return created_accounts


async def get_entity_account(
    session: AsyncSession,
    entity_type: str,
    entity_id: int,
    currency: str,
    entity_name: str = "",
) -> Account:
    """Fetch entity account for currency, provisioning on-the-fly if missing."""
    ent_type_enum = (
        EntityAccountType.CUSTOMER if entity_type.lower() == "customer" else EntityAccountType.SUPPLIER
    )
    parent_code = "1201" if ent_type_enum == EntityAccountType.CUSTOMER else "2101"
    prefix = "CUST" if ent_type_enum == EntityAccountType.CUSTOMER else "SUPP"
    code = f"{parent_code}-{prefix}-{entity_id}-{currency}"

    stmt = select(Account).where(Account.code == code)
    res = await session.execute(stmt)
    acc = res.scalar_one_or_none()
    if not acc:
        accounts = await create_entity_accounts(session, entity_type, entity_id, entity_name or f"Entity #{entity_id}")
        for a in accounts:
            if a.currency.value == currency:
                return a
        # Refetch
        stmt = select(Account).where(Account.code == code)
        res = await session.execute(stmt)
        acc = res.scalar_one_or_none()
    return acc


async def get_account_by_code(session: AsyncSession, code: str) -> Account:
    """Fetch account by code, ensuring chart of accounts is initialized if missing."""
    stmt = select(Account).where(Account.code == code)
    res = await session.execute(stmt)
    acc = res.scalar_one_or_none()
    if not acc:
        await init_chart_of_accounts(session)
        res = await session.execute(stmt)
        acc = res.scalar_one_or_none()
        if not acc:
            raise ValueError(f"الحساب برمز {code} غير معرف في دليل الحسابات")
    return acc


async def get_payment_channel_account(
    session: AsyncSession, payment_method: Any, currency: str
) -> Account:
    """
    يرجع حساب الخزينة المناسب حسب قناة الدفع:
    - cash -> الصندوق النقدي 1101-{CURR}
    - bank_transfer / check -> الحسابات البنكية والحوالات 1102-{CURR}
    (القيود التاريخية المرحلة سابقاً على 1101 تبقى كما هي دون مساس).
    """
    pm_val = payment_method.value if hasattr(payment_method, "value") else str(payment_method or "cash")
    prefix = "1101" if pm_val.lower() == "cash" else "1102"
    curr_u = (currency or "YER").upper()
    return await get_account_by_code(session, f"{prefix}-{curr_u}")


async def create_journal_entry(
    session: AsyncSession,
    entry_number: str,
    reference_type: str,
    reference_id: str,
    currency: str,
    description: str,
    lines_data: List[Dict[str, Any]],
    entry_date: Optional[date] = None,
) -> JournalEntry:
    """
    Creates an immutable, balanced Double-Entry Journal Entry.
    Enforces Mandatory Directive 2:
    - Auto-balances rounding differences if |sum(debit_base) - sum(credit_base)| <= 0.05 to 5901-YER.
    - Rejects with AccountingMismatchException if imbalance > 0.05.
    - Enforces Period Lock: rejects if entry_date falls within a locked period.
    """
    await assert_period_open(session, entry_date or office_today())
    curr_enum = AccountCurrency(currency)
    rate = await get_exchange_rate_to_yer(session, currency)

    entry = JournalEntry(
        entry_number=entry_number,
        reference_type=reference_type,
        reference_id=reference_id,
        currency=curr_enum,
        exchange_rate=rate,
        description=description,
        is_posted=True,
    )
    session.add(entry)
    await session.flush()

    total_debit_base = Decimal("0.0000")
    total_credit_base = Decimal("0.0000")
    entry_lines: List[JournalEntryLine] = []

    for item in lines_data:
        debit = Decimal(str(item.get("debit", 0))).quantize(Decimal("0.0001"))
        credit = Decimal(str(item.get("credit", 0))).quantize(Decimal("0.0001"))

        # Skip zero lines if any
        if debit == 0 and credit == 0:
            continue

        debit_base = Decimal(str(item.get("debit_base", debit * rate))).quantize(Decimal("0.0001"))
        credit_base = Decimal(str(item.get("credit_base", credit * rate))).quantize(Decimal("0.0001"))

        total_debit_base += debit_base
        total_credit_base += credit_base

        line = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=item["account_id"],
            debit=debit,
            credit=credit,
            debit_base=debit_base,
            credit_base=credit_base,
        )
        session.add(line)
        entry_lines.append(line)

    # Check Base Currency Balancing
    diff = (total_debit_base - total_credit_base).quantize(Decimal("0.0001"))
    tolerance = Decimal("0.0500")

    if abs(diff) > Decimal("0.0000"):
        if abs(diff) <= tolerance:
            # Auto-balance rounding difference to account 5901-YER (Directive 2)
            rounding_acc = await get_account_by_code(session, "5901-YER")
            rounding_local = (abs(diff) / rate).quantize(Decimal("0.0001"))
            if diff > 0:
                # Debits exceed Credits -> add credit to rounding account
                r_line = JournalEntryLine(
                    journal_entry_id=entry.id,
                    account_id=rounding_acc.id,
                    debit=Decimal("0.0000"),
                    credit=rounding_local,
                    debit_base=Decimal("0.0000"),
                    credit_base=abs(diff),
                )
            else:
                # Credits exceed Debits -> add debit to rounding account
                r_line = JournalEntryLine(
                    journal_entry_id=entry.id,
                    account_id=rounding_acc.id,
                    debit=rounding_local,
                    credit=Decimal("0.0000"),
                    debit_base=abs(diff),
                    credit_base=Decimal("0.0000"),
                )
            session.add(r_line)
            entry_lines.append(r_line)
        else:
            raise AccountingMismatchException(
                f"فشل توازن قيد اليومية {entry_number}: إجمالي المدين الأساسي ({total_debit_base}) لا يطابق إجمالي الدائن الأساسي ({total_credit_base}) بفارق يتجاوز حد التقريب ({diff} YER)"
            )

    await session.flush()
    return entry


async def get_entity_balance(
    session: AsyncSession,
    entity_type: str,
    entity_id: int,
    currency: Optional[str] = None,
) -> Decimal:
    """
    Calculates dynamic entity balance from the immutable General Ledger.
    - When `currency` is specified: returns balance in that exact currency (sum(debit) vs sum(credit)).
    - When `currency` is None: returns unified base-currency (YER) balance across all sub-accounts
      using debit_base / credit_base (falling back to debit / credit if base is 0).
    For Customer (AR): Debit - Credit
    For Supplier (AP): Credit - Debit
    """
    ent_type_enum = (
        EntityAccountType.CUSTOMER if entity_type.lower() == "customer" else EntityAccountType.SUPPLIER
    )

    if currency:
        stmt = (
            select(
                func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.0000")),
                func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.0000")),
            )
            .join(Account, JournalEntryLine.account_id == Account.id)
            .where(
                Account.entity_type == ent_type_enum,
                Account.entity_id == entity_id,
                Account.currency == AccountCurrency(currency),
            )
        )
    else:
        debit_expr = case(
            (JournalEntryLine.debit_base > 0, JournalEntryLine.debit_base),
            else_=JournalEntryLine.debit,
        )
        credit_expr = case(
            (JournalEntryLine.credit_base > 0, JournalEntryLine.credit_base),
            else_=JournalEntryLine.credit,
        )
        stmt = (
            select(
                func.coalesce(func.sum(debit_expr), Decimal("0.0000")),
                func.coalesce(func.sum(credit_expr), Decimal("0.0000")),
            )
            .join(Account, JournalEntryLine.account_id == Account.id)
            .where(
                Account.entity_type == ent_type_enum,
                Account.entity_id == entity_id,
            )
        )

    res = await session.execute(stmt)
    total_debit, total_credit = res.one()

    if ent_type_enum == EntityAccountType.CUSTOMER:
        return (Decimal(str(total_debit)) - Decimal(str(total_credit))).quantize(Decimal("0.01"))
    else:
        return (Decimal(str(total_credit)) - Decimal(str(total_debit))).quantize(Decimal("0.01"))


async def sync_all_entity_balances(session: AsyncSession) -> dict:
    """
    Recalculates and synchronizes `customer.balance` and `supplier.balance`
    for all records in the database from the immutable General Ledger.
    """
    from app.models.customer import Customer
    from app.models.supplier import Supplier

    cust_res = await session.execute(select(Customer))
    customers = cust_res.scalars().all()
    for c in customers:
        c.balance = await get_entity_balance(session, "customer", c.id)

    supp_res = await session.execute(select(Supplier))
    suppliers = supp_res.scalars().all()
    for s in suppliers:
        s.balance = await get_entity_balance(session, "supplier", s.id)

    await session.flush()
    return {"customers_synced": len(customers), "suppliers_synced": len(suppliers)}



async def get_cash_balance_with_lock(
    session: AsyncSession,
    currency: str,
) -> Decimal:
    """
    Returns current cash (1101-{currency}) balance with pessimistic row-level lock.
    Used by payment-voucher to prevent negative balances under concurrency.
    """
    from sqlalchemy import text
    cash_code = f"1101-{currency}"
    # Lock the account row
    acc_stmt = select(Account).where(Account.code == cash_code).with_for_update()
    res = await session.execute(acc_stmt)
    acc = res.scalar_one_or_none()
    if not acc:
        await init_chart_of_accounts(session)
        res = await session.execute(acc_stmt)
        acc = res.scalar_one_or_none()
    if not acc:
        return Decimal("0.0000")

    # Sum all journal lines for this account
    bal_stmt = select(
        func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.0000")),
        func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.0000")),
    ).where(JournalEntryLine.account_id == acc.id)
    bal_res = await session.execute(bal_stmt)
    total_debit, total_credit = bal_res.one()
    # Cash is ASSET: balance = debit - credit
    return (Decimal(str(total_debit)) - Decimal(str(total_credit))).quantize(Decimal("0.0001"))


async def get_customer_available_credit(
    session: AsyncSession,
    customer_id: int,
    currency: str,
) -> Decimal:
    """
    يحسب الرصيد الدائن الفائض (غير المخصص لتذاكر مفتوحة) المتاح للعميل بعملة محددة:
    available_credit = max(0, إجمالي المتبقي على التذاكر المفتوحة بهذه العملة - رصيد الأستاذ العام للعميل بهذه العملة)
    """
    from app.models.booking import Booking, BookingStatus

    curr_upper = (currency or "YER").upper()
    open_stmt = select(
        func.coalesce(func.sum(Booking.remaining_amount), Decimal("0.00"))
    ).where(
        Booking.customer_id == customer_id,
        Booking.currency == curr_upper,
        Booking.status != BookingStatus.CANCELLED,
    )
    open_rem = Decimal(str((await session.execute(open_stmt)).scalar() or Decimal("0.00"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    ledger_bal = await get_entity_balance(session, "customer", customer_id, curr_upper)
    avail = (open_rem - ledger_bal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return avail if avail > Decimal("0.00") else Decimal("0.00")


async def get_customers_credit_balances_map(
    session: AsyncSession,
    customer_ids: List[int],
) -> Dict[int, Dict[str, float]]:
    """
    يحسب الأرصدة الدائنة المتاحة لمجموعة عملاء دفعة واحدة عبر استعلامين مجمعين فقط (منع N+1).
    """
    from app.models.booking import Booking, BookingStatus

    if not customer_ids:
        return {}

    result_map: Dict[int, Dict[str, float]] = {
        cid: {"YER": 0.0, "SAR": 0.0, "USD": 0.0} for cid in customer_ids
    }

    open_stmt = (
        select(
            Booking.customer_id,
            Booking.currency,
            func.coalesce(func.sum(Booking.remaining_amount), Decimal("0.00")),
        )
        .where(
            Booking.customer_id.in_(customer_ids),
            Booking.status != BookingStatus.CANCELLED,
        )
        .group_by(Booking.customer_id, Booking.currency)
    )
    open_rows = (await session.execute(open_stmt)).all()
    open_map: Dict[tuple[int, str], Decimal] = {}
    for cid, curr, rem_sum in open_rows:
        curr_u = (curr or "YER").upper()
        open_map[(cid, curr_u)] = Decimal(str(rem_sum or 0)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    ledger_stmt = (
        select(
            Account.entity_id,
            Account.currency,
            func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.0000")),
            func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.0000")),
        )
        .join(Account, JournalEntryLine.account_id == Account.id)
        .where(
            Account.entity_type == EntityAccountType.CUSTOMER,
            Account.entity_id.in_(customer_ids),
        )
        .group_by(Account.entity_id, Account.currency)
    )
    ledger_rows = (await session.execute(ledger_stmt)).all()
    ledger_map: Dict[tuple[int, str], Decimal] = {}
    for cid, curr_enum, sum_d, sum_c in ledger_rows:
        curr_u = curr_enum.value if hasattr(curr_enum, "value") else str(curr_enum)
        ledger_map[(cid, curr_u)] = (Decimal(str(sum_d)) - Decimal(str(sum_c))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    for cid in customer_ids:
        for curr in ("YER", "SAR", "USD"):
            open_rem = open_map.get((cid, curr), Decimal("0.00"))
            ledger_bal = ledger_map.get((cid, curr), Decimal("0.00"))
            avail = (open_rem - ledger_bal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            result_map[cid][curr] = float(avail) if avail > Decimal("0.00") else 0.0

    return result_map


async def get_customer_all_credit_balances(
    session: AsyncSession,
    customer_id: int,
) -> Dict[str, float]:
    """يرجع الأرصدة الدائنة المتاحة للعميل في العملات الثلاث (YER, SAR, USD)."""
    batch = await get_customers_credit_balances_map(session, [customer_id])
    return batch.get(customer_id, {"YER": 0.0, "SAR": 0.0, "USD": 0.0})


async def backfill_historical_bookings(session: AsyncSession) -> Dict[str, int]:
    """
    يسوّي القيود التاريخية للحجوزات القديمة (التي سُجل فيها صافي المتبقي فقط على حساب العميل)
    عبر إضافة قيد تسوية صفري الأثر (BOOKING_BACKFILL) يثبت مبلغ الدفعة المقدمة (مديناً ودائناً)
    على حساب العميل دون تعديل أو مسح أي سطر قيد مرحّل سابقاً، مع تقريب أرصدة التذاكر إلى خانتين.
    """
    from app.models.booking import Booking
    from app.models.customer import Customer
    from app.models.financial import FinancialTransaction, TransactionType

    stmt = (
        select(JournalEntry)
        .where(JournalEntry.reference_type == "BOOKING")
        .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
    )
    res = await session.execute(stmt)
    booking_jes = res.scalars().all()

    backfilled_count = 0
    for je in booking_jes:
        bf_number = f"JE-BF-{je.reference_id}"
        exists_res = await session.execute(
            select(JournalEntry.id).where(JournalEntry.entry_number == bf_number)
        )
        if exists_res.scalar_one_or_none():
            continue

        # الحجوزات القديمة التي دمجت الدفعة النقدية الأولية مباشرة في قيد الحجز على حساب الصندوق 1101
        cash_lines = [
            l
            for l in je.lines
            if l.account
            and l.account.code.startswith("1101-")
            and Decimal(str(l.debit)) > Decimal("0.0000")
        ]
        if not cash_lines:
            continue

        cash_debit = sum((Decimal(str(l.debit)) for l in cash_lines), Decimal("0.0000")).quantize(
            Decimal("0.0001")
        )
        cash_debit_base = sum(
            (Decimal(str(l.debit_base)) for l in cash_lines), Decimal("0.0000")
        ).quantize(Decimal("0.0001"))
        if cash_debit <= Decimal("0.0000"):
            continue

        b_res = await session.execute(
            select(Booking).where(Booking.ticket_number == je.reference_id)
        )
        booking = b_res.scalar_one_or_none()
        if not booking:
            continue

        cust = await session.get(Customer, booking.customer_id)
        cust_name = cust.name if cust else f"Customer #{booking.customer_id}"
        curr_str = je.currency.value if hasattr(je.currency, "value") else str(je.currency)
        cust_acc = await get_entity_account(
            session, "customer", booking.customer_id, curr_str, cust_name
        )

        rc_res = await session.execute(
            select(FinancialTransaction.transaction_id)
            .where(
                FinancialTransaction.booking_id == booking.id,
                FinancialTransaction.type == TransactionType.PAYMENT_IN,
            )
            .order_by(FinancialTransaction.id.asc())
            .limit(1)
        )
        rc_ref = rc_res.scalar_one_or_none() or je.reference_id

        bf_entry = JournalEntry(
            entry_number=bf_number,
            date=je.date,
            reference_type="BOOKING_BACKFILL",
            reference_id=je.reference_id,
            currency=je.currency,
            exchange_rate=je.exchange_rate,
            description=f"قيد تسوية إثبات كامل قيمة الحجز {je.reference_id} والدفعة المقدمة ({rc_ref})",
            is_posted=True,
        )
        session.add(bf_entry)
        await session.flush()

        session.add_all(
            [
                JournalEntryLine(
                    journal_entry_id=bf_entry.id,
                    account_id=cust_acc.id,
                    debit=cash_debit,
                    credit=Decimal("0.0000"),
                    debit_base=cash_debit_base,
                    credit_base=Decimal("0.0000"),
                ),
                JournalEntryLine(
                    journal_entry_id=bf_entry.id,
                    account_id=cust_acc.id,
                    debit=Decimal("0.0000"),
                    credit=cash_debit,
                    debit_base=Decimal("0.0000"),
                    credit_base=cash_debit_base,
                ),
            ]
        )
        backfilled_count += 1

    all_b_res = await session.execute(select(Booking))
    rounded_bookings = 0
    for b in all_b_res.scalars().all():
        p_2 = Decimal(str(b.paid_amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        r_2 = Decimal(str(b.remaining_amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if b.paid_amount != p_2 or b.remaining_amount != r_2:
            b.paid_amount = p_2
            b.remaining_amount = r_2
            rounded_bookings += 1

    await session.flush()
    return {"backfilled_bookings": backfilled_count, "rounded_bookings": rounded_bookings}
