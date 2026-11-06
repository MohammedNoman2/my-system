import asyncio
import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import format_office_dt, office_date_range_utc
from app.core.database import Base
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.customer import Customer
from app.models.exchange_rate import ExchangeRate
from app.models.financial import EntityType, FinancialTransaction, PaymentMethod, TransactionType
from app.models.user import User, UserRole
from app.schemas.report import ReportFilter
from app.api.routes.reports import build_report
from app.api.routes.dashboard import get_dashboard_summary
from app.services.accounting_service import init_chart_of_accounts, create_entity_accounts


async def run_stage_4b_verification():
    # 1. Verify UTC -> Sana'a (+03:00) formatting and date range conversion
    utc_dt = datetime(2026, 11, 1, 22, 22, 0, tzinfo=timezone.utc)
    assert format_office_dt(utc_dt) == "2026-11-02 01:22", f"Unexpected office dt: {format_office_dt(utc_dt)}"
    start_utc, end_utc = office_date_range_utc(date(2026, 11, 2), date(2026, 11, 2))
    assert start_utc.tzinfo == timezone.utc and end_utc.tzinfo == timezone.utc
    assert start_utc <= utc_dt <= end_utc, "2026-11-01 22:22 UTC must fall inside 2026-11-02 Sana'a day!"

    # 2. Functional test on isolated in-memory DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        await init_chart_of_accounts(db)
        db.add_all([
            ExchangeRate(from_currency="USD", to_currency="YER", rate=Decimal("530.0000")),
            ExchangeRate(from_currency="SAR", to_currency="YER", rate=Decimal("140.0000")),
        ])
        admin = User(username="admin", password_hash="x", full_name="مدير", role=UserRole.ADMIN, is_active=True)
        cust = Customer(name="هشام عبد الوكيل نعمان", phone_number="776522371", balance=Decimal("0.00"))
        db.add_all([admin, cust])
        await db.commit()
        await db.refresh(admin)
        await db.refresh(cust)
        await create_entity_accounts(db, "customer", cust.id, cust.name)

        # Insert 3 bookings at 2026-11-01 22:22 UTC (which is 2026-11-02 01:22 Sana'a time) in USD, SAR, YER
        b_usd = Booking(
            booking_id="FL-0048", ticket_number="FL-0048", type=BookingType.FLIGHT,
            customer_id=cust.id, employee_id=admin.id, booking_date=utc_dt,
            cost_price=Decimal("590.00"), selling_price=Decimal("635.00"),
            paid_amount=Decimal("580.00"), remaining_amount=Decimal("55.00"),
            currency="USD", status=BookingStatus.CONFIRMED,
        )
        b_sar = Booking(
            booking_id="VI-0005", ticket_number="VI-0005", type=BookingType.VISA,
            customer_id=cust.id, employee_id=admin.id, booking_date=utc_dt,
            cost_price=Decimal("520.00"), selling_price=Decimal("600.00"),
            paid_amount=Decimal("500.00"), remaining_amount=Decimal("100.00"),
            currency="SAR", status=BookingStatus.CONFIRMED,
        )
        b_yer = Booking(
            booking_id="TR-0017", ticket_number="TR-0017", type=BookingType.TRANSPORT,
            customer_id=cust.id, employee_id=admin.id, booking_date=utc_dt,
            cost_price=Decimal("25000.00"), selling_price=Decimal("40000.00"),
            paid_amount=Decimal("35000.00"), remaining_amount=Decimal("5000.00"),
            currency="YER", status=BookingStatus.CONFIRMED,
        )
        db.add_all([b_usd, b_sar, b_yer])

        # Insert out-of-order cash flow transactions (2026-11-02 first, then 2026-11-01)
        db.add_all([
            FinancialTransaction(
                transaction_id="RC-0064", type=TransactionType.PAYMENT_IN,
                entity_type=EntityType.CUSTOMER, entity_id=cust.id,
                amount=Decimal("580.00"), currency="USD", payment_method=PaymentMethod.CASH,
                transaction_date=date(2026, 11, 2), created_by=admin.id,
            ),
            FinancialTransaction(
                transaction_id="PY-0022", type=TransactionType.PAYMENT_OUT,
                entity_type=EntityType.SUPPLIER, entity_id=None,
                amount=Decimal("70000.00"), currency="YER", payment_method=PaymentMethod.BANK_TRANSFER,
                transaction_date=date(2026, 11, 1), created_by=admin.id,
            ),
            FinancialTransaction(
                transaction_id="EX-0010", type=TransactionType.EXPENSE,
                entity_type=EntityType.NONE, entity_id=None, expense_type="إيجار",
                amount=Decimal("15000.00"), currency="YER", payment_method=PaymentMethod.CASH,
                transaction_date=date(2026, 11, 1), created_by=admin.id,
            ),
        ])
        await db.commit()

        # Test A: Revenue report for Sana'a date 2026-11-02 finds all 3 bookings (not 0!)
        rev_rep = await build_report(
            ReportFilter(report_type="revenue", start_date=date(2026, 11, 2), end_date=date(2026, 11, 2)),
            admin, db,
        )
        assert rev_rep.total_count == 3, f"Expected 3 bookings on 2026-11-02 Sana'a day, got {rev_rep.total_count}"
        assert rev_rep.totals_by_currency["USD"]["sales"] == 635.0
        assert rev_rep.totals_by_currency["SAR"]["sales"] == 600.0
        assert rev_rep.totals_by_currency["YER"]["sales"] == 40000.0
        # 635*530 + 600*140 + 40000 = 336550 + 84000 + 40000 = 460550 YER (never 41235!)
        assert rev_rep.total_amount == Decimal("460550.00"), f"Unexpected YER equivalent: {rev_rep.total_amount}"

        # Test B: Cash flow report is sorted chronologically, has Currency & Payment Method, and separates Payment Out vs Expense
        cf_rep = await build_report(
            ReportFilter(report_type="cash_flow", start_date=date(2026, 11, 1), end_date=date(2026, 11, 2)),
            admin, db,
        )
        assert len(cf_rep.rows) == 3
        assert cf_rep.rows[0]["التاريخ"] == "2026-11-01" and cf_rep.rows[-1]["التاريخ"] == "2026-11-02", "Cash flow not sorted chronologically!"
        assert "العملة" in cf_rep.rows[0] and "طريقة الدفع" in cf_rep.rows[0]
        types_in_cf = {r["النوع"] for r in cf_rep.rows}
        assert "سند صرف (مدفوعات)" in types_in_cf and any("مصروف تشغيلي" in t for t in types_in_cf)
        assert cf_rep.totals_by_currency["USD"]["inflow"] == 580.0
        assert cf_rep.totals_by_currency["YER"]["outflow"] == 85000.0

        # Test C: Debts report is 100% Read-Only (does NOT mutate Customer.balance)
        cust.balance = Decimal("777.00")
        await db.commit()
        debts_rep_1 = await build_report(ReportFilter(report_type="debts"), admin, db)
        debts_rep_2 = await build_report(ReportFilter(report_type="debts"), admin, db)
        await db.refresh(cust)
        assert cust.balance == Decimal("777.00"), f"Debts report mutated customer.balance to {cust.balance}!"
        assert debts_rep_1.total_count == debts_rep_2.total_count

        # Test D: Dashboard summary returns real monthly_series and services_distribution
        dash = await get_dashboard_summary(admin, db)
        assert "monthly_series" in dash and len(dash["monthly_series"]) == 4
        assert "services_distribution" in dash and len(dash["services_distribution"]) == 3

    await engine.dispose()

    # 3. Verify 0 files in the repository have UTF-8 BOM (\xef\xbb\xbf)
    import os
    root_dir = Path(__file__).resolve().parent.parent.parent
    exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json", ".md"}
    bom_files = []
    for r, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "dist", "__pycache__"}]
        for fn in files:
            fp = Path(r) / fn
            if fp.suffix.lower() in exts and fp.read_bytes().startswith(b"\xef\xbb\xbf"):
                bom_files.append(str(fp.relative_to(root_dir)))
    assert not bom_files, f"UTF-8 BOM detected in files: {bom_files}"

    paths = list(app.openapi()["paths"].keys())
    print("TOTAL_ROUTES:", len(paths))
    print("UTF8_BOM_FILES_COUNT: 0")
    print("STAGE_4B_FUNCTIONAL_VERIFICATION: PASSED 100%")


if __name__ == "__main__":
    asyncio.run(run_stage_4b_verification())
