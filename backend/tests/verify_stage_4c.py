import asyncio
import os
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException
from main import app
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.database import Base
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.customer import Customer
from app.models.exchange_rate import ExchangeRate
from app.models.financial import EntityType, PaymentMethod
from app.models.user import User, UserRole
from app.schemas.booking import (
    BookingCancelRequest,
    BookingCreate,
    FlightDetailCreate,
    FlightTicketType,
    VisaDetailCreate,
)
from app.api.routes.bookings import cancel_booking, create_booking
from app.api.routes.finance import (
    AllocationItem,
    ReceiptVoucherV2Create,
    create_receipt_voucher_v2,
)
from app.services.accounting_service import (
    backfill_historical_bookings,
    create_entity_accounts,
    create_journal_entry,
    get_account_by_code,
    get_customer_available_credit,
    get_entity_account,
    get_entity_balance,
    init_chart_of_accounts,
)
from app.services.ledger_service import get_ledger_statement


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage4c-verifier"}


async def run_stage_4c_verification():
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
            username="admin",
            password_hash="x",
            full_name="مدير النظام",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        # 1. Test P5 on New Bookings: Create USD Flight (635 USD, paid 580 USD) & SAR Visa (600 SAR, paid 500 SAR)
        fl_res = await create_booking(
            data=BookingCreate(
                type=BookingType.FLIGHT,
                cost_price=Decimal("590.00"),
                selling_price=Decimal("635.00"),
                paid_amount=Decimal("580.00"),
                currency="USD",
                flight_details=FlightDetailCreate(
                    airline_company="اليمنية",
                    flight_number="IY-602",
                    departure_airport="صنعاء",
                    arrival_airport="القاهرة",
                    departure_date=date(2026, 11, 10),
                    departure_time=time(10, 0),
                    ticket_type=FlightTicketType.ONEWAY,
                    passenger_name="هشام عبد الوكيل نعمان",
                    passenger_phone="776522371",
                    passport_number="A99887766",
                    birth_date=date(1990, 1, 1),
                    birth_place="تعز",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        cust_id = fl_res.customer.id
        fl_id = fl_res.id

        vi_res = await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                customer_id=cust_id,
                cost_price=Decimal("520.00"),
                selling_price=Decimal("600.00"),
                paid_amount=Decimal("500.00"),
                currency="SAR",
                visa_details=VisaDetailCreate(
                    visa_type="زيارة عائلية",
                    application_date=date(2026, 11, 2),
                    applicant_name="هشام عبد الوكيل نعمان",
                    applicant_phone="776522371",
                    passport_number="A99887766",
                    birth_date=date(1990, 1, 1),
                    birth_place="تعز",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        vi_id = vi_res.id

        # Check P5 statement before v2 receipt: SAR must show 600 debit and 500 credit (not just 100 debit!)
        st_before = await get_ledger_statement(db, "customer", cust_id)
        sar_ledger_1 = st_before["ledgers"]["SAR"]
        assert sar_ledger_1["total_debit"] == 600.0, f"Expected 600.0 debit, got {sar_ledger_1['total_debit']}"
        assert sar_ledger_1["total_credit"] == 500.0, f"Expected 500.0 credit, got {sar_ledger_1['total_credit']}"
        assert sar_ledger_1["closing_balance"] == 100.0
        assert sar_ledger_1["closing_balance_label"] == "عليه (مدين)"

        # 2. Test P7 Cross-Currency Receipt Voucher V2 (187 SAR -> 100 SAR to VI + 77 SAR to FL (server-derived rate) + 10 SAR unallocated)
        rc_v2 = await create_receipt_voucher_v2(
            data=ReceiptVoucherV2Create(
                entity_type=EntityType.CUSTOMER,
                entity_id=cust_id,
                total_amount=Decimal("187.00"),
                currency="SAR",
                payment_method=PaymentMethod.CASH,
                allocations=[
                    AllocationItem(
                        booking_id=vi_id,
                        allocated_amount=Decimal("100.00"),
                        exchange_rate=Decimal("1.000000"),
                    ),
                    AllocationItem(
                        booking_id=fl_id,
                        allocated_amount=Decimal("77.00"),
                        exchange_rate=Decimal("0.266600"),
                    ),
                ],
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        assert rc_v2["unallocated_balance"] == 10.0

        fl_booking = await db.get(Booking, fl_id)
        # الخادم يتجاهل exchange_rate=0.2666 المرسل ويشتق المعامل من الإعدادات: 77 * 140 / 530 = 20.3396 -> 20.34 USD. المتبقي = 55 - 20.34 = 34.66 USD
        assert Decimal(str(fl_booking.paid_amount)) == Decimal("600.34"), f"Got {fl_booking.paid_amount}"
        assert Decimal(str(fl_booking.remaining_amount)) == Decimal("34.66"), f"Got {fl_booking.remaining_amount}"

        st_after = await get_ledger_statement(db, "customer", cust_id)
        usd_ledger = st_after["ledgers"]["USD"]
        assert usd_ledger["total_debit"] == 635.0
        assert usd_ledger["total_credit"] == 600.34
        assert usd_ledger["closing_balance"] == 34.66
        assert any("77.00 SAR" in e["description"] and "20.34 USD" in e["description"] for e in usd_ledger["entries"]), (
            f"Missing cross-currency detail in USD ledger: {usd_ledger['entries']}"
        )

        sar_ledger_2 = st_after["ledgers"]["SAR"]
        assert sar_ledger_2["closing_balance"] == -10.0
        assert sar_ledger_2["closing_balance_label"] == "له (رصيد دائن)"
        assert any("فائض دفعة مقدمة" in e["description"] for e in sar_ledger_2["entries"])

        # 3-A. Test P6 Available Credit Balance & Auto-Consumption on Next SAR Booking
        avail_sar = await get_customer_available_credit(db, cust_id, "SAR")
        assert avail_sar == Decimal("10.00"), f"Expected 10.00 SAR available credit, got {avail_sar}"

        vi_2 = await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                customer_id=cust_id,
                cost_price=Decimal("100.00"),
                selling_price=Decimal("150.00"),
                paid_amount=Decimal("100.00"),
                currency="SAR",
                visa_details=VisaDetailCreate(
                    visa_type="عمرة",
                    application_date=date(2026, 11, 3),
                    applicant_name="هشام عبد الوكيل نعمان",
                    applicant_phone="776522371",
                    passport_number="A99887766",
                    birth_date=date(1990, 1, 1),
                    birth_place="تعز",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        # Paid 100 cash + 10 available credit = 110 paid, 10 credit_applied, 40 remaining!
        assert Decimal(str(vi_2.paid_amount)) == Decimal("110.00"), f"Expected 110.00 paid, got {vi_2.paid_amount}"
        assert Decimal(str(vi_2.credit_applied)) == Decimal("10.00"), f"Expected 10.00 credit_applied, got {vi_2.credit_applied}"
        assert Decimal(str(vi_2.remaining_amount)) == Decimal("40.00"), f"Expected 40.00 remaining, got {vi_2.remaining_amount}"
        avail_sar_after = await get_customer_available_credit(db, cust_id, "SAR")
        assert avail_sar_after == Decimal("0.00"), f"Expected 0.00 SAR credit remaining, got {avail_sar_after}"

        # 3-B. Test Cancelling Booking that Consumed Credit Balance (Mandatory Check #1)
        # First verify refunding > cash_paid (105 > 100) is rejected with 400
        over_refund_blocked = False
        try:
            await cancel_booking(
                id=vi_2.id,
                data=BookingCancelRequest(reason="اختبار تجاوز النقد", refund_amount=Decimal("105.00")),
                request=req,
                current_user=admin,
                db=db,
            )
        except HTTPException as exc:
            assert exc.status_code == 400
            over_refund_blocked = True
        assert over_refund_blocked, "Expected 400 when refund_amount exceeds cash_paid_amt (100.00 SAR)"

        # Now cancel vi_2 with 80.00 SAR cash refund (20.00 SAR penalty retained)
        await cancel_booking(
            id=vi_2.id,
            data=BookingCancelRequest(reason="إلغاء مع استعادة الرصيد الدائن", refund_amount=Decimal("80.00")),
            request=req,
            current_user=admin,
            db=db,
        )
        # Customer's SAR balance must return to -10.00 SAR (available credit = 10.00 SAR)!
        sar_bal_after_cancel = await get_entity_balance(db, "customer", cust_id, "SAR")
        avail_sar_restored = await get_customer_available_credit(db, cust_id, "SAR")
        assert sar_bal_after_cancel == Decimal("-10.00"), f"Expected -10.00 SAR balance after cancel, got {sar_bal_after_cancel}"
        assert avail_sar_restored == Decimal("10.00"), f"Expected 10.00 SAR credit restored after cancel, got {avail_sar_restored}"

        # 4. Test Historical Booking Backfill (simulating old-style booking where only remaining was debited to cust_acc)
        old_cust = Customer(name="عميل قديم", phone_number="771234567", balance=Decimal("0.00"))
        db.add(old_cust)
        await db.commit()
        await db.refresh(old_cust)
        await create_entity_accounts(db, "customer", old_cust.id, old_cust.name)

        old_b = Booking(
            booking_id="PA-0099",
            ticket_number="PA-0099",
            type=BookingType.PASSPORT,
            customer_id=old_cust.id,
            employee_id=admin.id,
            cost_price=Decimal("30000.00"),
            selling_price=Decimal("50000.00"),
            paid_amount=Decimal("35000.00"),
            remaining_amount=Decimal("15000.00"),
            currency="YER",
            status=BookingStatus.CONFIRMED,
        )
        db.add(old_b)
        await db.flush()

        cash_yer = await get_account_by_code(db, "1101-YER")
        sales_yer = await get_account_by_code(db, "4101-YER")
        old_cust_yer = await get_entity_account(db, "customer", old_cust.id, "YER", old_cust.name)
        await create_journal_entry(
            session=db,
            entry_number="JE-OLD-0099",
            reference_type="BOOKING",
            reference_id="PA-0099",
            currency="YER",
            description="قيد حجز PA-0099 قديم",
            lines_data=[
                {"account_id": sales_yer.id, "debit": Decimal("0.0000"), "credit": Decimal("50000.0000")},
                {"account_id": cash_yer.id, "debit": Decimal("35000.0000"), "credit": Decimal("0.0000")},
                {"account_id": old_cust_yer.id, "debit": Decimal("15000.0000"), "credit": Decimal("0.0000")},
            ],
        )
        await db.commit()

        bf_stats = await backfill_historical_bookings(db)
        await db.commit()
        assert bf_stats["backfilled_bookings"] == 1

        old_st = await get_ledger_statement(db, "customer", old_cust.id, currency="YER")
        yer_l = old_st["ledgers"]["YER"]
        assert yer_l["total_debit"] == 50000.0, f"Expected 50000.0 debit after backfill, got {yer_l['total_debit']}"
        assert yer_l["total_credit"] == 35000.0, f"Expected 35000.0 credit after backfill, got {yer_l['total_credit']}"
        assert yer_l["closing_balance"] == 15000.0
        assert len(yer_l["entries"]) == 2

    await engine.dispose()

    # 5. Verify 0 files in the repository have UTF-8 BOM (\xef\xbb\xbf)
    root_dir = Path(__file__).resolve().parent.parent.parent
    exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json", ".md"}
    bom_files = []
    for r, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "dist", "__pycache__"}]
        for fn in files:
            fp = Path(r) / fn
            if fp.suffix.lower() in exts and fp.read_bytes().startswith(b"\xef\xbb\xbf"):
                bom_files.append(str(fp.relative_to(root_dir)))
    assert not bom_files, f"UTF-8 BOM detected in files: {bom_files}"

    paths = list(app.openapi()["paths"].keys())
    print("TOTAL_ROUTES:", len(paths))
    print("UTF8_BOM_FILES_COUNT: 0")
    print("STAGE_4C_FUNCTIONAL_VERIFICATION: PASSED 100%")


if __name__ == "__main__":
    asyncio.run(run_stage_4c_verification())
