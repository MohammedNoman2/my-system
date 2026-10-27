from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.booking import Booking, BookingStatus
from app.models.booking_details.flight import FlightBookingDetail
from app.models.booking_details.passport import PassportBookingDetail
from app.models.booking_details.visa import VisaBookingDetail
from app.models.customer import Customer
from app.models.financial import FinancialTransaction, TransactionType
from app.models.supplier import Supplier
from app.models.user import User, UserRole

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    # Base query for bookings depending on role
    bookings_q = select(Booking)
    if current_user.role == UserRole.EMPLOYEE:
        bookings_q = bookings_q.where(Booking.employee_id == current_user.id)

    res = await db.execute(bookings_q)
    all_bookings = [b for b in res.scalars().all() if b.status != BookingStatus.CANCELLED]

    total_bookings_count = len(all_bookings)
    today_bookings = [
        b for b in all_bookings 
        if b.booking_date and (b.booking_date.date() if hasattr(b.booking_date, 'date') else b.booking_date) == today
    ]
    month_bookings = [
        b for b in all_bookings 
        if b.booking_date and (b.booking_date.date() if hasattr(b.booking_date, 'date') else b.booking_date) >= start_of_month
    ]

    # For employee, do not compute or expose cost/profit
    if current_user.role == UserRole.EMPLOYEE:
        return {
            "role": "employee",
            "today_bookings_count": len(today_bookings),
            "month_bookings_count": len(month_bookings),
            "total_bookings_count": total_bookings_count,
            "today_sales": sum(b.selling_price for b in today_bookings),
            "month_sales": sum(b.selling_price for b in month_bookings),
        }

    # For Admin and Accountant: compute revenue, expenses, and profits
    total_sales = sum(b.selling_price for b in all_bookings)
    total_cost = sum(b.cost_price for b in all_bookings)
    gross_profit = total_sales - total_cost

    # Expenses query (exclude voided expenses)
    exp_res = await db.execute(
        select(func.sum(FinancialTransaction.amount)).where(
            FinancialTransaction.type == TransactionType.EXPENSE,
            FinancialTransaction.is_void == False,
        )
    )
    total_expenses = exp_res.scalar() or Decimal("0.00")
    net_profit = gross_profit - total_expenses

    # Counts
    cust_cnt = (await db.execute(select(func.count(Customer.id)))).scalar() or 0
    supp_cnt = (await db.execute(select(func.count(Supplier.id)))).scalar() or 0

    return {
        "role": current_user.role.value,
        "today_bookings_count": len(today_bookings),
        "month_bookings_count": len(month_bookings),
        "total_bookings_count": total_bookings_count,
        "total_sales": total_sales,
        "total_cost": total_cost,
        "gross_profit": gross_profit,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "customers_count": cust_cnt,
        "suppliers_count": supp_cnt,
    }


@router.get("/alerts")
async def get_dashboard_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    alerts = []
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    three_months_ahead = today + timedelta(days=90)

    # 1. Debts > 30 days
    if current_user.role in [UserRole.ADMIN, UserRole.ACCOUNTANT]:
        cust_stmt = select(Customer).where(
            Customer.balance > 0,
            Customer.updated_at <= thirty_days_ago
        ).limit(10)
        cust_res = await db.execute(cust_stmt)
        old_debts = cust_res.scalars().all()
        for c in old_debts:
            alerts.append({
                "type": "debt",
                "severity": "high",
                "title": f"مديونية مستحقة منذ أكثر من 30 يوماً: {c.name}",
                "description": f"المبلغ المستحق: {c.balance} - هاتف: {c.phone_number}",
                "entity_id": c.id,
            })

    # 2. Passports expiring or pending delivery within 3 months
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
