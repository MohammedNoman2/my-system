"""
Stage 5-B Verification Suite:
1. Transport validation: 3-word first_middle_name + last_name, passport (8), national_id (11), birth_certificate (optional).
2. Transport infants stored in transport_infants, shown in bookings_detailed report, and omitted from printed ticket HTML.
3. Thermal 80mm CSS in print_service.generate_voucher_html.
4. Multi-seat transport batch: per-seat price, independent TR tickets & BOOKING JEs, ONE RC receipt distributed equally with remainder on last ticket.
"""
import asyncio
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
from app.models.accounting import JournalEntry
from app.models.booking import Booking
from app.models.booking_details.transport import TransportInfant
from app.models.exchange_rate import ExchangeRate
from app.models.financial import FinancialTransaction, PaymentMethod
from app.models.settings import Settings
from app.models.user import User, UserRole
from app.models.voucher_allocation import VoucherAllocation
from app.schemas.booking import TransportBatchCreate, TransportDetailCreate, TransportInfantCreate
from app.schemas.report import ReportFilter
from app.api.routes.bookings import create_transport_batch
from app.api.routes.reports import build_report
from app.services.accounting_service import init_chart_of_accounts
from app.services.print_service import generate_voucher_html


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5b-verifier"}


def test_stage_5b_transport_validation_rules():
    # Reject 2-word first_middle_name
    with pytest.raises(ValidationError):
        TransportDetailCreate(
            transport_company="النور",
            departure_station="صنعاء",
            arrival_station="الرياض",
            travel_date=date(2026, 12, 1),
            travel_time=time(8, 0),
            first_middle_name="محمد أحمد",
            last_name="الصالحي",
            passenger_phone="771112233",
            id_type="national_id",
            id_number="12345678901",
            birth_date=date(1990, 1, 1),
            birth_place="صنعاء",
        )

    # Reject national_id != 11 digits
    with pytest.raises(ValidationError):
        TransportDetailCreate(
            transport_company="النور",
            departure_station="صنعاء",
            arrival_station="الرياض",
            travel_date=date(2026, 12, 1),
            travel_time=time(8, 0),
            first_middle_name="محمد أحمد علي",
            last_name="الصالحي",
            passenger_phone="771112233",
            id_type="national_id",
            id_number="12345678",
            birth_date=date(1990, 1, 1),
            birth_place="صنعاء",
        )

    # Accept birth_certificate with empty id_number
    ok_bc = TransportDetailCreate(
        transport_company="النور",
        departure_station="صنعاء",
        arrival_station="الرياض",
        travel_date=date(2026, 12, 1),
        travel_time=time(8, 0),
        first_middle_name="محمد أحمد علي",
        last_name="الصالحي",
        passenger_phone="771112233",
        id_type="birth_certificate",
        id_number="",
        birth_date=date(2020, 5, 5),
        birth_place="صنعاء",
    )
    assert ok_bc.passenger_name == "محمد أحمد علي الصالحي"


async def _run_5b_batch_and_infants():
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
                Settings(),
            ]
        )
        admin = User(
            username="admin_5b",
            password_hash="x",
            full_name="موظف النقل",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 3 seats, selling=200 SAR each (600 total), paid=100 SAR -> shares 33.33, 33.33, 33.34
        passengers = [
            TransportDetailCreate(
                transport_company="البراق",
                departure_station="صنعاء",
                arrival_station="جدة",
                travel_date=date(2026, 12, 10),
                travel_time=time(7, 30),
                first_middle_name="علي صالح محمد",
                last_name="الحداد",
                passenger_phone="771110001",
                id_type="national_id",
                id_number="01010101011",
                birth_date=date(1988, 1, 1),
                birth_place="صنعاء",
                infants=[
                    TransportInfantCreate(
                        full_name="رضيع علي الحداد",
                        id_type="birth_certificate",
                        id_number="",
                        birth_date=date(2025, 6, 1),
                    )
                ],
            ),
            TransportDetailCreate(
                transport_company="البراق",
                departure_station="صنعاء",
                arrival_station="جدة",
                travel_date=date(2026, 12, 10),
                travel_time=time(7, 30),
                first_middle_name="فاطمة يحيى حسن",
                last_name="الحداد",
                passenger_phone="771110002",
                id_type="passport",
                id_number="P1234567",
                birth_date=date(1992, 2, 2),
                birth_place="صنعاء",
            ),
            TransportDetailCreate(
                transport_company="البراق",
                departure_station="صنعاء",
                arrival_station="جدة",
                travel_date=date(2026, 12, 10),
                travel_time=time(7, 30),
                first_middle_name="عمر علي صالح",
                last_name="الحداد",
                passenger_phone="771110003",
                id_type="birth_certificate",
                id_number="",
                birth_date=date(2019, 3, 3),
                birth_place="صنعاء",
            ),
        ]

        res = await create_transport_batch(
            data=TransportBatchCreate(
                cost_price=Decimal("150.00"),
                selling_price=Decimal("200.00"),
                paid_amount=Decimal("100.00"),
                currency="SAR",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="TR-BATCH-1",
                use_credit_balance=False,
                passengers=passengers,
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        assert res["count"] == 3
        assert len(res["ticket_numbers"]) == 3
        assert res["receipt_id"] is not None

        # Verify ONE single receipt voucher & 3 VoucherAllocations summing to 100.00 (33.33, 33.33, 33.34)
        rcs = (await db.execute(select(FinancialTransaction))).scalars().all()
        assert len(rcs) == 1
        allocs = (
            await db.execute(select(VoucherAllocation).order_by(VoucherAllocation.booking_id))
        ).scalars().all()
        assert [Decimal(str(a.allocated_amount)).quantize(Decimal("0.01")) for a in allocs] == [
            Decimal("33.33"),
            Decimal("33.33"),
            Decimal("33.34"),
        ]

        # Verify 3 independent BOOKING JEs + 1 RECEIPT JE
        jes = (await db.execute(select(JournalEntry))).scalars().all()
        assert sum(1 for j in jes if j.reference_type == "BOOKING") == 3
        assert sum(1 for j in jes if j.reference_type == "RECEIPT") == 1

        # Verify infant exists in DB, appears in report, and does NOT appear on printed ticket
        infants = (await db.execute(select(TransportInfant))).scalars().all()
        assert len(infants) == 1

        rep = await build_report(
            ReportFilter(report_type="bookings_detailed"),
            current_user=admin,
            db=db,
        )
        assert any("رضيع علي الحداد" in str(r.get("الرضّع المرافقون", "")) for r in rep.rows)

        first_bk = (
            await db.execute(
                select(Booking)
                .where(Booking.id == res["booking_ids"][0])
                .options(
                    selectinload(Booking.customer),
                    selectinload(Booking.employee),
                    selectinload(Booking.supplier),
                    selectinload(Booking.transport_details),
                    selectinload(Booking.transport_infants),
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        settings_obj = (await db.execute(select(Settings).limit(1))).scalar_one()
        html = generate_voucher_html(first_bk, settings_obj, mode="thermal")
        assert "80mm 60mm" in html
        assert "رضيع علي الحداد" not in html

    await engine.dispose()


def test_stage_5b_batch_and_infants():
    asyncio.run(_run_5b_batch_and_infants())
