"""
Stage 5-A5 Verification Suite:
1. Receipt voucher v2 with multiple booking allocations + unallocated surplus.
2. print_voucher HTML output includes real ticket numbers (not raw #id) and unallocated surplus note.
"""
import asyncio
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
from app.models.booking import BookingType
from app.models.exchange_rate import ExchangeRate
from app.models.financial import EntityType, FinancialTransaction, PaymentMethod
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, VisaDetailCreate
from app.api.routes.bookings import create_booking
from app.api.routes.finance import (
    AllocationItem,
    ReceiptVoucherV2Create,
    create_receipt_voucher_v2,
    print_voucher,
)
from app.services.accounting_service import init_chart_of_accounts


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5a5-verifier"}


async def _run_5a5_tests():
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
            username="admin_5a5",
            password_hash="x",
            full_name="محاسب السندات",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 1. Create two deferred bookings for the same customer
        b1 = await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("200.00"),
                selling_price=Decimal("300.00"),
                paid_amount=Decimal("0.00"),
                currency="SAR",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="زيارة",
                    application_date=date(2026, 11, 20),
                    applicant_name="ماهر عبد الله صالح",
                    applicant_phone="776667788",
                    passport_number="P66778899",
                    birth_date=date(1990, 6, 6),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        b2 = await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                customer_id=b1.customer.id,
                cost_price=Decimal("150.00"),
                selling_price=Decimal("250.00"),
                paid_amount=Decimal("0.00"),
                currency="SAR",
                payment_method=PaymentMethod.CASH,
                visa_details=VisaDetailCreate(
                    visa_type="عمرة",
                    application_date=date(2026, 11, 20),
                    applicant_name="ماهر عبد الله صالح",
                    applicant_phone="776667788",
                    passport_number="P66778899",
                    birth_date=date(1990, 6, 6),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        # 2. Multi-allocation receipt (300 + 250 = 550 allocated, + 50 surplus = 600 SAR)
        rc = await create_receipt_voucher_v2(
            data=ReceiptVoucherV2Create(
                entity_type=EntityType.CUSTOMER,
                entity_id=b1.customer.id,
                total_amount=Decimal("600.00"),
                currency="SAR",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="KRM-5A5",
                allocations=[
                    AllocationItem(booking_id=b1.id, allocated_amount=Decimal("300.00"), exchange_rate=Decimal("1.000000")),
                    AllocationItem(booking_id=b2.id, allocated_amount=Decimal("250.00"), exchange_rate=Decimal("1.000000")),
                ],
            ),
            request=req,
            current_user=admin,
            db=db,
        )

        tx = (
            await db.execute(
                select(FinancialTransaction).where(FinancialTransaction.transaction_id == rc["transaction_id"])
            )
        ).scalar_one()

        resp = await print_voucher(voucher_id=tx.id, mode="a4", current_user=admin, db=db)
        html = resp.body.decode("utf-8")
        assert b1.ticket_number in html, f"Expected {b1.ticket_number} in printed voucher HTML"
        assert b2.ticket_number in html, f"Expected {b2.ticket_number} in printed voucher HTML"
        assert "فائض غير مخصص" in html, "Expected unallocated surplus label in printed voucher HTML"
        assert "50.00 SAR" in html, "Expected unallocated surplus 50.00 SAR in printed voucher HTML"

    await engine.dispose()


def test_stage_5a5_multi_allocation_print():
    asyncio.run(_run_5a5_tests())
