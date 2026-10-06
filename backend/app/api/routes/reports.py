from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.customer import Customer
from app.models.financial import FinancialTransaction, TransactionType
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.schemas.report import ReportFilter, ReportSummary
from app.services.export_service import export_report_to_excel, export_report_to_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])


async def build_report(filters: ReportFilter, current_user: User, db: AsyncSession) -> ReportSummary:
    # Strict role check:
    # If employee, ONLY bookings_detailed is allowed, and employee_id is FORCED to current_user.id
    if current_user.role == UserRole.EMPLOYEE:
        if filters.report_type != "bookings_detailed":
            raise HTTPException(
                status_code=403,
                detail="الموظف مصرح له فقط بالوصول إلى تقرير الحجوزات التفصيلي الخاص به",
            )
        filters.employee_id = current_user.id  # Enforced on server!

    period_str = f"{filters.start_date or 'البداية'} إلى {filters.end_date or 'اليوم'}"

    # 1. Detailed Bookings Report
    if filters.report_type == "bookings_detailed":
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.customer),
                selectinload(Booking.employee),
                selectinload(Booking.supplier),
            )
            .order_by(Booking.booking_date.desc())
        )
        if filters.employee_id:
            stmt = stmt.where(Booking.employee_id == filters.employee_id)
        if filters.service_type:
            stmt = stmt.where(Booking.type == filters.service_type)
        if filters.start_date:
            stmt = stmt.where(func.date(Booking.booking_date) >= filters.start_date)
        if filters.end_date:
            stmt = stmt.where(func.date(Booking.booking_date) <= filters.end_date)
        if filters.customer_id:
            stmt = stmt.where(Booking.customer_id == filters.customer_id)

        res = await db.execute(stmt)
        bookings = res.scalars().all()

        rows = []
        for b in bookings:
            row = {
                "رقم التذكرة": b.ticket_number,
                "النوع": b.type.value,
                "العميل": b.customer.name if b.customer else "--",
                "الموظف": b.employee.full_name if b.employee else "--",
                "تاريخ الحجز": b.booking_date.strftime("%Y-%m-%d %H:%M") if b.booking_date else "--",
                "سعر البيع": float(b.selling_price),
                "المدفوع": float(b.paid_amount),
                "المتبقي": float(b.remaining_amount),
                "الحالة": b.status.value,
            }
            # Only include cost_price if NOT employee
            if current_user.role != UserRole.EMPLOYEE:
                row["سعر التكلفة"] = float(b.cost_price)
            rows.append(row)

        total_amount = sum(b.selling_price for b in bookings)
        return ReportSummary(
            title="تقرير الحجوزات التفصيلي",
            report_type="bookings_detailed",
            period=period_str,
            total_count=len(bookings),
            total_amount=total_amount,
            rows=rows,
        )

    # 2. Revenue Report
    elif filters.report_type == "revenue":
        stmt = select(Booking)
        if filters.start_date:
            stmt = stmt.where(func.date(Booking.booking_date) >= filters.start_date)
        if filters.end_date:
            stmt = stmt.where(func.date(Booking.booking_date) <= filters.end_date)
        res = await db.execute(stmt)
        bookings = res.scalars().all()

        # Group by service type
        by_type: Dict[str, Dict[str, Any]] = {}
        for b in bookings:
            t = b.type.value
            if t not in by_type:
                by_type[t] = {"count": 0, "sales": Decimal("0.00"), "cost": Decimal("0.00")}
            by_type[t]["count"] += 1
            by_type[t]["sales"] += b.selling_price
            by_type[t]["cost"] += b.cost_price

        rows = []
        for t, data in by_type.items():
            net = data["sales"] - data["cost"]
            rows.append({
                "نوع الخدمة": t,
                "عدد الحجوزات": data["count"],
                "إجمالي المبيعات": float(data["sales"]),
                "إجمالي التكلفة": float(data["cost"]),
                "صافي الإيراد": float(net),
            })

        total_sales = sum(r["إجمالي المبيعات"] for r in rows)
        return ReportSummary(
            title="تقرير الإيرادات",
            report_type="revenue",
            period=period_str,
            total_count=len(bookings),
            total_amount=Decimal(str(total_sales)),
            rows=rows,
        )

    # 3. Expenses Report
    elif filters.report_type == "expenses":
        stmt = select(FinancialTransaction).where(FinancialTransaction.type == TransactionType.EXPENSE)
        if filters.start_date:
            stmt = stmt.where(FinancialTransaction.transaction_date >= filters.start_date)
        if filters.end_date:
            stmt = stmt.where(FinancialTransaction.transaction_date <= filters.end_date)
        if filters.expense_type:
            stmt = stmt.where(FinancialTransaction.expense_type == filters.expense_type)

        res = await db.execute(stmt)
        txs = res.scalars().all()

        rows = [
            {
                "رقم السند": t.transaction_id,
                "النوع": t.expense_type or "مصروف عام",
                "المبلغ": float(t.amount),
                "العملة": t.currency,
                "التاريخ": str(t.transaction_date),
                "ملاحظات": t.notes or "--",
            }
            for t in txs
        ]
        total_amount = sum(t.amount for t in txs)
        return ReportSummary(
            title="تقرير المصروفات",
            report_type="expenses",
            period=period_str,
            total_count=len(txs),
            total_amount=total_amount,
            rows=rows,
        )

    # 4. Profit & Loss Report
    elif filters.report_type == "profit_loss":
        b_stmt = select(Booking)
        if filters.start_date:
            b_stmt = b_stmt.where(func.date(Booking.booking_date) >= filters.start_date)
        if filters.end_date:
            b_stmt = b_stmt.where(func.date(Booking.booking_date) <= filters.end_date)
        b_res = await db.execute(b_stmt)
        bookings = b_res.scalars().all()

        e_stmt = select(FinancialTransaction).where(FinancialTransaction.type == TransactionType.EXPENSE)
        if filters.start_date:
            e_stmt = e_stmt.where(FinancialTransaction.transaction_date >= filters.start_date)
        if filters.end_date:
            e_stmt = e_stmt.where(FinancialTransaction.transaction_date <= filters.end_date)
        e_res = await db.execute(e_stmt)
        expenses = e_res.scalars().all()

        total_sales = sum(b.selling_price for b in bookings)
        total_cost = sum(b.cost_price for b in bookings)
        gross_profit = total_sales - total_cost
        total_exp = sum(e.amount for e in expenses)
        net_profit = gross_profit - total_exp

        rows = [
            {"البند": "إجمالي المبيعات", "المبلغ": float(total_sales)},
            {"البند": "تكلفة الحجوزات", "المبلغ": float(total_cost)},
            {"البند": "إجمالي الربح التشغيلي", "المبلغ": float(gross_profit)},
            {"البند": "المصروفات العمومية", "المبلغ": float(total_exp)},
            {"البند": "صافي الربح / الخسارة", "المبلغ": float(net_profit)},
        ]
        return ReportSummary(
            title="تقرير الأرباح والخسائر",
            report_type="profit_loss",
            period=period_str,
            total_count=len(bookings) + len(expenses),
            total_amount=net_profit,
            rows=rows,
        )

    # 5. Debts Report
    elif filters.report_type == "debts":
        cust_res = await db.execute(select(Customer).where(Customer.balance > 0))
        custs = cust_res.scalars().all()
        supp_res = await db.execute(select(Supplier).where(Supplier.balance != 0))
        supps = supp_res.scalars().all()

        rows = []
        for c in custs:
            rows.append({
                "نوع الحساب": "عميل (مدين للمكتب)",
                "الاسم": c.name,
                "الهاتف": c.phone_number,
                "الرصيد المستحق": float(c.balance),
            })
        for s in supps:
            rows.append({
                "نوع الحساب": "مورد",
                "الاسم": s.name,
                "الهاتف": s.phone_number,
                "الرصيد المستحق": float(s.balance),
            })

        total_debts = sum(c.balance for c in custs)
        return ReportSummary(
            title="تقرير المديونيات والأرصدة",
            report_type="debts",
            period="الرصيد التراكمي اللحظي",
            total_count=len(rows),
            total_amount=total_debts,
            rows=rows,
        )

    # 6. Employee Performance Report
    elif filters.report_type == "employee_performance":
        b_stmt = select(Booking).options(selectinload(Booking.employee))
        if filters.start_date:
            b_stmt = b_stmt.where(func.date(Booking.booking_date) >= filters.start_date)
        if filters.end_date:
            b_stmt = b_stmt.where(func.date(Booking.booking_date) <= filters.end_date)

        b_res = await db.execute(b_stmt)
        bookings = b_res.scalars().all()

        by_emp: Dict[int, Dict[str, Any]] = {}
        for b in bookings:
            emp_id = b.employee_id
            emp_name = b.employee.full_name if b.employee else f"موظف #{emp_id}"
            if emp_id not in by_emp:
                by_emp[emp_id] = {"name": emp_name, "count": 0, "sales": Decimal("0.00")}
            by_emp[emp_id]["count"] += 1
            by_emp[emp_id]["sales"] += b.selling_price

        rows = [
            {
                "اسم الموظف": data["name"],
                "عدد الحجوزات": data["count"],
                "إجمالي المبيعات": float(data["sales"]),
            }
            for data in by_emp.values()
        ]
        total_sales = sum(r["إجمالي المبيعات"] for r in rows)
        return ReportSummary(
            title="تقرير أداء الموظفين",
            report_type="employee_performance",
            period=period_str,
            total_count=len(bookings),
            total_amount=Decimal(str(total_sales)),
            rows=rows,
        )

    # 7. Cash Flow Report
    elif filters.report_type == "cash_flow":
        stmt = select(FinancialTransaction)
        if filters.start_date:
            stmt = stmt.where(FinancialTransaction.transaction_date >= filters.start_date)
        if filters.end_date:
            stmt = stmt.where(FinancialTransaction.transaction_date <= filters.end_date)
        res = await db.execute(stmt)
        txs = res.scalars().all()

        inflow = sum(t.amount for t in txs if t.type == TransactionType.PAYMENT_IN)
        outflow = sum(t.amount for t in txs if t.type in [TransactionType.PAYMENT_OUT, TransactionType.EXPENSE])
        net_cash = inflow - outflow

        rows = [
            {
                "رقم السند": t.transaction_id,
                "النوع": "قبض (مقبوضات)" if t.type == TransactionType.PAYMENT_IN else "صرف / مصروف",
                "المبلغ": float(t.amount),
                "التاريخ": str(t.transaction_date),
                "ملاحظات": t.notes or "--",
            }
            for t in txs
        ]

        return ReportSummary(
            title="تقرير التدفق النقدي",
            report_type="cash_flow",
            period=period_str,
            total_count=len(txs),
            total_amount=net_cash,
            additional_totals={"inflow": float(inflow), "outflow": float(outflow), "net": float(net_cash)},
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
    pdf_bytes = export_report_to_pdf(summary)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{filters.report_type}.pdf"},
    )
