"""
Stage 6-C Verification Suite (PostgreSQL / asyncpg):
1. Verify alembic upgrade head on an empty PostgreSQL schema.
2. Verify Base.metadata.create_all creates all tables cleanly on PostgreSQL (production path).
3. Verify FastAPI ASGI lifespan seeding + POST /api/auth/login + audit logs date filter.
4. Verify full shift open -> flight booking -> receipt voucher allocation -> cancel booking -> close shift.
5. Verify get_dashboard_summary, get_dashboard_alerts, and all 9 report types (strict PostgreSQL GROUP BY).
"""
import asyncio
import os
import sys
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PG_URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not PG_URL.startswith("postgresql"),
    reason="Requires PostgreSQL DATABASE_URL",
)


async def _run_postgres_verification():
    # 1. Verify alembic upgrade head on a completely empty PostgreSQL schema
    engine = create_async_engine(PG_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", PG_URL)
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    # 2. Reset schema & verify Base.metadata.create_all on real PostgreSQL
    engine = create_async_engine(PG_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        from app.models import Base  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    from main import app
    from app.core.config import office_today
    from app.core.database import AsyncSessionLocal
    from app.models.booking import BookingType
    from app.models.cash_shift import ShiftStatus
    from app.models.customer import Customer
    from app.models.financial import EntityType, PaymentMethod
    from app.models.supplier import Supplier
    from app.models.user import User
    from app.schemas.booking import BookingCancelRequest, BookingCreate, FlightDetailCreate
    from app.schemas.financial import ReceiptVoucherCreate
    from app.api.routes.bookings import cancel_booking, create_booking
    from app.api.routes.dashboard import get_dashboard_alerts, get_dashboard_summary
    from app.api.routes.finance import create_receipt_voucher
    from app.api.routes.reports import ReportFilter, generate_report
    from app.api.routes.settings import list_audit_logs
    from app.services.shift_service import close_shift, open_shift

    # 3. Trigger ASGI lifespan seeding & login
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            login_res = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert login_res.status_code == 200, login_res.text

        async with AsyncSessionLocal() as db:
            admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            today = office_today()
            req = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"user-agent": "pg-test"})

            # 4. Audit logs date filter
            logs = await list_audit_logs(
                limit=50,
                offset=0,
                action="LOGIN",
                table_name=None,
                date_from=today - timedelta(days=1),
                date_to=today + timedelta(days=1),
                search=None,
                current_user=admin,
                db=db,
            )
            assert len(logs) >= 1

            # 5. Open shift
            shift = await open_shift(
                db=db,
                user_id=admin.id,
                starting_balance=Decimal("10000.00"),
                starting_balance_sar=Decimal("0.00"),
                starting_balance_usd=Decimal("0.00"),
            )
            await db.commit()
            assert shift.id > 0

            # 6. Customer & Supplier + Deferred Flight Booking
            cust = Customer(name="عميل اختبار بوستجرس", phone_number="770001122", balance=Decimal("0"))
            supp = Supplier(name="مورد اختبار بوستجرس", phone_number="770003344", balance=Decimal("0"))
            db.add_all([cust, supp])
            await db.commit()
            await db.refresh(cust)
            await db.refresh(supp)

            flight = await create_booking(
                data=BookingCreate(
                    type=BookingType.FLIGHT,
                    customer_id=cust.id,
                    supplier_id=supp.id,
                    cost_price=Decimal("200.00"),
                    selling_price=Decimal("250.00"),
                    paid_amount=Decimal("0.00"),
                    currency="USD",
                    payment_method=PaymentMethod.CASH,
                    flight_details=FlightDetailCreate(
                        first_middle_name="خالد محمد علي",
                        last_name="الهمداني",
                        passenger_category="adult",
                        airline_company="اليمنية",
                        flight_number="IY600",
                        departure_airport="SAH",
                        arrival_airport="CAI",
                        departure_date=today + timedelta(days=1),
                        departure_time=time(10, 30),
                        passenger_phone="770001122",
                        passport_number="P1234567",
                        birth_date=date(1990, 5, 5),
                        birth_place="صنعاء",
                    ),
                ),
                request=req,
                current_user=admin,
                db=db,
            )
            assert flight.id > 0

            # 7. Receipt voucher with booking allocation
            rv = await create_receipt_voucher(
                data=ReceiptVoucherCreate(
                    entity_type=EntityType.CUSTOMER,
                    entity_id=cust.id,
                    amount=Decimal("100.00"),
                    currency="USD",
                    payment_method=PaymentMethod.CASH,
                    booking_id=flight.id,
                    notes="دفعة تخصيص اختبار PG",
                ),
                request=req,
                current_user=admin,
                db=db,
            )
            assert rv["transaction_id"].startswith("RC-")

            # 8. Cancel booking
            cancelled = await cancel_booking(
                flight.id,
                BookingCancelRequest(
                    reason="اختبار PG",
                    refund_amount=Decimal("80.00"),
                    payment_method=PaymentMethod.CASH,
                ),
                req,
                admin,
                db,
            )
            assert "message" in cancelled

            # 9. Close shift
            closed = await close_shift(
                db=db,
                shift_id=shift.id,
                user_id=admin.id,
                actual_cash=Decimal("10000.00"),
                actual_cash_sar=Decimal("0.00"),
                actual_cash_usd=Decimal("20.00"),
            )
            await db.commit()
            assert closed.status == ShiftStatus.CLOSED

            # 10. Dashboard summary & alerts
            summary = await get_dashboard_summary(current_user=admin, db=db)
            alerts = await get_dashboard_alerts(current_user=admin, db=db)
            assert summary is not None
            assert isinstance(alerts, list)

            # 11. All 9 report types (strict PostgreSQL GROUP BY verification)
            report_types = [
                "bookings_detailed",
                "revenue",
                "expenses",
                "profit_loss",
                "debts",
                "employee_performance",
                "cash_flow",
                "daily_reconciliation",
                "passport_tracking",
            ]
            for rt in report_types:
                res = await generate_report(
                    filters=ReportFilter(
                        report_type=rt,
                        start_date=today - timedelta(days=7),
                        end_date=today + timedelta(days=7),
                    ),
                    current_user=admin,
                    db=db,
                )
                assert res is not None, f"Report {rt} returned None"


def test_stage_6c_postgresql_full_verification():
    asyncio.run(_run_postgres_verification())
