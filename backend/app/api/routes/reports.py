from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user
from app.core.config import format_office_dt, office_date_range_utc, office_today
from app.core.database import get_db
from app.models.accounting import Account, EntityAccountType, JournalEntry, JournalEntryLine
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.cash_shift import CashShift
from app.models.customer import Customer
from app.models.financial import FinancialTransaction, PaymentMethod, TransactionType
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.schemas.report import ReportFilter, ReportSummary
from app.services.accounting_service import get_exchange_rate_to_yer
from app.services.export_service import export_report_to_excel, export_report_to_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])

SERVICE_LABELS = {
    "flight": "طيران (flight)",
    "transport": "نقل بري (transport)",
    "visa": "تأشيرة (visa)",
    "passport": "جوازات (passport)",
    "parcel": "طرود (parcel)",
}

PAYMENT_METHOD_LABELS = {
    "cash": "نقداً",
    "bank_transfer": "تحويل بنكي",
    "check": "شيك مصرفي",
}

STATUS_LABELS = {
    "pending": "معلق (آجل)",
    "confirmed": "مؤكد",
    "completed": "مكتمل",
    "cancelled": "ملغي",
}


async def _get_rates_map(db: AsyncSession) -> Dict[str, Decimal]:
    return {
        "YER": Decimal("1.0000"),
        "SAR": await get_exchange_rate_to_yer(db, "SAR"),
        "USD": await get_exchange_rate_to_yer(db, "USD"),
    }


async def build_report(filters: ReportFilter, current_user: User, db: AsyncSession) -> ReportSummary:
    # Strict role check: Employee is only allowed bookings_detailed for their own bookings
    if current_user.role == UserRole.EMPLOYEE:
        if filters.report_type != "bookings_detailed":
            raise HTTPException(
                status_code=403,
                detail="الموظف مصرح له فقط بالوصول إلى تقرير الحجوزات التفصيلي الخاص به",
            )
        filters.employee_id = current_user.id

    period_str = f"{filters.start_date or 'البداية'} إلى {filters.end_date or 'اليوم'}"
    start_utc, end_utc = office_date_range_utc(filters.start_date, filters.end_date)
    rates_map = await _get_rates_map(db)

    # 1. Detailed Bookings Report
    if filters.report_type == "bookings_detailed":
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.customer),
                selectinload(Booking.employee),
                selectinload(Booking.supplier),
                selectinload(Booking.transport_infants),
            )
            .order_by(Booking.booking_date.desc())
        )
        if filters.employee_id:
            stmt = stmt.where(Booking.employee_id == filters.employee_id)
        if filters.service_type:
            stmt = stmt.where(Booking.type == filters.service_type)
        if start_utc:
            stmt = stmt.where(Booking.booking_date >= start_utc)
        if end_utc:
            stmt = stmt.where(Booking.booking_date <= end_utc)
        if filters.customer_id:
            stmt = stmt.where(Booking.customer_id == filters.customer_id)

        res = await db.execute(stmt)
        bookings = res.scalars().all()

        rows = []
        totals_by_curr: Dict[str, Decimal] = {}
        total_yer_equiv = Decimal("0.00")

        for b in bookings:
            curr = (b.currency or "YER").upper()
            st_val = b.status.value if hasattr(b.status, "value") else str(b.status)
            t_val = b.type.value if hasattr(b.type, "value") else str(b.type)
            row: Dict[str, Any] = {
                "رقم التذكرة": b.ticket_number,
                "النوع": SERVICE_LABELS.get(t_val, t_val),
                "العميل": b.customer.name if b.customer else "--",
                "الموظف": b.employee.full_name if b.employee else "--",
                "تاريخ الحجز": format_office_dt(b.booking_date),
                "العملة": curr,
                "سعر البيع": float(b.selling_price),
                "المدفوع": float(b.paid_amount),
                "المتبقي": float(b.remaining_amount),
                "الحالة": STATUS_LABELS.get(st_val, st_val),
                "الرضّع المرافقون": (
                    f"{len(b.transport_infants)} ({'، '.join(inf.full_name for inf in b.transport_infants)})"
                    if getattr(b, "transport_infants", None)
                    else "لا يوجد"
                ),
            }
            if current_user.role != UserRole.EMPLOYEE:
                row["سعر التكلفة"] = float(b.cost_price)
            rows.append(row)

            if b.status != BookingStatus.CANCELLED:
                totals_by_curr[curr] = totals_by_curr.get(curr, Decimal("0.00")) + Decimal(str(b.selling_price))
                rate = rates_map.get(curr, Decimal("1.0000"))
                total_yer_equiv += (Decimal(str(b.selling_price)) * rate).quantize(Decimal("0.01"))

        return ReportSummary(
            title="تقرير الحجوزات التفصيلي",
            report_type="bookings_detailed",
            period=period_str,
            total_count=len(bookings),
            total_amount=total_yer_equiv,
            totals_by_currency={k: float(v.quantize(Decimal("0.01"))) for k, v in totals_by_curr.items()},
            rows=rows,
        )

    # 2. Revenue Report (Separated by Service Type AND Currency)
    elif filters.report_type == "revenue":
        stmt = select(Booking).where(Booking.status != BookingStatus.CANCELLED)
        if start_utc:
            stmt = stmt.where(Booking.booking_date >= start_utc)
        if end_utc:
            stmt = stmt.where(Booking.booking_date <= end_utc)
        if filters.service_type:
            stmt = stmt.where(Booking.type == filters.service_type)
        res = await db.execute(stmt)
        bookings = res.scalars().all()

        by_type_curr: Dict[tuple[str, str], Dict[str, Any]] = {}
        totals_by_curr: Dict[str, Dict[str, Decimal]] = {}
        total_yer_equiv = Decimal("0.00")

        for b in bookings:
            t_val = b.type.value if hasattr(b.type, "value") else str(b.type)
            curr = (b.currency or "YER").upper()
            key = (t_val, curr)
            if key not in by_type_curr:
                by_type_curr[key] = {"count": 0, "sales": Decimal("0.00"), "cost": Decimal("0.00")}
            by_type_curr[key]["count"] += 1
            by_type_curr[key]["sales"] += Decimal(str(b.selling_price))
            by_type_curr[key]["cost"] += Decimal(str(b.cost_price))

            if curr not in totals_by_curr:
                totals_by_curr[curr] = {"sales": Decimal("0.00"), "cost": Decimal("0.00"), "net": Decimal("0.00")}
            totals_by_curr[curr]["sales"] += Decimal(str(b.selling_price))
            totals_by_curr[curr]["cost"] += Decimal(str(b.cost_price))
            totals_by_curr[curr]["net"] += Decimal(str(b.selling_price)) - Decimal(str(b.cost_price))

            rate = rates_map.get(curr, Decimal("1.0000"))
            total_yer_equiv += (Decimal(str(b.selling_price)) * rate).quantize(Decimal("0.01"))

        rows = []
        for (t_val, curr), data in by_type_curr.items():
            net = data["sales"] - data["cost"]
            rows.append({
                "نوع الخدمة": SERVICE_LABELS.get(t_val, t_val),
                "العملة": curr,
                "عدد الحجوزات": data["count"],
                "إجمالي المبيعات": float(data["sales"].quantize(Decimal("0.01"))),
                "إجمالي التكلفة": float(data["cost"].quantize(Decimal("0.01"))),
                "صافي الإيراد": float(net.quantize(Decimal("0.01"))),
            })

        formatted_curr_totals = {
            c: {
                "sales": float(vals["sales"].quantize(Decimal("0.01"))),
                "cost": float(vals["cost"].quantize(Decimal("0.01"))),
                "net": float(vals["net"].quantize(Decimal("0.01"))),
            }
            for c, vals in totals_by_curr.items()
        }

        return ReportSummary(
            title="تقرير الإيرادات والمبيعات",
            report_type="revenue",
            period=period_str,
            total_count=len(bookings),
            total_amount=total_yer_equiv,
            totals_by_currency=formatted_curr_totals,
            rows=rows,
        )

    # 3. Expenses Report
    elif filters.report_type == "expenses":
        stmt = (
            select(FinancialTransaction)
            .where(
                FinancialTransaction.type == TransactionType.EXPENSE,
                FinancialTransaction.is_void == False,
            )
            .order_by(FinancialTransaction.transaction_date.asc(), FinancialTransaction.id.asc())
        )
        if filters.start_date:
            stmt = stmt.where(FinancialTransaction.transaction_date >= filters.start_date)
        if filters.end_date:
            stmt = stmt.where(FinancialTransaction.transaction_date <= filters.end_date)
        if filters.expense_type:
            stmt = stmt.where(FinancialTransaction.expense_type == filters.expense_type)

        res = await db.execute(stmt)
        txs = res.scalars().all()

        totals_by_curr: Dict[str, Decimal] = {}
        total_yer_equiv = Decimal("0.00")
        rows = []

        for t in txs:
            curr = (t.currency or "YER").upper()
            pm_val = t.payment_method.value if hasattr(t.payment_method, "value") else str(t.payment_method)
            amt = Decimal(str(t.amount))
            totals_by_curr[curr] = totals_by_curr.get(curr, Decimal("0.00")) + amt
            rate = rates_map.get(curr, Decimal("1.0000"))
            total_yer_equiv += (amt * rate).quantize(Decimal("0.01"))

            rows.append({
                "رقم السند": t.transaction_id,
                "النوع": t.expense_type or "مصروف عام",
                "المبلغ": float(amt.quantize(Decimal("0.01"))),
                "العملة": curr,
                "طريقة الدفع": PAYMENT_METHOD_LABELS.get(pm_val, pm_val),
                "التاريخ": str(t.transaction_date),
                "ملاحظات": t.notes or "--",
            })

        return ReportSummary(
            title="تقرير المصروفات",
            report_type="expenses",
            period=period_str,
            total_count=len(txs),
            total_amount=total_yer_equiv,
            totals_by_currency={k: float(v.quantize(Decimal("0.01"))) for k, v in totals_by_curr.items()},
            rows=rows,
        )

    # 4. Profit & Loss Report (Separated per Currency + Base YER Equivalent)
    elif filters.report_type == "profit_loss":
        b_stmt = select(Booking).where(Booking.status != BookingStatus.CANCELLED)
        if start_utc:
            b_stmt = b_stmt.where(Booking.booking_date >= start_utc)
        if end_utc:
            b_stmt = b_stmt.where(Booking.booking_date <= end_utc)
        b_res = await db.execute(b_stmt)
        bookings = b_res.scalars().all()

        e_stmt = select(FinancialTransaction).where(
            FinancialTransaction.type == TransactionType.EXPENSE,
            FinancialTransaction.is_void == False,
        )
        if filters.start_date:
            e_stmt = e_stmt.where(FinancialTransaction.transaction_date >= filters.start_date)
        if filters.end_date:
            e_stmt = e_stmt.where(FinancialTransaction.transaction_date <= filters.end_date)
        e_res = await db.execute(e_stmt)
        expenses = e_res.scalars().all()

        by_curr: Dict[str, Dict[str, Decimal]] = {}
        for curr in ("YER", "SAR", "USD"):
            by_curr[curr] = {
                "sales": Decimal("0.00"),
                "cost": Decimal("0.00"),
                "expenses": Decimal("0.00"),
            }

        for b in bookings:
            c = (b.currency or "YER").upper()
            if c not in by_curr:
                by_curr[c] = {"sales": Decimal("0.00"), "cost": Decimal("0.00"), "expenses": Decimal("0.00")}
            by_curr[c]["sales"] += Decimal(str(b.selling_price))
            by_curr[c]["cost"] += Decimal(str(b.cost_price))

        for e in expenses:
            c = (e.currency or "YER").upper()
            if c not in by_curr:
                by_curr[c] = {"sales": Decimal("0.00"), "cost": Decimal("0.00"), "expenses": Decimal("0.00")}
            by_curr[c]["expenses"] += Decimal(str(e.amount))

        rows = []
        totals_by_curr = {}
        total_net_yer = Decimal("0.00")

        for curr, vals in by_curr.items():
            sales_c = vals["sales"]
            cost_c = vals["cost"]
            exp_c = vals["expenses"]
            if sales_c == 0 and cost_c == 0 and exp_c == 0:
                continue
            gross_c = sales_c - cost_c
            net_c = gross_c - exp_c
            rate = rates_map.get(curr, Decimal("1.0000"))
            total_net_yer += (net_c * rate).quantize(Decimal("0.01"))

            totals_by_curr[curr] = float(net_c.quantize(Decimal("0.01")))
            rows.append({
                "العملة": curr,
                "إجمالي المبيعات": float(sales_c.quantize(Decimal("0.01"))),
                "تكلفة الحجوزات": float(cost_c.quantize(Decimal("0.01"))),
                "إجمالي الربح التشغيلي": float(gross_c.quantize(Decimal("0.01"))),
                "المصروفات العمومية": float(exp_c.quantize(Decimal("0.01"))),
                "صافي الربح / الخسارة": float(net_c.quantize(Decimal("0.01"))),
            })

        return ReportSummary(
            title="تقرير الأرباح والخسائر",
            report_type="profit_loss",
            period=period_str,
            total_count=len(bookings) + len(expenses),
            total_amount=total_net_yer,
            totals_by_currency=totals_by_curr,
            rows=rows,
        )

    # 5. Debts Report (100% Read-Only from General Ledger grouped by Entity & Currency)
    elif filters.report_type == "debts":
        cust_map = {c.id: c for c in (await db.execute(select(Customer))).scalars().all()}
        supp_map = {s.id: s for s in (await db.execute(select(Supplier))).scalars().all()}

        agg_stmt = (
            select(
                Account.entity_type,
                Account.entity_id,
                Account.currency,
                func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.0000")),
                func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.0000")),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
            .where(Account.entity_type.in_([EntityAccountType.CUSTOMER, EntityAccountType.SUPPLIER]))
            .group_by(Account.entity_type, Account.entity_id, Account.currency)
        )
        agg_rows = (await db.execute(agg_stmt)).all()

        rows = []
        totals_by_curr: Dict[str, Decimal] = {}
        total_debts_yer = Decimal("0.00")

        for ent_type, ent_id, curr_enum, sum_debit, sum_credit in agg_rows:
            curr = curr_enum.value if hasattr(curr_enum, "value") else str(curr_enum)
            d_val = Decimal(str(sum_debit))
            c_val = Decimal(str(sum_credit))
            if ent_type == EntityAccountType.CUSTOMER:
                bal = (d_val - c_val).quantize(Decimal("0.01"))
                if bal == Decimal("0.00"):
                    continue
                c_obj = cust_map.get(ent_id)
                if not c_obj:
                    continue
                direction = "مدين للمكتب (عليه)" if bal > 0 else "دائن للمكتب (له رصيد مقدم)"
                rows.append({
                    "نوع الحساب": "عميل",
                    "الاسم": c_obj.name,
                    "الهاتف": c_obj.phone_number,
                    "العملة": curr,
                    "الرصيد": float(abs(bal)),
                    "حالة الرصيد": direction,
                })
                if bal > 0:
                    totals_by_curr[curr] = totals_by_curr.get(curr, Decimal("0.00")) + bal
                    rate = rates_map.get(curr, Decimal("1.0000"))
                    total_debts_yer += (bal * rate).quantize(Decimal("0.01"))
            else:
                bal = (c_val - d_val).quantize(Decimal("0.01"))
                if bal == Decimal("0.00"):
                    continue
                s_obj = supp_map.get(ent_id)
                if not s_obj:
                    continue
                direction = "دائن (مستحق للمورد)" if bal > 0 else "مدين (دفعة مقدمة للمورد)"
                rows.append({
                    "نوع الحساب": "مورد",
                    "الاسم": s_obj.name,
                    "الهاتف": s_obj.phone_number or "--",
                    "العملة": curr,
                    "الرصيد": float(abs(bal)),
                    "حالة الرصيد": direction,
                })

        return ReportSummary(
            title="تقرير المديونيات والأرصدة",
            report_type="debts",
            period="الرصيد التراكمي اللحظي حسب العملة",
            total_count=len(rows),
            total_amount=total_debts_yer,
            totals_by_currency={k: float(v.quantize(Decimal("0.01"))) for k, v in totals_by_curr.items()},
            rows=rows,
        )

    # 6. Employee Performance Report
    elif filters.report_type == "employee_performance":
        b_stmt = (
            select(Booking)
            .where(Booking.status != BookingStatus.CANCELLED)
            .options(selectinload(Booking.employee))
        )
        if start_utc:
            b_stmt = b_stmt.where(Booking.booking_date >= start_utc)
        if end_utc:
            b_stmt = b_stmt.where(Booking.booking_date <= end_utc)

        b_res = await db.execute(b_stmt)
        bookings = b_res.scalars().all()

        by_emp_curr: Dict[tuple[int, str], Dict[str, Any]] = {}
        totals_by_curr: Dict[str, Decimal] = {}
        total_yer_equiv = Decimal("0.00")

        for b in bookings:
            emp_id = b.employee_id
            emp_name = b.employee.full_name if b.employee else f"موظف #{emp_id}"
            curr = (b.currency or "YER").upper()
            key = (emp_id, curr)
            if key not in by_emp_curr:
                by_emp_curr[key] = {"name": emp_name, "currency": curr, "count": 0, "sales": Decimal("0.00")}
            by_emp_curr[key]["count"] += 1
            by_emp_curr[key]["sales"] += Decimal(str(b.selling_price))

            totals_by_curr[curr] = totals_by_curr.get(curr, Decimal("0.00")) + Decimal(str(b.selling_price))
            rate = rates_map.get(curr, Decimal("1.0000"))
            total_yer_equiv += (Decimal(str(b.selling_price)) * rate).quantize(Decimal("0.01"))

        rows = [
            {
                "اسم الموظف": data["name"],
                "العملة": data["currency"],
                "عدد الحجوزات": data["count"],
                "إجمالي المبيعات": float(data["sales"].quantize(Decimal("0.01"))),
            }
            for data in by_emp_curr.values()
        ]

        return ReportSummary(
            title="تقرير أداء الموظفين",
            report_type="employee_performance",
            period=period_str,
            total_count=len(bookings),
            total_amount=total_yer_equiv,
            totals_by_currency={k: float(v.quantize(Decimal("0.01"))) for k, v in totals_by_curr.items()},
            rows=rows,
        )

    # 7. Cash Flow Report (Chronological, Currency + PaymentMethod, Separated Payment Out vs Expense)
    elif filters.report_type == "cash_flow":
        stmt = (
            select(FinancialTransaction)
            .where(FinancialTransaction.is_void == False)
            .order_by(FinancialTransaction.transaction_date.asc(), FinancialTransaction.id.asc())
        )
        if filters.start_date:
            stmt = stmt.where(FinancialTransaction.transaction_date >= filters.start_date)
        if filters.end_date:
            stmt = stmt.where(FinancialTransaction.transaction_date <= filters.end_date)
        res = await db.execute(stmt)
        txs = res.scalars().all()

        by_curr: Dict[str, Dict[str, Decimal]] = {}
        total_net_yer = Decimal("0.00")
        rows = []

        for t in txs:
            curr = (t.currency or "YER").upper()
            if curr not in by_curr:
                by_curr[curr] = {"inflow": Decimal("0.00"), "outflow": Decimal("0.00"), "net": Decimal("0.00")}

            amt = Decimal(str(t.amount))
            if t.type == TransactionType.PAYMENT_IN:
                tx_label = "سند قبض (مقبوضات)"
                by_curr[curr]["inflow"] += amt
                by_curr[curr]["net"] += amt
            elif t.type == TransactionType.PAYMENT_OUT:
                tx_label = "سند صرف (مدفوعات)"
                by_curr[curr]["outflow"] += amt
                by_curr[curr]["net"] -= amt
            else:
                tx_label = f"مصروف تشغيلي ({t.expense_type or 'عام'})"
                by_curr[curr]["outflow"] += amt
                by_curr[curr]["net"] -= amt

            pm_val = t.payment_method.value if hasattr(t.payment_method, "value") else str(t.payment_method)
            rows.append({
                "التاريخ": str(t.transaction_date),
                "رقم السند": t.transaction_id,
                "النوع": tx_label,
                "طريقة الدفع": PAYMENT_METHOD_LABELS.get(pm_val, pm_val),
                "المبلغ": float(amt.quantize(Decimal("0.01"))),
                "العملة": curr,
                "ملاحظات": t.notes or "--",
            })

        formatted_curr = {}
        for c, vals in by_curr.items():
            rate = rates_map.get(c, Decimal("1.0000"))
            total_net_yer += (vals["net"] * rate).quantize(Decimal("0.01"))
            formatted_curr[c] = {
                "inflow": float(vals["inflow"].quantize(Decimal("0.01"))),
                "outflow": float(vals["outflow"].quantize(Decimal("0.01"))),
                "net": float(vals["net"].quantize(Decimal("0.01"))),
            }

        return ReportSummary(
            title="تقرير التدفق النقدي",
            report_type="cash_flow",
            period=period_str,
            total_count=len(txs),
            total_amount=total_net_yer,
            totals_by_currency=formatted_curr,
            additional_totals=formatted_curr,
            rows=rows,
        )

    elif filters.report_type == "daily_reconciliation":
        rec_start = filters.start_date or office_today()
        rec_end = filters.end_date or rec_start
        rec_start_utc, rec_end_utc = office_date_range_utc(rec_start, rec_end)
        rec_period = f"{rec_start.isoformat()} إلى {rec_end.isoformat()}"

        # 1. مطابقة أرصدة القنوات (1101 نقدي مقابل 1102 بنكي/حوالات) من قيود اليومية
        je_stmt = (
            select(
                Account.code,
                Account.name,
                func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.0000")),
                func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.0000")),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .where(
                Account.code.like("1101-%") | Account.code.like("1102-%"),
                JournalEntry.date >= rec_start_utc,
                JournalEntry.date <= rec_end_utc,
            )
            .group_by(Account.code, Account.name)
            .order_by(Account.code)
        )
        je_rows = (await db.execute(je_stmt)).all()

        # الأرصدة التراكمية الختامية حتى نهاية الفترة
        closing_stmt = (
            select(
                Account.code,
                func.coalesce(func.sum(JournalEntryLine.debit), Decimal("0.0000"))
                - func.coalesce(func.sum(JournalEntryLine.credit), Decimal("0.0000")),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .where(
                Account.code.like("1101-%") | Account.code.like("1102-%"),
                JournalEntry.date <= rec_end_utc,
            )
            .group_by(Account.code)
        )
        closing_map = {code: Decimal(str(bal or 0)) for code, bal in (await db.execute(closing_stmt)).all()}

        channel_map: Dict[str, Dict[str, Decimal]] = {
            code: {"inflow": Decimal("0"), "outflow": Decimal("0")}
            for code in ("1101-YER", "1101-SAR", "1101-USD", "1102-YER", "1102-SAR", "1102-USD")
        }
        name_map: Dict[str, str] = {
            "1101-YER": "الصندوق الرئيسي - ريال يمني",
            "1101-SAR": "الصندوق الرئيسي - ريال سعودي",
            "1101-USD": "الصندوق الرئيسي - دولار أمريكي",
            "1102-YER": "الحسابات البنكية والحوالات - ريال يمني",
            "1102-SAR": "الحسابات البنكية والحوالات - ريال سعودي",
            "1102-USD": "الحسابات البنكية والحوالات - دولار أمريكي",
        }
        for code, acc_name, deb, cred in je_rows:
            if code in channel_map:
                channel_map[code]["inflow"] = Decimal(str(deb or 0))
                channel_map[code]["outflow"] = Decimal(str(cred or 0))
                name_map[code] = acc_name

        rows: List[Dict[str, Any]] = []
        totals_by_curr: Dict[str, Dict[str, float]] = {}
        total_net_yer = Decimal("0.00")

        for code in ("1101-YER", "1101-SAR", "1101-USD", "1102-YER", "1102-SAR", "1102-USD"):
            prefix, curr = code.split("-")
            inflow = channel_map[code]["inflow"].quantize(Decimal("0.01"))
            outflow = channel_map[code]["outflow"].quantize(Decimal("0.01"))
            net = (inflow - outflow).quantize(Decimal("0.01"))
            closing = closing_map.get(code, Decimal("0")).quantize(Decimal("0.01"))
            channel_label = "صندوق نقدي (1101)" if prefix == "1101" else "بنك / حوالات (1102)"

            if curr not in totals_by_curr:
                totals_by_curr[curr] = {"inflow": 0.0, "outflow": 0.0, "net": 0.0}
            totals_by_curr[curr]["inflow"] = round(totals_by_curr[curr]["inflow"] + float(inflow), 2)
            totals_by_curr[curr]["outflow"] = round(totals_by_curr[curr]["outflow"] + float(outflow), 2)
            totals_by_curr[curr]["net"] = round(totals_by_curr[curr]["net"] + float(net), 2)

            rate = rates_map.get(curr, Decimal("1.0000"))
            total_net_yer += (net * rate).quantize(Decimal("0.01"))

            rows.append({
                "النوع": "قناة مالية",
                "القناة / المرجع": f"{code} — {channel_label}",
                "البيان": name_map[code],
                "العملة": curr,
                "الوارد": float(inflow),
                "الصادر": float(outflow),
                "الصافي": float(net),
                "الرصيد الختامي": float(closing),
            })

        # 2. ملخص الورديات النقدية في الفترة
        shifts_stmt = (
            select(CashShift)
            .where(CashShift.opened_at >= rec_start_utc, CashShift.opened_at <= rec_end_utc)
            .order_by(CashShift.opened_at.desc())
        )
        shifts = (await db.execute(shifts_stmt)).scalars().all()
        for sh in shifts:
            status_ar = "مفتوحة" if sh.status.value == "open" else "مغلقة"
            diff_yer = float(Decimal(str(sh.difference or 0)).quantize(Decimal("0.01"))) if sh.difference is not None else 0.0
            rows.append({
                "النوع": "وردية نقدية",
                "القناة / المرجع": sh.shift_number,
                "البيان": f"حالة الوردية: {status_ar}",
                "العملة": "YER",
                "الوارد": float(Decimal(str(sh.starting_balance or 0)).quantize(Decimal("0.01"))),
                "الصادر": float(Decimal(str(sh.ending_balance_actual or 0)).quantize(Decimal("0.01"))) if sh.ending_balance_actual is not None else 0.0,
                "الصافي": diff_yer,
                "الرصيد الختامي": float(Decimal(str(sh.ending_balance_system or 0)).quantize(Decimal("0.01"))) if sh.ending_balance_system is not None else 0.0,
            })

        return ReportSummary(
            title="تقرير المطابقة اليومية (القنوات والورديات)",
            report_type="daily_reconciliation",
            period=rec_period,
            total_count=len(rows),
            total_amount=total_net_yer,
            totals_by_currency=totals_by_curr,
            additional_totals={"shifts_count": len(shifts), "channels": totals_by_curr},
            rows=rows,
        )

    else:
        raise HTTPException(status_code=400, detail="نوع التقرير غير مدعوم")


@router.post("/generate", response_model=ReportSummary)
async def generate_report(
    filters: ReportFilter,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_report(filters, current_user, db)


@router.post("/export/excel")
async def export_excel(
    filters: ReportFilter,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await build_report(filters, current_user, db)
    excel_bytes = export_report_to_excel(summary)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=report-{filters.report_type}.xlsx"},
    )


@router.post("/export/pdf")
async def export_pdf(
    filters: ReportFilter,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await build_report(filters, current_user, db)
    pdf_bytes, is_pdf = export_report_to_pdf(summary)

    if is_pdf:
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report-{filters.report_type}.pdf"},
        )
    else:
        return Response(
            content=pdf_bytes,
            media_type="text/html; charset=utf-8",
        )
