"""
اختبارات الدفعة 5-A2:
- فصل الصندوق النقدي (1101) عن الحسابات البنكية وحسابات الصرافة (1102).
- توجيه قيود الحجوزات، سندات القبض، سندات الصرف، والمصروفات حسب قناة السداد.
- الحجز الآجل بدون سند قبض مع بقاء استهلاك الرصيد الدائن فعالاً.
"""
import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from main import app
from app.core.database import Base, get_db
from app.api.deps import get_current_user
from app.api.routes import bookings as bookings_route
from app.core.security import generate_csrf_token
from app.models.cash_shift import CashShift
from app.models.financial import FinancialTransaction, PaymentMethod, TransactionType
from app.models.accounting import JournalEntry, JournalEntryLine, Account
from app.models.booking import Booking, BookingType, BookingStatus
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.models.settings import Settings
from app.models.exchange_rate import ExchangeRate
from app.services.counter_service import init_reference_counters
from app.services.accounting_service import (
    init_chart_of_accounts,
    get_payment_channel_account,
    get_account_by_code,
)

# Ensure standard test fixtures



@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        await init_reference_counters(session)
        # Seed settings and exchange rates
        session.add(Settings(
            office_name="عالم النقل",
            tagline="للسفريات والنقل",
            phone_numbers="778699440",
            default_currency="YER",
        ))
        session.add_all([
            ExchangeRate(from_currency="USD", to_currency="YER", rate=Decimal("530.0000")),
            ExchangeRate(from_currency="SAR", to_currency="YER", rate=Decimal("140.0000")),
            ExchangeRate(from_currency="USD", to_currency="SAR", rate=Decimal("3.7500")),
        ])
        await session.commit()
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def employee_user(db_session):
    user = User(
        username="emp_test_5a2",
        password_hash="fakehash",
        full_name="موظف اختبار 5A2",
        role=UserRole.EMPLOYEE,
        phone_number="771000222",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


_TEST_CSRF_TOKEN = generate_csrf_token()


@pytest_asyncio.fixture
def auth_headers():
    return {
        "Authorization": "Bearer fake-token-5a2",
        "X-CSRF-Token": _TEST_CSRF_TOKEN,
    }


@pytest_asyncio.fixture
async def client(db_session, employee_user):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return employee_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    cookies = {"csrf_token": _TEST_CSRF_TOKEN}
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chart_of_accounts_includes_1102(db_session):
    """التحقق من إنشاء حسابات 1102 في شجرة الحسابات لكل العملات."""
    await init_chart_of_accounts(db_session)
    for curr in ["YER", "SAR", "USD"]:
        acc_1101 = await get_account_by_code(db_session, f"1101-{curr}")
        acc_1102 = await get_account_by_code(db_session, f"1102-{curr}")
        assert acc_1101 is not None, f"1101-{curr} missing"
        assert acc_1102 is not None, f"1102-{curr} missing"
        assert "البنك" in acc_1102.name and "الحوالات" in acc_1102.name


@pytest.mark.asyncio
async def test_get_payment_channel_account_mapping(db_session):
    """التحقق من توجيه كل وسيلة دفع للحساب المحاسبي الصحيح."""
    await init_chart_of_accounts(db_session)
    acc_cash = await get_payment_channel_account(db_session, PaymentMethod.CASH, "YER")
    acc_bank = await get_payment_channel_account(db_session, PaymentMethod.BANK_TRANSFER, "YER")
    acc_check = await get_payment_channel_account(db_session, PaymentMethod.CHECK, "YER")

    assert acc_cash.code == "1101-YER"
    assert acc_bank.code == "1102-YER"
    assert acc_check.code == "1102-YER"


@pytest.mark.asyncio
async def test_booking_cash_vs_bank_transfer(client, db_session, employee_user, auth_headers):
    """
    التحقق من:
    - حجز مسدد نقداً يوجه قيده وسنده إلى 1101 ويرتبط بوردية نشطة.
    - حجز مسدد بتحويل بنكي يوجه قيده وسنده إلى 1102 دون اشتراط وردية الصندوق.
    """
    await init_chart_of_accounts(db_session)

    # 1. إنشاء عميل ومورد
    cust = Customer(name="عميل اختبار 5-A2", phone_number="777991122")
    supp = Supplier(name="طيران اليمنية 5A2", phone_number="777112233", service_type="flight")
    db_session.add_all([cust, supp])
    await db_session.commit()
    await db_session.refresh(cust)
    await db_session.refresh(supp)

    # فتح وردية للموظف لاختبار الدفع النقدي
    from app.services.shift_service import open_shift
    shift = await open_shift(db_session, employee_user.id, starting_balance=Decimal("5000.00"))
    await db_session.commit()

    # أ) حجز نقدي:
    cash_payload = {
        "type": "flight",
        "customer_id": cust.id,
        "supplier_id": supp.id,
        "selling_price": 50000.0,
        "paid_amount": 20000.0,
        "currency": "YER",
        "payment_method": "cash",
        "flight_details": {
            "airline_company": "Yemenia",
            "flight_number": "IY601",
            "departure_airport": "SAH",
            "arrival_airport": "CAI",
            "departure_date": "2026-12-01",
            "departure_time": "10:00",
            "ticket_type": "oneway",
            "passenger_name": "عميل نقدي",
            "passenger_phone": "777991122",
            "passport_number": "P12345678",
            "id_number": "123456",
            "birth_date": "1990-01-01",
            "birth_place": "صنعاء"
        }
    }
    res_cash = await client.post("/api/bookings/", json=cash_payload, headers=auth_headers)
    assert res_cash.status_code == 201, res_cash.text
    cash_booking_id = res_cash.json()["id"]

    # فحص قيد اليومية وسند القبض للحجز النقدي
    cash_rc_stmt = select(FinancialTransaction).where(FinancialTransaction.booking_id == cash_booking_id)
    cash_rc = (await db_session.execute(cash_rc_stmt)).scalar_one_or_none()
    assert cash_rc is not None
    assert cash_rc.payment_method == PaymentMethod.CASH
    assert cash_rc.shift_id == shift.id

    cash_je_stmt = (
        select(JournalEntry)
        .where(JournalEntry.reference_id == cash_rc.transaction_id)
        .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
    )
    cash_je = (await db_session.execute(cash_je_stmt)).scalar_one_or_none()
    assert cash_je is not None
    debit_lines = [l for l in cash_je.lines if l.debit > 0]
    assert len(debit_lines) == 1
    assert debit_lines[0].account.code == "1101-YER"

    # ب) حجز بتحويل بنكي برقم مرجع:
    bank_payload = {
        "type": "flight",
        "customer_id": cust.id,
        "supplier_id": supp.id,
        "selling_price": 60000.0,
        "paid_amount": 30000.0,
        "currency": "YER",
        "payment_method": "bank_transfer",
        "reference_number": "TRANSFER-TR-9988",
        "flight_details": {
            "airline_company": "Yemenia",
            "flight_number": "IY602",
            "departure_airport": "SAH",
            "arrival_airport": "JED",
            "departure_date": "2026-12-05",
            "departure_time": "14:00",
            "ticket_type": "oneway",
            "passenger_name": "عميل تحويل",
            "passenger_phone": "777991122",
            "passport_number": "P87654321",
            "id_number": "654321",
            "birth_date": "1992-05-05",
            "birth_place": "عدن"
        }
    }
    res_bank = await client.post("/api/bookings/", json=bank_payload, headers=auth_headers)
    assert res_bank.status_code == 201, res_bank.text
    bank_booking_id = res_bank.json()["id"]

    # فحص قيد اليومية وسند القبض للحجز البنكي
    bank_rc_stmt = select(FinancialTransaction).where(FinancialTransaction.booking_id == bank_booking_id)
    bank_rc = (await db_session.execute(bank_rc_stmt)).scalar_one_or_none()
    assert bank_rc is not None
    assert bank_rc.payment_method == PaymentMethod.BANK_TRANSFER
    assert bank_rc.reference_number == "TRANSFER-TR-9988"
    assert bank_rc.shift_id is None, "Bank transfer voucher must NOT be linked to a cash shift"

    bank_je_stmt = (
        select(JournalEntry)
        .where(JournalEntry.reference_id == bank_rc.transaction_id)
        .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
    )
    bank_je = (await db_session.execute(bank_je_stmt)).scalar_one_or_none()
    assert bank_je is not None
    bank_debit_lines = [l for l in bank_je.lines if l.debit > 0]
    assert len(bank_debit_lines) == 1
    assert bank_debit_lines[0].account.code == "1102-YER"


@pytest.mark.asyncio
async def test_deferred_booking_with_credit_balance(client, db_session, employee_user, auth_headers):
    """
    التحقق من الحجز الآجل بالكامل:
    - إرسال paid_amount = 0 مع payment_method = cash.
    - عدم إنشاء سند قبض.
    - إذا كان لدى العميل رصيد دائن متاح يتم استهلاكه كـ credit_applied وتوليد قيد تسوية الرصيد الدائن فقط.
    """
    await init_chart_of_accounts(db_session)

    # عميل لديه رصيد دائن مسبق
    cust = Customer(name="عميل دائن 5-A2", phone_number="777884433", balance=Decimal("-15000.00"))
    supp = Supplier(name="مورد نقل 5A2", phone_number="777334455", service_type="transport")
    db_session.add_all([cust, supp])
    await db_session.commit()
    await db_session.refresh(cust)
    await db_session.refresh(supp)

    # إنشاء حسابات العميل وقيد رصيد دائن مسبق في دفتر الأستاذ (15,000 YER)
    from app.services.accounting_service import create_entity_accounts, create_journal_entry, get_entity_account
    await create_entity_accounts(db_session, "customer", cust.id, cust.name)
    cust_acc = await get_entity_account(db_session, "customer", cust.id, "YER")
    cash_acc = await get_account_by_code(db_session, "1101-YER")
    await create_journal_entry(
        session=db_session,
        entry_number="JE-INIT-CREDIT-5A2",
        reference_type="MANUAL",
        reference_id="INIT-5A2",
        currency="YER",
        description="رصيد دائن افتتاحي للعميل",
        lines_data=[
            {"account_id": cash_acc.id, "debit": Decimal("15000.00"), "credit": Decimal("0.00")},
            {"account_id": cust_acc.id, "debit": Decimal("0.00"), "credit": Decimal("15000.00")},
        ]
    )
    await db_session.commit()

    deferred_payload = {
        "type": "transport",
        "customer_id": cust.id,
        "supplier_id": supp.id,
        "selling_price": 40000.0,
        "paid_amount": 0.0,
        "currency": "YER",
        "payment_method": "cash",
        "use_credit_balance": True,
        "transport_details": {
            "transport_company": "Al-Buraq",
            "departure_station": "Sanaa",
            "arrival_station": "Aden",
            "travel_date": "2026-12-10",
            "travel_time": "08:00",
            "passenger_name": "راكب آجل",
            "passenger_phone": "777884433",
            "id_number": "998877",
            "birth_date": "1995-02-02",
            "birth_place": "إب"
        }
    }
    res = await client.post("/api/bookings/", json=deferred_payload, headers=auth_headers)
    assert res.status_code == 201, res.text
    booking_id = res.json()["id"]

    # لا يوجد سند قبض نقدي
    rc_stmt = select(FinancialTransaction).where(FinancialTransaction.booking_id == booking_id)
    rc = (await db_session.execute(rc_stmt)).scalar_one_or_none()
    assert rc is None, "Deferred booking without upfront payment must not create a receipt voucher"

    # التحقق من استهلاك الرصيد الدائن
    b_stmt = select(Booking).where(Booking.id == booking_id)
    b = (await db_session.execute(b_stmt)).scalar_one()
    assert Decimal(str(b.credit_applied)) == Decimal("15000.00")
    assert Decimal(str(b.paid_amount)) in (Decimal("0.00"), Decimal("15000.00"))
    assert Decimal(str(b.remaining_amount)) == Decimal("25000.00")
