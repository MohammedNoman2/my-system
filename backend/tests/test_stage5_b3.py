"""
Stage 5-B3 Verification Suite:
1. Server always derives FX rate from ExchangeRate settings (ignores tampered client exchange_rate).
2. Cross-currency overpayment protection blocks allocating more than remaining amount using authoritative settings rate.
"""
import asyncio
import sys
from datetime import date
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
from app.models.financial import EntityType, PaymentMethod
from app.models.voucher_allocation import VoucherAllocation
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, VisaDetailCreate
from app.api.routes.bookings import create_booking
from app.api.routes.finance import AllocationItem, ReceiptVoucherV2Create, create_receipt_voucher_v2
from app.services.accounting_service import init_chart_of_accounts


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5b3-verifier"}


async def _run_5b3_tests():
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
            username="admin_5b3",
            password_hash="x",
            full_name="محاسب الصرف",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 1. Create a deferred YER booking of 28,000 YER (= 200 SAR at 140)
        b = await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("20000.00"),
                selling_price=Decimal("28000.00"),
                paid_amount=Decimal("0.00"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="زيارة",
                    application_date=date(2026, 11, 23),
                    first_middle_name="سعيد محمد علي",
                    last_name="الهمداني",
                    applicant_phone="777112233",
                    passport_number="P99887766",
                    birth_date=date(1992, 4, 12),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 2. Pay 100 SAR with tampered client exchange_rate=200 -> server must use 140 => 14,000.00 YER
        await create_receipt_voucher_v2(
            data=ReceiptVoucherV2Create(
                entity_type=EntityType.CUSTOMER,
                entity_id=b.customer.id,
                total_amount=Decimal("100.00"),
                currency="SAR",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="FX-5B3-1",
                allocations=[
                    AllocationItem(
                        booking_id=b.id,
                        allocated_amount=Decimal("100.00"),
                        exchange_rate=Decimal("200.000000"),
                    )
                ],
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        refreshed_b = (await db.execute(select(Booking).where(Booking.id == b.id))).scalar_one()
        assert Decimal(str(refreshed_b.paid_amount)).quantize(Decimal("0.01")) == Decimal("14000.00")
        assert Decimal(str(refreshed_b.remaining_amount)).quantize(Decimal("0.01")) == Decimal("14000.00")

        alloc = (
            await db.execute(select(VoucherAllocation).where(VoucherAllocation.booking_id == b.id))
        ).scalar_one()
        assert Decimal(str(alloc.exchange_rate)).quantize(Decimal("0.000001")) == Decimal("140.000000")

        # 3. Large-amount precision check: 10,000.00 USD booking paid with 5,330,000.00 YER (rate=533) -> remaining == 0.00
        b_usd = await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("8000.00"),
                selling_price=Decimal("10000.00"),
                paid_amount=Decimal("0.00"),
                currency="USD",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="عمل",
                    application_date=date(2026, 11, 23),
                    first_middle_name="خالد ناصر علي",
                    last_name="الزبيري",
                    applicant_phone="777445566",
                    passport_number="P11223344",
                    birth_date=date(1985, 9, 10),
                    birth_place="عدن",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        await create_receipt_voucher_v2(
            data=ReceiptVoucherV2Create(
                entity_type=EntityType.CUSTOMER,
                entity_id=b_usd.customer.id,
                total_amount=Decimal("5330000.00"),
                currency="YER",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="FX-5B3-3",
                allocations=[
                    AllocationItem(
                        booking_id=b_usd.id,
                        allocated_amount=Decimal("5330000.00"),
                    )
                ],
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        refreshed_usd = (await db.execute(select(Booking).where(Booking.id == b_usd.id))).scalar_one()
        assert Decimal(str(refreshed_usd.remaining_amount)).quantize(Decimal("0.01")) == Decimal("0.00")

        # 4. Attempt overpayment: 105 SAR (= 14,700 YER > 14,000 YER remaining) even with tampered low rate=100
        with pytest.raises(HTTPException) as exc:
            await create_receipt_voucher_v2(
                data=ReceiptVoucherV2Create(
                    entity_type=EntityType.CUSTOMER,
                    entity_id=b.customer.id,
                    total_amount=Decimal("105.00"),
                    currency="SAR",
                    payment_method=PaymentMethod.BANK_TRANSFER,
                    reference_number="FX-5B3-2",
                    allocations=[
                        AllocationItem(
                            booking_id=b.id,
                            allocated_amount=Decimal("105.00"),
                            exchange_rate=Decimal("100.000000"),
                        )
                    ],
                ),
                request=req,
                current_user=admin,
                db=db,
            )
        assert exc.value.status_code == 400

    await engine.dispose()


def test_stage_5b3_server_fx_and_overpayment_guard():
    asyncio.run(_run_5b3_tests())
