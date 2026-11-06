from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import office_today, to_office_time
from app.core.database import get_db
from app.models.booking import Booking, BookingStatus
from app.models.booking_details.passport import PassportBookingDetail
from app.models.customer import Customer
from app.models.financial import FinancialTransaction, TransactionType
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.services.accounting_service import get_exchange_rate_to_yer

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

ARABIC_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

SERVICE_AR_NAMES = {
    "flight": "طيران",
    "transport": "نقل بري",
    "visa": "تأشيرات",
    "passport": "جوازات",
    "parcel": "طرود",
}


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = office_today()
    start_of_month = date(today.year, today.month, 1)

    rates_map = {
        "YER": Decimal("1.0000"),
        "SAR": await get_exchange_rate_to_yer(db, "SAR"),
        "USD": await get_exchange_rate_to_yer(db, "USD"),
    }

    bookings_q = select(Booking)
    if current_user.role == UserRole.EMPLOYEE:
        bookings_q = bookings_q.where(Booking.employee_id == current_user.id)

    res = await db.execute(bookings_q)
    all_bookings = [b for b in res.scalars().all() if b.status != BookingStatus.CANCELLED]

    def _b_office_date(b: Booking) -> date:
        if not b.booking_date:
            return today
        if isinstance(b.booking_date, datetime):
            return to_office_time(b.booking_date).date()
        return b.booking_date

    def _to_yer(amount: Decimal, curr: str) -> Decimal:
        r = rates_map.get((curr or "YER").upper(), Decimal("1.0000"))
        return (Decimal(str(amount or 0)) * r).quantize(Decimal("0.01"))

    total_bookings_count = len(all_bookings)
    today_bookings = [b for b in all_bookings if _b_office_date(b) == today]
    month_bookings = [b for b in all_bookings if _b_office_date(b) >= start_of_month]

    # Live services distribution from actual active bookings
    type_counts: Dict[str, int] = {"flight": 0, "transport": 0, "visa": 0, "passport": 0, "parcel": 0}
    for b in all_bookings:
        t_val = b.type.value if hasattr(b.type, "value") else str(b.type)
        if t_val in type_counts:
            type_counts[t_val] += 1

    services_distribution = [
        {"name": SERVICE_AR_NAMES[k], "value": cnt}
        for k, cnt in type_counts.items()
        if cnt > 0
    ]

    # Live monthly series for the last 4 months
    months_keys: List[tuple[int, int]] = []
    y, m = today.year, today.month
    for _ in range(4):
        months_keys.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months_keys.reverse()

    exp_all_res = await db.execute(
        select(FinancialTransaction).where(
            FinancialTransaction.type == TransactionType.EXPENSE,
            FinancialTransaction.is_void == False,
        )
    )
    all_expenses = exp_all_res.scalars().all()

    monthly_series = []
    for yr, mo in months_keys:
        m_sales = sum(
            (_to_yer(b.selling_price, b.currency) for b in all_bookings if _b_office_date(b).year == yr and _b_office_date(b).month == mo),
            Decimal("0.00"),
        )
        m_exp = Decimal("0.00")
        if current_user.role != UserRole.EMPLOYEE:
            m_exp = sum(
                (_to_yer(e.amount, e.currency) for e in all_expenses if e.transaction_date and e.transaction_date.year == yr and e.transaction_date.month == mo),
                Decimal("0.00"),
            )
        monthly_series.append({
            "name": f"{ARABIC_MONTHS[mo]} {yr}",
            "sales": float(m_sales),
            "expenses": float(m_exp),
        })

    today_sales_yer = sum((_to_yer(b.selling_price, b.currency) for b in today_bookings), Decimal("0.00"))
    month_sales_yer = sum((_to_yer(b.selling_price, b.currency) for b in month_bookings), Decimal("0.00"))

    if current_user.role == UserRole.EMPLOYEE:
        return {
            "role": "employee",
            "today_bookings_count": len(today_bookings),
            "month_bookings_count": len(month_bookings),
            "total_bookings_count": total_bookings_count,
            "today_sales": float(today_sales_yer),
            "month_sales": float(month_sales_yer),
            "monthly_series": monthly_series,
            "services_distribution": services_distribution,
        }

    total_sales_yer = sum((_to_yer(b.selling_price, b.currency) for b in all_bookings), Decimal("0.00"))
    total_cost_yer = sum((_to_yer(b.cost_price, b.currency) for b in all_bookings), Decimal("0.00"))
    gross_profit_yer = total_sales_yer - total_cost_yer
    total_expenses_yer = sum((_to_yer(e.amount, e.currency) for e in all_expenses), Decimal("0.00"))
    net_profit_yer = gross_profit_yer - total_expenses_yer

    sales_by_currency: Dict[str, float] = {}
    for b in all_bookings:
        c = (b.currency or "YER").upper()
        sales_by_currency[c] = round(sales_by_currency.get(c, 0.0) + float(b.selling_price), 2)

    cust_cnt = (await db.execute(select(func.count(Customer.id)))).scalar() or 0
    supp_cnt = (await db.execute(select(func.count(Supplier.id)))).scalar() or 0

    return {
        "role": current_user.role.value,
        "today_bookings_count": len(today_bookings),
        "month_bookings_count": len(month_bookings),
        "total_bookings_count": total_bookings_count,
        "today_sales": float(today_sales_yer),
        "month_sales": float(month_sales_yer),
        "total_sales": float(total_sales_yer),
        "total_cost": float(total_cost_yer),
        "gross_profit": float(gross_profit_yer),
        "total_expenses": float(total_expenses_yer),
        "net_profit": float(net_profit_yer),
        "sales_by_currency": sales_by_currency,
        "monthly_series": monthly_series,
        "services_distribution": services_distribution,
        "customers_count": cust_cnt,
        "suppliers_count": supp_cnt,
    }


@router.get("/alerts")
async def get_dashboard_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    alerts = []
    today = office_today()
    thirty_days_ago = today - timedelta(days=30)
    three_months_ahead = today + timedelta(days=90)

    if current_user.role in [UserRole.ADMIN, UserRole.ACCOUNTANT]:
        cust_stmt = select(Customer).where(
            Customer.balance > 0,
            Customer.updated_at <= thirty_days_ago,
        ).limit(10)
        cust_res = await db.execute(cust_stmt)
        old_debts = cust_res.scalars().all()
        for c in old_debts:
            alerts.append({
                "type": "debt",
                "severity": "high",
                "title": f"مديونية مستحقة منذ أكثر من 30 يوماً: {c.name}",
                "description": f"المبلغ المستحق (معادل): {c.balance} YER - هاتف: {c.phone_number}",
                "entity_id": c.id,
            })

    passport_stmt = select(PassportBookingDetail, Booking).join(
        Booking, PassportBookingDetail.booking_id == Booking.id
    )
    if current_user.role == UserRole.EMPLOYEE:
        passport_stmt = passport_stmt.where(Booking.employee_id == current_user.id)

    passport_res = await db.execute(passport_stmt.limit(10))
    for p_detail, b in passport_res.all():
        if p_detail.expected_delivery_date and p_detail.expected_delivery_date <= three_months_ahead:
            alerts.append({
                "type": "passport",
                "severity": "medium",
                "title": f"معاملة جواز مستحقة التسليم: {p_detail.applicant_name}",
                "description": f"تاريخ التسليم: {p_detail.expected_delivery_date} - تذكرة رقم: {b.ticket_number}",
                "entity_id": b.id,
            })

    return alerts
