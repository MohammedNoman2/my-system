"""
Stage 5-A3 Verification Suite:
1. Alembic migration c9d0e1f2a3b4 upgrades cleanly on a copy of schema at b7c8d9e0f1a2.
2. Opening a multi-currency shift (YER, SAR, USD) stores all 3 starting balances.
3. Cash receipts/expenses in YER, SAR, and USD update each currency's system balance independently;
   bank transfers (1102) are excluded from cash shift totals.
4. Closing the shift computes ending_balance_system, ending_balance_actual, and difference per currency.
"""
import asyncio
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
from app.models.booking import BookingType
from app.models.exchange_rate import ExchangeRate
from app.models.financial import EntityType, PaymentMethod
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, VisaDetailCreate
from app.schemas.financial import ExpenseCreate
from app.api.routes.bookings import create_booking
from app.api.routes.finance import (
    CloseShiftRequest,
    OpenShiftRequest,
    close_cash_shift,
    create_expense,
    get_active_shift_status,
    open_cash_shift,
)
from app.services.accounting_service import init_chart_of_accounts


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5a3-verifier"}


def test_stage_5a3_alembic_multicurrency_columns():
    """تأكد من نجاح ترحيل c9d0e1f2a3b4 على قاعدة SQLite معزولة وإضافة الأعمدة الثمانية."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_shift_mig.db"
        conn = sqlite3.connect(db_file)
        conn.execute(
            """
            CREATE TABLE cash_shifts (
                id INTEGER PRIMARY KEY,
                shift_number VARCHAR(50) NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                opened_at DATETIME NOT NULL,
                closed_at DATETIME,
                starting_balance NUMERIC(18, 4) NOT NULL DEFAULT 0,
                ending_balance_system NUMERIC(18, 4),
                ending_balance_actual NUMERIC(18, 4),
                difference NUMERIC(18, 4),
                status VARCHAR(6) NOT NULL,
                closing_notes TEXT
            )
            """
        )
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version (version_num) VALUES ('b7c8d9e0f1a2')")
        conn.commit()
        conn.close()

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_file.as_posix()}")
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(db_file)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cash_shifts)").fetchall()}
        ver = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        conn.close()

        assert ver in ("c9d0e1f2a3b4", "d0e1f2a3b4c5", "e1f2a3b4c5d6", "f2a3b4c5d6e7"), f"Expected head f2a3b4c5d6e7, got {ver}"
        for expected_col in (
            "starting_balance_sar",
            "starting_balance_usd",
            "ending_balance_system_sar",
            "ending_balance_system_usd",
            "ending_balance_actual_sar",
            "ending_balance_actual_usd",
            "difference_sar",
            "difference_usd",
        ):
            assert expected_col in cols, f"Missing column {expected_col}"


async def _run_5a3_shift_flow():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    req = _DummyRequest()

    async with Session() as db:
        await init_chart_of_accounts(db)
        db.add_all(
            [
                ExchangeRate(from_currency="USD", to_currency="YER", rate=Decimal("530.0000")),
                ExchangeRate(from_currency="SAR", to_currency="YER", rate=Decimal("140.0000")),
            ]
        )
        admin = User(
            username="admin_shift",
            password_hash="x",
            full_name="مدير الوردية",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 1. Open multi-currency shift
        opened = await open_cash_shift(
            data=OpenShiftRequest(
                starting_balance=Decimal("10000.00"),
                starting_balance_sar=Decimal("500.00"),
                starting_balance_usd=Decimal("100.00"),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        shift_id = opened["shift_id"]
        assert opened["starting_balance"] == 10000.0
        assert opened["starting_balance_sar"] == 500.0
        assert opened["starting_balance_usd"] == 100.0

        # 2. Cash booking in SAR (+300 SAR)
        await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("200.00"),
                selling_price=Decimal("400.00"),
                paid_amount=Decimal("300.00"),
                currency="SAR",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="عمرة",
                    application_date=date(2026, 11, 19),
                    applicant_name="أحمد علي سعيد",
                    applicant_phone="772223344",
                    passport_number="P99887766",
                    birth_date=date(1990, 5, 5),
                    birth_place="تعز",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 3. Cash booking in USD (+50 USD)
        await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("40.00"),
                selling_price=Decimal("80.00"),
                paid_amount=Decimal("50.00"),
                currency="USD",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="عمل",
                    application_date=date(2026, 11, 19),
                    applicant_name="سالم حسن ناصر",
                    applicant_phone="773334455",
                    passport_number="P55443322",
                    birth_date=date(1988, 3, 3),
                    birth_place="عدن",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 4. Bank transfer booking in USD (+100 USD) must NOT enter cash shift
        await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("70.00"),
                selling_price=Decimal("100.00"),
                paid_amount=Decimal("100.00"),
                currency="USD",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="BNK-5A3",
                visa_details=VisaDetailCreate(
                    visa_type="زيارة",
                    application_date=date(2026, 11, 19),
                    applicant_name="ماجد قاسم عمر",
                    applicant_phone="774445566",
                    passport_number="P44332211",
                    birth_date=date(1992, 7, 7),
                    birth_place="إب",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 5a. Cash booking in YER (+5000 YER) so 1101-YER ledger balance covers the upcoming cash expense
        await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("6000.00"),
                selling_price=Decimal("8000.00"),
                paid_amount=Decimal("5000.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="زيارة",
                    application_date=date(2026, 11, 19),
                    applicant_name="ياسر محمد علي",
                    applicant_phone="775556677",
                    passport_number="P33221100",
                    birth_date=date(1993, 9, 9),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 5b. Cash expense in YER (-1500 YER)
        await create_expense(
            data=ExpenseCreate(
                expense_type="ضيافة",
                amount=Decimal("1500.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                transaction_date=date(2026, 11, 19),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 6. Check active shift balances per currency
        active = await get_active_shift_status(current_user=admin, db=db)
        by_c = active["shift"]["balances_by_currency"]
        assert by_c["YER"]["current_system_balance"] == 13500.0  # 10000 + 5000 - 1500
        assert by_c["SAR"]["current_system_balance"] == 800.0
        assert by_c["USD"]["current_system_balance"] == 150.0  # Bank transfer excluded

        # 7. Close shift with actual cash (YER=13500 exact, SAR=790 -10 deficit, USD=155 +5 surplus)
        closed = await close_cash_shift(
            data=CloseShiftRequest(
                shift_id=shift_id,
                actual_cash=Decimal("13500.00"),
                actual_cash_sar=Decimal("790.00"),
                actual_cash_usd=Decimal("155.00"),
                notes="جرد نهاية اليوم متعدد العملات",
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        c_by = closed["balances_by_currency"]
        assert c_by["YER"]["difference"] == 0.0
        assert c_by["SAR"]["difference"] == -10.0
        assert c_by["USD"]["difference"] == 5.0

    await engine.dispose()


def test_stage_5a3_multicurrency_shift_flow():
    asyncio.run(_run_5a3_shift_flow())
