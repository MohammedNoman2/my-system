"""
Stage 5-A4 Verification Suite:
1. Alembic migration d0e1f2a3b4c5 upgrades cleanly from c9d0e1f2a3b4 and adds settings.accounting_lock_date.
2. Period Lock blocks backdated/locked-period vouchers and expenses (HTTP 400), allows open dates,
   and allows posting again once unlocked.
3. Daily Reconciliation Report separates 1101 (cash) from 1102 (bank/transfer) across currencies.
"""
import asyncio
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import office_today
from app.core.database import Base
from app.models.booking import BookingType
from app.models.exchange_rate import ExchangeRate
from sqlalchemy import select
from app.models.financial import FinancialTransaction, PaymentMethod
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, VisaDetailCreate
from app.schemas.financial import ExpenseCreate
from app.schemas.report import ReportFilter
from app.api.routes.bookings import create_booking
from app.api.routes.finance import VoidVoucherRequest, create_expense, void_voucher
from app.api.routes.reports import build_report
from app.api.routes.settings import PeriodLockUpdate, get_period_lock, update_period_lock
from app.services.accounting_service import init_chart_of_accounts


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5a4-verifier"}


def test_stage_5a4_alembic_period_lock_column():
    """التأكد من نجاح ترحيل d0e1f2a3b4c5 على نسخة SQLite معزولة وإضافة عمود accounting_lock_date."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_period_lock.db"
        conn = sqlite3.connect(db_file)
        conn.execute(
            """
            CREATE TABLE settings (
                id INTEGER PRIMARY KEY,
                office_name VARCHAR(255) NOT NULL DEFAULT 'عالم النقل',
                tagline VARCHAR(255) NOT NULL DEFAULT '',
                address VARCHAR(255) NOT NULL DEFAULT '',
                phone_numbers TEXT NOT NULL DEFAULT '',
                email VARCHAR(100),
                website VARCHAR(100),
                logo_image_url VARCHAR(255),
                logo_data TEXT,
                default_currency VARCHAR(10) NOT NULL DEFAULT 'YER',
                footer_text TEXT NOT NULL DEFAULT '',
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        )
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version (version_num) VALUES ('c9d0e1f2a3b4')")
        conn.commit()
        conn.close()

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_file.as_posix()}")
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(db_file)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
        ver = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        conn.close()

        assert ver in ("d0e1f2a3b4c5", "e1f2a3b4c5d6", "f2a3b4c5d6e7"), f"Expected head f2a3b4c5d6e7, got {ver}"
        assert "accounting_lock_date" in cols


async def _run_5a4_period_lock_and_reconciliation():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    req = _DummyRequest()
    today = office_today()
    yesterday = today - timedelta(days=1)

    async with Session() as db:
        await init_chart_of_accounts(db)
        db.add_all(
            [
                ExchangeRate(from_currency="USD", to_currency="YER", rate=Decimal("530.0000")),
                ExchangeRate(from_currency="SAR", to_currency="YER", rate=Decimal("140.0000")),
            ]
        )
        admin = User(
            username="admin_lock",
            password_hash="x",
            full_name="مدير القفل",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 1. Create a cash YER booking (+4000 YER) and a bank-transfer SAR booking (+500 SAR) today
        await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("3000.00"),
                selling_price=Decimal("5000.00"),
                paid_amount=Decimal("4000.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="زيارة",
                    application_date=today,
                    applicant_name="طارق صالح محمد",
                    applicant_phone="771234567",
                    passport_number="P12345670",
                    birth_date=date(1990, 1, 1),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("350.00"),
                selling_price=Decimal("500.00"),
                paid_amount=Decimal("500.00"),
                currency="SAR",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="KRM-5A4",
                visa_details=VisaDetailCreate(
                    visa_type="عمرة",
                    application_date=today,
                    applicant_name="نواف علي حسن",
                    applicant_phone="772345678",
                    passport_number="P23456780",
                    birth_date=date(1991, 4, 4),
                    birth_place="تعز",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 2. Lock accounting period up to yesterday
        lock_res = await update_period_lock(
            data=PeriodLockUpdate(accounting_lock_date=yesterday),
            request=req,
            current_user=admin,
            db=db,
        )
        assert lock_res["accounting_lock_date"] == yesterday.isoformat()
        got_lock = await get_period_lock(current_user=admin, db=db)
        assert got_lock["accounting_lock_date"] == yesterday.isoformat()

        # 3. Expense dated yesterday (locked) must fail with HTTP 400
        with pytest.raises(HTTPException) as exc_info:
            await create_expense(
                data=ExpenseCreate(
                    expense_type="قرطاسية",
                    amount=Decimal("500.00"),
                    currency="YER",
                    payment_method=PaymentMethod.CASH,
                    transaction_date=yesterday,
                ),
                request=req,
                current_user=admin,
                db=db,
            )
        assert exc_info.value.status_code == 400
        assert "مغلقة" in exc_info.value.detail
        await db.rollback()
        await db.refresh(admin)

        # 4. Expense dated today (open) succeeds
        await create_expense(
            data=ExpenseCreate(
                expense_type="قرطاسية",
                amount=Decimal("500.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                transaction_date=today,
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 5. Unlock period and verify yesterday expense now succeeds
        await update_period_lock(
            data=PeriodLockUpdate(accounting_lock_date=None),
            request=req,
            current_user=admin,
            db=db,
        )
        await create_expense(
            data=ExpenseCreate(
                expense_type="قرطاسية",
                amount=Decimal("200.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                transaction_date=yesterday,
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 6. Daily Reconciliation Report separates 1101-YER (cash) and 1102-SAR (bank)
        rep = await build_report(
            ReportFilter(report_type="daily_reconciliation", start_date=today, end_date=today),
            current_user=admin,
            db=db,
        )
        assert rep.report_type == "daily_reconciliation"
        by_code = {r["القناة / المرجع"].split(" — ")[0]: r for r in rep.rows if r["النوع"] == "قناة مالية"}
        assert by_code["1101-YER"]["الوارد"] == 4000.0
        assert by_code["1101-YER"]["الصادر"] == 700.0  # 500 + 200 (both JE posted with today's timestamp)
        assert by_code["1101-YER"]["الصافي"] == 3300.0
        assert by_code["1102-SAR"]["الوارد"] == 500.0
        assert by_code["1102-SAR"]["الصادر"] == 0.0

        # 7. Voiding a voucher dated inside a locked period must fail with HTTP 400
        yest_tx = (
            await db.execute(
                select(FinancialTransaction).where(FinancialTransaction.transaction_date == yesterday)
            )
        ).scalar_one()
        await update_period_lock(
            data=PeriodLockUpdate(accounting_lock_date=yesterday),
            request=req,
            current_user=admin,
            db=db,
        )
        with pytest.raises(HTTPException) as void_exc:
            await void_voucher(
                voucher_id=yest_tx.id,
                data=VoidVoucherRequest(void_reason="اختبار منع إلغاء سند في فترة مقفلة"),
                request=req,
                current_user=admin,
                db=db,
            )
        assert void_exc.value.status_code == 400
        assert "مغلقة" in void_exc.value.detail

    await engine.dispose()


def test_stage_5a4_period_lock_and_reconciliation():
    asyncio.run(_run_5a4_period_lock_and_reconciliation())
