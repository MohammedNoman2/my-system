"""
Stage 5-C Verification Suite:
1. Passport issuing_office persistence + computed 24-48h status + passport_tracking report.
2. 48h upcoming departure alerts (Flight & Transport) with WhatsApp wa.me links.
3. Audit log filters (action, table_name, date_from, date_to, search).
4. In-memory login rate limiting (10/minute) and Arabic 429 handler.
"""
import asyncio
import sys
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from slowapi.errors import RateLimitExceeded

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
from app.models.booking import BookingType
from app.models.exchange_rate import ExchangeRate
from app.models.financial import PaymentMethod
from app.models.user import User, UserRole
from app.schemas.booking import (
    BookingCreate,
    FlightDetailCreate,
    PassportDetailCreate,
    TransportDetailCreate,
    compute_passport_24_48_status,
)
from main import arabic_rate_limit_handler
from app.api.routes.bookings import create_booking
from app.api.routes.dashboard import get_dashboard_alerts
from app.api.routes.reports import ReportFilter, generate_report
from app.api.routes.settings import list_audit_logs
from app.services.accounting_service import init_chart_of_accounts
from app.core.config import office_today


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5c-verifier"}


async def _run_5c_tests():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    req = _DummyRequest()
    today = office_today()

    assert compute_passport_24_48_status(today, today)[0] == "under_24h"
    assert compute_passport_24_48_status(today - timedelta(days=1), today)[0] == "within_48h"
    assert compute_passport_24_48_status(today - timedelta(days=3), today)[0] == "over_48h"

    async with Session() as db:
        await init_chart_of_accounts(db)
        db.add_all(
            [
                ExchangeRate(from_currency="USD", to_currency="YER", rate=Decimal("533.0000")),
                ExchangeRate(from_currency="SAR", to_currency="YER", rate=Decimal("140.0000")),
            ]
        )
        admin = User(
            username="admin_5c",
            password_hash="x",
            full_name="المدير",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 1. Passport with issuing_office
        pa = await create_booking(
            data=BookingCreate(
                type=BookingType.PASSPORT,
                cost_price=Decimal("20000.00"),
                selling_price=Decimal("30000.00"),
                paid_amount=Decimal("30000.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                passport_details=PassportDetailCreate(
                    issuing_office="مصلحة الجوازات - صنعاء",
                    application_date=today - timedelta(days=1),
                    first_middle_name="عادل صالح علي",
                    last_name="المقطري",
                    applicant_phone="771112233",
                    id_number="01012233445",
                    birth_date=date(1990, 5, 5),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        assert pa.passport_details.issuing_office == "مصلحة الجوازات - صنعاء"
        assert pa.passport_details.processing_status_code == "within_48h"

        # 2. Upcoming 48h flight for departure alert + WhatsApp URL
        await create_booking(
            data=BookingCreate(
                type=BookingType.FLIGHT,
                cost_price=Decimal("400.00"),
                selling_price=Decimal("500.00"),
                paid_amount=Decimal("500.00"),
                currency="USD",
                payment_method=PaymentMethod.CASH,
                flight_details=FlightDetailCreate(
                    airline_company="اليمنية",
                    flight_number="IY602",
                    departure_airport="SAH",
                    arrival_airport="JED",
                    departure_date=today + timedelta(days=1),
                    departure_time=time(14, 0),
                    first_middle_name="ناصر علي محمد",
                    last_name="الأهدل",
                    passenger_phone="778889900",
                    passport_number="P88990011",
                    birth_date=date(1987, 3, 3),
                    birth_place="الحديدة",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        alerts = await get_dashboard_alerts(current_user=admin, db=db)
        dep_alerts = [a for a in alerts if a["type"] == "departure"]
        assert len(dep_alerts) >= 1
        assert dep_alerts[0]["whatsapp_url"].startswith("https://wa.me/967778889900")

        # 3. Passport tracking report
        rep = await generate_report(
            filters=ReportFilter(report_type="passport_tracking"),
            current_user=admin,
            db=db,
        )
        assert rep.total_count == 1
        assert rep.rows[0]["مكتب الإصدار"] == "مصلحة الجوازات - صنعاء"

        # 4. Audit log filters
        logs = await list_audit_logs(
            limit=50,
            offset=0,
            action="INSERT",
            table_name="bookings",
            date_from=today - timedelta(days=1),
            date_to=today + timedelta(days=1),
            search=None,
            current_user=admin,
            db=db,
        )
        assert len(logs) >= 2

        # 5. WhatsApp 10-digit leading-zero local phone normalization (0777889900 -> 967777889900)
        await create_booking(
            data=BookingCreate(
                type=BookingType.TRANSPORT,
                cost_price=Decimal("10000.00"),
                selling_price=Decimal("15000.00"),
                paid_amount=Decimal("15000.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                transport_details=TransportDetailCreate(
                    transport_company="الصقور",
                    departure_station="صنعاء",
                    arrival_station="عدن",
                    travel_date=today + timedelta(days=1),
                    travel_time=time(8, 0),
                    first_middle_name="ياسر علي صالح",
                    last_name="البريهي",
                    passenger_phone="0777889900",
                    id_type="national_id",
                    id_number="01015566778",
                    birth_date=date(1992, 2, 2),
                    birth_place="تعز",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        alerts2 = await get_dashboard_alerts(current_user=admin, db=db)
        tr_alerts = [a for a in alerts2 if a["type"] == "departure" and "البريهي" in a["title"]]
        assert len(tr_alerts) == 1
        assert tr_alerts[0]["whatsapp_url"].startswith("https://wa.me/967777889900")

        # 6. Direct verification of Arabic 429 rate-limit handler
        exc = RateLimitExceeded(SimpleNamespace(limit="10 per 1 minute", error_message=None))
        rate_resp = await arabic_rate_limit_handler(req, exc)
        assert rate_resp.status_code == 429
        assert "تم تجاوز الحد المسموح" in rate_resp.body.decode("utf-8")

    await engine.dispose()


def test_stage_5c_passport_alerts_audit_and_rate_limit():
    asyncio.run(_run_5c_tests())
