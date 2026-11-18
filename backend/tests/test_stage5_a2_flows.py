import asyncio
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
from app.models.accounting import Account, JournalEntry, JournalEntryLine
from app.models.booking import BookingType
from app.models.booking_details.flight import FlightTicketType
from app.models.exchange_rate import ExchangeRate
from app.models.financial import EntityType, FinancialTransaction, PaymentMethod, TransactionType
from app.models.user import User, UserRole
from app.schemas.booking import BookingCancelRequest, BookingCreate, FlightDetailCreate, VisaDetailCreate
from app.schemas.financial import ExpenseCreate, PaymentVoucherCreate
from app.api.routes.bookings import cancel_booking, create_booking
from app.api.routes.finance import (
    AllocationItem,
    ReceiptVoucherV2Create,
    create_expense,
    create_payment_voucher,
    create_receipt_voucher_v2,
    void_voucher,
    VoidVoucherRequest,
)
from app.services.accounting_service import init_chart_of_accounts


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage5a2-verifier"}


async def _run_5a2_tests():
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

        # 1. Verify 1102-{YER,SAR,USD} bank accounts exist
        acc_codes = set(
            (await db.execute(select(Account.code))).scalars().all()
        )
        for code in ("1102-YER", "1102-SAR", "1102-USD"):
            assert code in acc_codes, f"Missing bank account {code}"

        # 2. Booking with BANK_TRANSFER must route receipt JE to 1102-SAR (NOT 1101-SAR)
        b_bank = await create_booking(
            data=BookingCreate(
                type=BookingType.VISA,
                cost_price=Decimal("400.00"),
                selling_price=Decimal("600.00"),
                paid_amount=Decimal("500.00"),
                currency="SAR",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="KRM-8899",
                visa_details=VisaDetailCreate(
                    visa_type="زيارة",
                    application_date=date(2026, 11, 17),
                    applicant_name="خالد محمد صالح",
                    applicant_phone="771112233",
                    passport_number="P11223344",
                    birth_date=date(1991, 2, 2),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        cust_id = b_bank.customer.id

        rc_tx = (
            await db.execute(
                select(FinancialTransaction).where(FinancialTransaction.booking_id == b_bank.id)
            )
        ).scalar_one()
        assert rc_tx.payment_method == PaymentMethod.BANK_TRANSFER
        assert rc_tx.reference_number == "KRM-8899"
        assert rc_tx.shift_id is None  # Bank transfer does NOT attach to cash shift

        rc_je = (
            await db.execute(
                select(JournalEntry)
                .where(JournalEntry.reference_id == rc_tx.transaction_id)
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
            )
        ).scalar_one()
        debit_codes = {l.account.code for l in rc_je.lines if l.debit > 0}
        assert debit_codes == {"1102-SAR"}, f"Expected 1102-SAR debit, got {debit_codes}"

        # 3. Receipt Voucher V2 with BANK_TRANSFER + unallocated surplus (50 SAR credit)
        rc_v2 = await create_receipt_voucher_v2(
            data=ReceiptVoucherV2Create(
                entity_type=EntityType.CUSTOMER,
                entity_id=cust_id,
                total_amount=Decimal("150.00"),
                currency="SAR",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="KRM-9900",
                allocations=[
                    AllocationItem(
                        booking_id=b_bank.id,
                        allocated_amount=Decimal("100.00"),
                        exchange_rate=Decimal("1.000000"),
                    )
                ],
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        v2_je = (
            await db.execute(
                select(JournalEntry)
                .where(JournalEntry.reference_id == rc_v2["transaction_id"])
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
            )
        ).scalar_one()
        assert {l.account.code for l in v2_je.lines if l.debit > 0} == {"1102-SAR"}

        # 4. Deferred booking (paid_amount=0) still consumes customer's 50 SAR available credit without creating a receipt
        b_def = await create_booking(
            data=BookingCreate(
                type=BookingType.FLIGHT,
                customer_id=cust_id,
                cost_price=Decimal("120.00"),
                selling_price=Decimal("200.00"),
                paid_amount=Decimal("0.00"),
                currency="SAR",
                payment_method=PaymentMethod.CASH,
                use_credit_balance=True,
                flight_details=FlightDetailCreate(
                    airline_company="اليمنية",
                    flight_number="IY-500",
                    departure_airport="صنعاء",
                    arrival_airport="جدة",
                    departure_date=date(2026, 11, 25),
                    departure_time=time(9, 0),
                    ticket_type=FlightTicketType.ONEWAY,
                    passenger_name="خالد محمد صالح",
                    passenger_phone="771112233",
                    passport_number="P11223344",
                    birth_date=date(1991, 2, 2),
                    birth_place="صنعاء",
                ),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        assert Decimal(str(b_def.credit_applied)) == Decimal("50.00")
        assert Decimal(str(b_def.paid_amount)) == Decimal("50.00")
        assert Decimal(str(b_def.remaining_amount)) == Decimal("150.00")
        def_tx = (
            await db.execute(
                select(FinancialTransaction).where(FinancialTransaction.booking_id == b_def.id)
            )
        ).scalar_one_or_none()
        assert def_tx is None, "Deferred booking with 0 cash paid must NOT create a receipt voucher!"

        # 5. Expense & Payment Voucher with BANK_TRANSFER route to 1102-SAR (and do NOT fail on 1101 cash guard)
        ex_res = await create_expense(
            data=ExpenseCreate(
                expense_type="رسوم بنكية",
                amount=Decimal("25.00"),
                currency="SAR",
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="BANK-FEE-1",
                transaction_date=date(2026, 11, 17),
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        ex_je = (
            await db.execute(
                select(JournalEntry)
                .where(JournalEntry.reference_id == ex_res["transaction_id"])
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
            )
        ).scalar_one()
        assert {l.account.code for l in ex_je.lines if l.credit > 0} == {"1102-SAR"}

        # 6. Voiding bank receipt reverses 1102-SAR
        v2_tx = (
            await db.execute(
                select(FinancialTransaction).where(
                    FinancialTransaction.transaction_id == rc_v2["transaction_id"]
                )
            )
        ).scalar_one()
        await void_voucher(
            voucher_id=v2_tx.id,
            data=VoidVoucherRequest(void_reason="اختبار عكس حوالة بنكية"),
            request=req,
            current_user=admin,
            db=db,
        )
        rev_je = (
            await db.execute(
                select(JournalEntry)
                .where(JournalEntry.reference_type == "VOID", JournalEntry.reference_id == v2_tx.transaction_id)
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
            )
        ).scalar_one()
        assert {l.account.code for l in rev_je.lines if l.credit > 0} == {"1102-SAR"}

        # 7. Cancelling bank-transfer booking with payment_method=BANK_TRANSFER credits 1102-SAR (no cash shift)
        await cancel_booking(
            id=b_bank.id,
            data=BookingCancelRequest(
                reason="إلغاء حجز مدفوع بالحوالة",
                refund_amount=Decimal("200.00"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                reference_number="REFUND-KRM-1",
            ),
            request=req,
            current_user=admin,
            db=db,
        )
        cancel_je = (
            await db.execute(
                select(JournalEntry)
                .where(JournalEntry.reference_type == "CANCEL", JournalEntry.reference_id == b_bank.ticket_number)
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
            )
        ).scalar_one()
        cancel_credit_codes = {l.account.code for l in cancel_je.lines if l.credit > 0}
        assert "1102-SAR" in cancel_credit_codes, f"Expected 1102-SAR credit on cancel, got {cancel_credit_codes}"
        assert "1101-SAR" not in cancel_credit_codes, f"1101-SAR must NOT be credited on bank refund: {cancel_credit_codes}"
        refund_tx = (
            await db.execute(
                select(FinancialTransaction).where(
                    FinancialTransaction.booking_id == b_bank.id,
                    FinancialTransaction.type == TransactionType.PAYMENT_OUT,
                )
            )
        ).scalar_one()
        assert refund_tx.payment_method == PaymentMethod.BANK_TRANSFER
        assert refund_tx.reference_number == "REFUND-KRM-1"
        assert refund_tx.shift_id is None

    await engine.dispose()


def test_stage_5a2_payment_channels():
    asyncio.run(_run_5a2_tests())
