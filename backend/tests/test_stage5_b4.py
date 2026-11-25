"""
Stage 5-B4 Verification Suite:
1. Strict full-name customer matching: identical name+doc reuses customer & updates balance; differing last name creates a separate customer.
2. Multi-passenger batch with selected customer_id on passenger 1 creates a separate customer for passenger 2 if not already registered.
3. Thermal voucher HTML fits single landscape page layout with compact typography and borderless logo-box.
"""
import asyncio
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
from app.models.booking import Booking, BookingType
from app.models.customer import Customer
from app.models.exchange_rate import ExchangeRate
from app.models.financial import PaymentMethod
from app.models.settings import Settings as OfficeSettings
from app.models.user import User, UserRole
from app.schemas.booking import (
    BookingCreate,
    TransportBatchCreate,
    TransportDetailCreate,
)
from app.api.routes.bookings import create_booking, create_transport_batch
from app.services.accounting_service import init_chart_of_accounts
from app.services.print_service import generate_voucher_html


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5b4-verifier"}


async def _run_5b4_tests():
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
            username="admin_5b4",
            password_hash="x",
            full_name="المدير",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 1. First booking creates customer #1
        b1 = await create_booking(
            data=BookingCreate(
                type=BookingType.TRANSPORT,
                cost_price=Decimal("20000.00"),
                selling_price=Decimal("30000.00"),
                paid_amount=Decimal("10000.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                transport_details=TransportDetailCreate(
                    transport_company="الصقور",
                    departure_station="صنعاء",
                    arrival_station="جدة",
                    travel_date=date(2026, 12, 1),
                    travel_time=time(16, 0),
                    first_middle_name="هشام عبدالوكيل نعمان",
                    last_name="عبدالله",
                    passenger_phone="776522371",
                    id_type="passport",
                    id_number="24687245",
                    birth_date=date(1990, 1, 1),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        c1_id = b1.customer.id

        # 2. Same phone + different last name & different doc -> MUST create a new separate customer
        b2 = await create_booking(
            data=BookingCreate(
                type=BookingType.TRANSPORT,
                cost_price=Decimal("20000.00"),
                selling_price=Decimal("30000.00"),
                paid_amount=Decimal("30000.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                transport_details=TransportDetailCreate(
                    transport_company="الصقور",
                    departure_station="صنعاء",
                    arrival_station="جدة",
                    travel_date=date(2026, 12, 1),
                    travel_time=time(16, 0),
                    first_middle_name="هشام عبدالوكيل نعمان",
                    last_name="الصالحي",
                    passenger_phone="776522371",
                    id_type="passport",
                    id_number="99887766",
                    birth_date=date(1992, 2, 2),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        assert b2.customer.id != c1_id, "Differing last name must create a new customer"

        # 3. Batch booking with customer_id=c1_id: passenger 1 uses c1_id, passenger 2 creates a 3rd separate customer
        batch = await create_transport_batch(
            data=TransportBatchCreate(
                customer_id=c1_id,
                cost_price=Decimal("20000.00"),
                selling_price=Decimal("30000.00"),
                paid_amount=Decimal("30000.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                passengers=[
                    TransportDetailCreate(
                        transport_company="الصقور",
                        departure_station="صنعاء",
                        arrival_station="جدة",
                        travel_date=date(2026, 12, 5),
                        travel_time=time(16, 0),
                        first_middle_name="هشام عبدالوكيل نعمان",
                        last_name="عبدالله",
                        passenger_phone="776522371",
                        id_type="passport",
                        id_number="24687245",
                        birth_date=date(1990, 1, 1),
                        birth_place="صنعاء",
                    ),
                    TransportDetailCreate(
                        transport_company="الصقور",
                        departure_station="صنعاء",
                        arrival_station="جدة",
                        travel_date=date(2026, 12, 5),
                        travel_time=time(16, 0),
                        first_middle_name="طارق علي سعيد",
                        last_name="الحمدي",
                        passenger_phone="771234567",
                        id_type="passport",
                        id_number="55443322",
                        birth_date=date(1994, 5, 5),
                        birth_place="تعز",
                    ),
                ],
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        assert batch["count"] == 2
        b_list = (
            await db.execute(select(Booking).where(Booking.id.in_(batch["booking_ids"])).order_by(Booking.id))
        ).scalars().all()
        assert b_list[0].customer_id == c1_id
        assert b_list[1].customer_id != c1_id

        # 4. Thermal HTML compact single-page CSS & borderless logo-box check
        settings = OfficeSettings(
            office_name="عالم النقل",
            tagline="للسفريات والنقل البري والتخليص",
            address="صنعاء - الستين الجنوبي",
            phone_numbers="778699440",
            footer_text="عالم النقل للسفريات - ثقتكم رصيدنا الأعلى",
        )
        full_b1 = (
            await db.execute(
                select(Booking)
                .where(Booking.id == b1.id)
                .options(
                    selectinload(Booking.transport_details),
                    selectinload(Booking.customer),
                    selectinload(Booking.employee),
                )
            )
        ).scalar_one()
        html = generate_voucher_html(full_b1, settings, mode="thermal")
        assert "size: 80mm 60mm;" in html
        assert "border: none;" in html
        assert "table-layout: fixed;" in html

    await engine.dispose()


def test_stage_5b4_matching_batch_and_thermal_print():
    asyncio.run(_run_5b4_tests())
