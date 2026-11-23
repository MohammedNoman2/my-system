"""
Stage 5-B2 Verification Suite:
1. 3-part name + last_name validation across Flight, Visa, Passport.
2. Automatic flight passenger_category detection (adult / child / infant) from birth_date vs departure_date.
3. Multi-passenger POST /bookings/batch for Flight with strict per-category pricing (no price mixing)
   and single RC receipt proportional allocation.
4. POST /bookings/batch rejects PARCEL with HTTP 400.
"""
import asyncio
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
from app.models.booking import Booking, BookingType
from app.models.exchange_rate import ExchangeRate
from app.models.financial import FinancialTransaction, PaymentMethod
from app.models.user import User, UserRole
from app.models.voucher_allocation import VoucherAllocation
from app.schemas.booking import (
    BookingBatchCreate,
    BookingBatchItem,
    FlightDetailCreate,
    PassportDetailCreate,
    VisaDetailCreate,
)
from app.api.routes.bookings import create_multi_booking_batch
from app.services.accounting_service import init_chart_of_accounts


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5b2-verifier"}


def test_stage_5b2_flight_category_detection_and_names():
    dep = date(2026, 12, 1)
    adult = FlightDetailCreate(
        airline_company="اليمنية",
        flight_number="IY100",
        departure_airport="SAH",
        arrival_airport="JED",
        departure_date=dep,
        departure_time=time(10, 0),
        first_middle_name="محمد أحمد علي",
        last_name="الصالحي",
        passenger_phone="771112233",
        passport_number="P1111111",
        birth_date=date(1990, 1, 1),
        birth_place="صنعاء",
    )
    child = FlightDetailCreate(
        airline_company="اليمنية",
        flight_number="IY100",
        departure_airport="SAH",
        arrival_airport="JED",
        departure_date=dep,
        departure_time=time(10, 0),
        first_middle_name="سارة محمد أحمد",
        last_name="الصالحي",
        passenger_phone="771112233",
        passport_number="P2222222",
        birth_date=date(2020, 6, 1),
        birth_place="صنعاء",
    )
    infant = FlightDetailCreate(
        airline_company="اليمنية",
        flight_number="IY100",
        departure_airport="SAH",
        arrival_airport="JED",
        departure_date=dep,
        departure_time=time(10, 0),
        first_middle_name="عمر محمد أحمد",
        last_name="الصالحي",
        passenger_phone="771112233",
        passport_number="P3333333",
        birth_date=date(2025, 6, 1),
        birth_place="صنعاء",
    )
    assert adult.passenger_category == "adult"
    assert child.passenger_category == "child"
    assert infant.passenger_category == "infant"
    assert adult.passenger_name == "محمد أحمد علي الصالحي"

    # Visa & Passport 3-part name
    vi = VisaDetailCreate(
        visa_type="عمرة",
        application_date=date(2026, 11, 22),
        first_middle_name="علي صالح يحيى",
        last_name="الحداد",
        applicant_phone="772223344",
        passport_number="P4444444",
        birth_date=date(1985, 5, 5),
        birth_place="تعز",
    )
    pa = PassportDetailCreate(
        application_date=date(2026, 11, 22),
        first_middle_name="فاطمة علي صالح",
        last_name="الحداد",
        applicant_phone="772223344",
        id_number="01010101011",
        birth_date=date(1992, 3, 3),
        birth_place="عدن",
    )
    assert vi.applicant_name == "علي صالح يحيى الحداد"
    assert pa.applicant_name == "فاطمة علي صالح الحداد"


async def _run_5b2_batch():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    req = _DummyRequest()

    async with Session() as db:
        await init_chart_of_accounts(db)
        db.add_all(
            [
                ExchangeRate(from_currency="USD", to_currency="YER", rate=Decimal("533.0000")),
                ExchangeRate(from_currency="SAR", to_currency="YER", rate=Decimal("140.0000")),
            ]
        )
        admin = User(
            username="admin_5b2",
            password_hash="x",
            full_name="مدير الحجوزات",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        dep = date(2026, 12, 1)
        # 1. Flight batch with 1 adult (500 USD), 1 child (350 USD), 1 infant (100 USD) = 950 USD total
        res = await create_multi_booking_batch(
            data=BookingBatchCreate(
                type=BookingType.FLIGHT,
                category_prices={
                    "adult": Decimal("500.00"),
                    "child": Decimal("350.00"),
                    "infant": Decimal("100.00"),
                },
                category_costs={
                    "adult": Decimal("450.00"),
                    "child": Decimal("300.00"),
                    "infant": Decimal("80.00"),
                },
                paid_amount=Decimal("475.00"),
                currency="USD",
                payment_method=PaymentMethod.CASH,
                use_credit_balance=False,
                items=[
                    BookingBatchItem(
                        flight_details=FlightDetailCreate(
                            airline_company="اليمنية",
                            flight_number="IY200",
                            departure_airport="SAH",
                            arrival_airport="JED",
                            departure_date=dep,
                            departure_time=time(9, 0),
                            first_middle_name="أحمد علي صالح",
                            last_name="المنصور",
                            passenger_category="infant",  # يجب أن يتجاهلها الخادم ويحسبها adult
                            passenger_phone="773334455",
                            passport_number="P5555551",
                            birth_date=date(1988, 1, 1),
                            birth_place="صنعاء",
                        )
                    ),
                    BookingBatchItem(
                        flight_details=FlightDetailCreate(
                            airline_company="اليمنية",
                            flight_number="IY200",
                            departure_airport="SAH",
                            arrival_airport="JED",
                            departure_date=dep,
                            departure_time=time(9, 0),
                            first_middle_name="سالم أحمد علي",
                            last_name="المنصور",
                            passenger_phone="773334455",
                            passport_number="P5555552",
                            birth_date=date(2019, 4, 4),
                            birth_place="صنعاء",
                        )
                    ),
                    BookingBatchItem(
                        flight_details=FlightDetailCreate(
                            airline_company="اليمنية",
                            flight_number="IY200",
                            departure_airport="SAH",
                            arrival_airport="JED",
                            departure_date=dep,
                            departure_time=time(9, 0),
                            first_middle_name="ليلى أحمد علي",
                            last_name="المنصور",
                            passenger_phone="773334455",
                            passport_number="P5555553",
                            birth_date=date(2025, 8, 1),
                            birth_place="صنعاء",
                        )
                    ),
                ],
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        assert res["count"] == 3
        bks = (
            await db.execute(select(Booking).where(Booking.id.in_(res["booking_ids"])).order_by(Booking.id))
        ).scalars().all()
        assert [Decimal(str(b.selling_price)).quantize(Decimal("0.01")) for b in bks] == [
            Decimal("500.00"),
            Decimal("350.00"),
            Decimal("100.00"),
        ]
        # 50% paid proportionally: 250.00, 175.00, 50.00
        allocs = (
            await db.execute(select(VoucherAllocation).order_by(VoucherAllocation.booking_id))
        ).scalars().all()
        assert [Decimal(str(a.allocated_amount)).quantize(Decimal("0.01")) for a in allocs] == [
            Decimal("250.00"),
            Decimal("175.00"),
            Decimal("50.00"),
        ]

        # 2. Reject PARCEL batch with HTTP 400
        with pytest.raises(HTTPException) as exc:
            await create_multi_booking_batch(
                data=BookingBatchCreate(
                    type=BookingType.PARCEL,
                    selling_price=Decimal("100.00"),
                    items=[BookingBatchItem()],
                ),
                request=req,
                current_user=admin,
                db=db,
            )
        assert exc.value.status_code == 400

    await engine.dispose()


def test_stage_5b2_multi_booking_batch():
    asyncio.run(_run_5b2_batch())
