import asyncio
import sqlite3
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException
from main import app
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.database import Base
from app.models.user import User, UserRole
from app.models.booking import Booking as BookingModel, BookingStatus, BookingType
from app.models.financial import EntityType, FinancialTransaction, PaymentMethod
from app.schemas.booking import (
    BookingCreate,
    TransportDetailCreate,
    validate_clean_phone,
    validate_clean_doc_number,
)
from app.schemas.financial import ReceiptVoucherCreate
from app.api.routes.bookings import create_booking
from app.api.routes.finance import create_receipt_voucher, void_voucher, VoidVoucherRequest
from app.services.counter_service import init_reference_counters
from app.services.accounting_service import init_chart_of_accounts
from starlette.requests import Request


def _dummy_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/test", "headers": [], "client": ("127.0.0.1", 8000)})


async def run_functional_tests():
    # 1. Check live SQLite index in backend/arp.db (verify by name and across all unique indexes)
    db_path = Path(__file__).resolve().parent.parent / "arp.db"
    conn = sqlite3.connect(str(db_path))
    idxs = conn.execute("PRAGMA index_list(customers)").fetchall()
    for r in idxs:
        if r[2] == 1:
            cols = [c[2] for c in conn.execute(f"PRAGMA index_info('{r[1]}')").fetchall()]
            assert "phone_number" not in cols, f"Unique index still covers phone_number: {r[1]}"
    conn.close()
    phone_idx = [r for r in idxs if r[1] == "ix_customers_phone_number"]
    assert phone_idx and phone_idx[0][2] == 0, f"Phone index is still unique: {phone_idx}"

    # 2. Check phone normalization (+967 -> 9 digits) and 8-digit / dummy doc rejection
    assert validate_clean_phone("+967 771 609 217") == "771609217"
    assert validate_clean_phone("00967771609217") == "771609217"
    for bad_phone in ("77160217", "12345"):
        try:
            validate_clean_phone(bad_phone)
            raise AssertionError(f"Bad phone {bad_phone} was not rejected")
        except ValueError:
            pass

    for bad_doc in ("12345678", "00000000", "11111111"):
        try:
            validate_clean_doc_number(bad_doc)
            raise AssertionError(f"Dummy doc {bad_doc} was not rejected")
        except ValueError:
            pass

    # 3. Functional test on isolated in-memory DB:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        await init_reference_counters(db)
        await init_chart_of_accounts(db)
        admin = User(username="admin", password_hash="x", full_name="مدير", role=UserRole.ADMIN, is_active=True)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # Booking 1: Father with unpaid booking -> status should be PENDING
        b1_data = BookingCreate(
            type=BookingType.TRANSPORT,
            selling_price=Decimal("40000"),
            paid_amount=Decimal("0"),
            currency="YER",
            transport_details=TransportDetailCreate(
                transport_company="النور",
                departure_station="صنعاء",
                arrival_station="الرياض",
                travel_date=date(2026, 11, 10),
                travel_time=time(18, 0),
                passenger_name="مهيوب عبد الحكيم",
                passenger_phone="771609217",
                id_number="01019988776",
                birth_date=date(1985, 5, 10),
                birth_place="تعز",
            ),
        )
        b1 = await create_booking(b1_data, _dummy_request(), admin, db)
        assert b1.status == BookingStatus.PENDING, f"Expected PENDING, got {b1.status}"

        # Booking 2: Same customer with 4-part name and no spacing in عبدالحكيم -> links to same customer_id
        b2_data = BookingCreate(
            type=BookingType.TRANSPORT,
            selling_price=Decimal("40000"),
            paid_amount=Decimal("20000"),
            currency="YER",
            transport_details=TransportDetailCreate(
                transport_company="النور",
                departure_station="صنعاء",
                arrival_station="الرياض",
                travel_date=date(2026, 11, 11),
                travel_time=time(18, 0),
                passenger_name="مهيوب عبدالحكيم مهيوب علي",
                passenger_phone="+967771609217",
                id_number="01019988776",
                birth_date=date(1985, 5, 10),
                birth_place="تعز",
            ),
        )
        b2 = await create_booking(b2_data, _dummy_request(), admin, db)
        assert b2.customer_id == b1.customer_id, "4-part name variation did not link to existing customer"
        assert b2.status == BookingStatus.CONFIRMED, f"Expected CONFIRMED on paid booking, got {b2.status}"

        # Booking 3: Son with different first name sharing father's phone -> creates separate customer without 500
        b3_data = BookingCreate(
            type=BookingType.TRANSPORT,
            selling_price=Decimal("40000"),
            paid_amount=Decimal("40000"),
            currency="YER",
            transport_details=TransportDetailCreate(
                transport_company="النور",
                departure_station="صنعاء",
                arrival_station="الرياض",
                travel_date=date(2026, 11, 12),
                travel_time=time(18, 0),
                passenger_name="أسامة مهيوب عبدالحكيم",
                passenger_phone="771609217",
                id_number="01015544332",
                birth_date=date(2010, 3, 15),
                birth_place="تعز",
            ),
        )
        b3 = await create_booking(b3_data, _dummy_request(), admin, db)
        assert b3.customer_id != b1.customer_id, "Family member did not get a separate customer record"

        # Booking 3b: Two people sharing first+second name ("محمد علي أحمد" vs "محمد علي صالح") with same phone -> must NOT merge under strict=True
        b3b_first = await create_booking(
            BookingCreate(
                type=BookingType.TRANSPORT,
                selling_price=Decimal("40000"),
                paid_amount=Decimal("40000"),
                currency="YER",
                transport_details=TransportDetailCreate(
                    transport_company="النور",
                    departure_station="صنعاء",
                    arrival_station="الرياض",
                    travel_date=date(2026, 11, 12),
                    travel_time=time(18, 0),
                    passenger_name="محمد علي أحمد",
                    passenger_phone="773344556",
                    id_number="01016677881",
                    birth_date=date(1992, 1, 1),
                    birth_place="صنعاء",
                ),
            ),
            _dummy_request(),
            admin,
            db,
        )
        b3b_second = await create_booking(
            BookingCreate(
                type=BookingType.TRANSPORT,
                selling_price=Decimal("40000"),
                paid_amount=Decimal("40000"),
                currency="YER",
                transport_details=TransportDetailCreate(
                    transport_company="النور",
                    departure_station="صنعاء",
                    arrival_station="الرياض",
                    travel_date=date(2026, 11, 12),
                    travel_time=time(18, 0),
                    passenger_name="محمد علي صالح",
                    passenger_phone="773344556",
                    id_number="01016677882",
                    birth_date=date(1994, 1, 1),
                    birth_place="صنعاء",
                ),
            ),
            _dummy_request(),
            admin,
            db,
        )
        assert b3b_first.customer_id != b3b_second.customer_id, "Distinct people sharing first+second name merged on phone!"

        # Booking 4: Same id_number ("01019988776") with completely different name -> must raise HTTPException 409
        conflict_raised = False
        try:
            await create_booking(
                BookingCreate(
                    type=BookingType.TRANSPORT,
                    selling_price=Decimal("40000"),
                    paid_amount=Decimal("10000"),
                    currency="YER",
                    transport_details=TransportDetailCreate(
                        transport_company="النور",
                        departure_station="صنعاء",
                        arrival_station="الرياض",
                        travel_date=date(2026, 11, 13),
                        travel_time=time(18, 0),
                        passenger_name="خالد صالح الزهراني",
                        passenger_phone="779988776",
                        id_number="01019988776",
                        birth_date=date(1990, 6, 20),
                        birth_place="عدن",
                    ),
                ),
                _dummy_request(),
                admin,
                db,
            )
        except HTTPException as exc:
            assert exc.status_code == 409, f"Expected 409, got {exc.status_code}"
            conflict_raised = True
        assert conflict_raised, "Expected 409 Conflict when reusing id_number with a different name"

        # Receipt voucher on unpaid Booking 1 -> transitions PENDING to CONFIRMED
        rc_res = await create_receipt_voucher(
            ReceiptVoucherCreate(
                entity_type=EntityType.CUSTOMER,
                entity_id=b1.customer_id,
                amount=Decimal("15000"),
                currency="YER",
                payment_method=PaymentMethod.CASH,
                booking_id=b1.id,
                transaction_date=date.today(),
            ),
            _dummy_request(),
            admin,
            db,
        )
        b1_refreshed = await db.get(BookingModel, b1.id)
        assert b1_refreshed.status == BookingStatus.CONFIRMED, "Receipt did not transition booking to CONFIRMED"

        # Void the receipt voucher -> returns Booking 1 to PENDING
        tx_obj = (
            await db.execute(
                select(FinancialTransaction).where(FinancialTransaction.transaction_id == rc_res["transaction_id"])
            )
        ).scalar_one()
        await void_voucher(tx_obj.id, VoidVoucherRequest(void_reason="اختبار إلغاء"), _dummy_request(), admin, db)
        b1_after_void = await db.get(BookingModel, b1.id)
        assert b1_after_void.status == BookingStatus.PENDING, "Voiding receipt did not return unpaid booking to PENDING"

    await engine.dispose()
    paths = list(app.openapi()["paths"].keys())
    print("TOTAL_ROUTES:", len(paths))
    print("STAGE_4A_FUNCTIONAL_VERIFICATION: PASSED 100%")


if __name__ == "__main__":
    asyncio.run(run_functional_tests())

