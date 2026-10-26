import sys
import os
import asyncio
import json
from decimal import Decimal
import jwt
import httpx
from sqlalchemy import select, func

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, decode_token
from app.models.accounting import (
    Account,
    AccountCurrency,
    AccountType,
    JournalEntry,
    JournalEntryLine,
)
from app.models.customer import Customer
from app.services.accounting_service import (
    AccountingMismatchException,
    create_journal_entry,
    get_account_by_code,
    get_entity_balance,
)
from app.services.counter_service import get_next_reference_number


async def test_1_pyjwt():
    print("======================================================================")
    print("1. اختبار منظومة الأمان والتوكنات عبر PyJWT المحدثة")
    print("======================================================================")
    subject_id = "1"
    token = create_access_token(subject_id)
    print(f"Generated PyJWT Access Token: {token[:35]}... (Length: {len(token)})")

    decoded = decode_token(token)
    print(f"Decoded Token Payload: {decoded}")
    assert decoded is not None
    assert decoded.get("sub") == "1"
    assert decoded.get("type") == "access"

    # Test invalid token handling
    invalid_decoded = decode_token(token + "tampered")
    print(f"Tampered Token Decode Result: {invalid_decoded} (Expected: None)")
    assert invalid_decoded is None
    print("نتيجة اختبار PyJWT: نجاح كامل 100% بدون استثناءات غير معالجة.")


async def test_2_alembic_and_backfill():
    print("\n======================================================================")
    print("2. التحقق من تطبيق ترحيلات Alembic والترحيل الآمن للبيانات السابقة (Backfill)")
    print("======================================================================")
    async with AsyncSessionLocal() as session:
        # Check accounts count
        acc_count = (await session.execute(select(func.count(Account.id)))).scalar_one()
        print(f"إجمالي الحسابات المسجلة في دليل الحسابات: {acc_count}")

        # Check opening journal entry
        je_res = await session.execute(
            select(JournalEntry).where(JournalEntry.entry_number == "JE-OPENING-0001")
        )
        opening_je = je_res.scalar_one_or_none()
        if opening_je:
            print(f"تم العثور على القيد الافتتاحي: {opening_je.entry_number} ({opening_je.description})")
            lines_res = await session.execute(
                select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == opening_je.id)
            )
            lines = lines_res.scalars().all()
            print(f"عدد أسطر القيد الافتتاحي: {len(lines)}")
            tot_d = sum(l.debit_base for l in lines)
            tot_c = sum(l.credit_base for l in lines)
            print(f"إجمالي المدين الأساسي: {tot_d} YER | إجمالي الدائن الأساسي: {tot_c} YER | الفارق: {tot_d - tot_c}")
            assert tot_d == tot_c
        else:
            print("لم توجد أرصدة سابقة تتطلب قيداً افتتاحياً أو تم الترحيل مسبقاً.")


async def test_3_concurrency_counter():
    print("\n======================================================================")
    print("3. اختبار القفل التشاؤمي والتزامن الصارم على العداد (Concurrency Test)")
    print("======================================================================")
    prefix = "FL"

    async def get_counter_in_session():
        async with AsyncSessionLocal() as s:
            val = await get_next_reference_number(s, prefix)
            await s.commit()
            return val

    # Launch 5 concurrent requests simultaneously
    results = await asyncio.gather(*[get_counter_in_session() for _ in range(5)])
    print(f"الأرقام التسلسلية المتولدة بالتوازي المتزامن (5 طلبات في نفس اللحظة):")
    for idx, r in enumerate(results, 1):
        print(f"  - Request {idx}: {r}")

    unique_results = set(results)
    print(f"عدد الأرقام الفريدة: {len(unique_results)} من أصل 5")
    assert len(unique_results) == 5, "خطأ: حدث تكرار في الأرقام المتزامنة!"
    print("نتيجة اختبار التزامن: نجاح كامل (Zero Collisions / Zero Duplicates) بفضل with_for_update().")


async def test_4_booking_balanced_journal():
    print("\n======================================================================")
    print("4. اختبار إنشاء حجز حي والتحقق من القيد المزدوج المتزن (Debit = Credit)")
    print("======================================================================")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        csrf_token = login_res.json()["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf_token

        booking_payload = {
            "type": "flight",
            "cost_price": 280000.0,
            "selling_price": 350000.0,
            "paid_amount": 200000.0,
            "currency": "YER",
            "notes": "حجز طيران تجريبي للتحقق من القيد المزدوج",
            "flight_details": {
                "airline_company": "طيران اليمنية",
                "flight_number": "IY-600",
                "departure_airport": "صنعاء (SAH)",
                "arrival_airport": "عمان (AMM)",
                "departure_date": "2026-11-01",
                "departure_time": "10:00:00",
                "ticket_type": "oneway",
                "allowed_weight": 30.0,
                "passenger_name": "ياسر أحمد المحاسبي",
                "passenger_phone": "771888111",
                "passport_number": "P00192837",
                "birth_date": "1990-05-15",
                "birth_place": "صنعاء",
            }
        }

        b_res = await client.post("/api/bookings/", json=booking_payload)
        print(f"HTTP Status: {b_res.status_code}")
        b_data = b_res.json()
        booking_ticket = b_data["ticket_number"]
        cust_id = b_data["customer"]["id"]
        print(f"تم إنشاء الحجز بنجاح: {booking_ticket} للعميل رقم {cust_id} ({b_data['customer']['name']})")

    # Inspect General Ledger for this booking
    async with AsyncSessionLocal() as session:
        je_res = await session.execute(
            select(JournalEntry).where(JournalEntry.reference_id == booking_ticket)
        )
        je = je_res.scalar_one()
        print(f"\nقيد اليومية المسجل للحجز:")
        print(f"  - رقم القيد: {je.entry_number}")
        print(f"  - نوع المرجع: {je.reference_type} | المرجع: {je.reference_id}")
        print(f"  - البيان: {je.description}")

        lines_res = await session.execute(
            select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == je.id)
        )
        lines = lines_res.scalars().all()

        print("\nأسطر قيد اليومية (Double-Entry Ledger Lines):")
        total_d_base = Decimal("0.0000")
        total_c_base = Decimal("0.0000")

        for idx, line in enumerate(lines, 1):
            acc = (await session.execute(select(Account).where(Account.id == line.account_id))).scalar_one()
            print(
                f"  [{idx}] حساب ({acc.code} - {acc.name}) | "
                f"مدين: {line.debit} YER | دائن: {line.credit} YER | "
                f"مدين أساسي: {line.debit_base} YER | دائن أساسي: {line.credit_base} YER"
            )
            total_d_base += line.debit_base
            total_c_base += line.credit_base

        diff = total_d_base - total_c_base
        print(f"\nالتحقق الحسابي الرياضي من توازن القيد:")
        print(f"  - إجمالي المدين الأساسي: {total_d_base} YER")
        print(f"  - إجمالي الدائن الأساسي: {total_c_base} YER")
        print(f"  - فارق المعادلة المحاسبية (Sum Debit - Sum Credit): {diff} YER")
        assert diff == Decimal("0.0000"), "خطأ فادح: القيد غير متوازن!"
        print("نتيجة اختبار توازن القيد المزدوج: تطابق تام 100% (Sum Debit == Sum Credit).")

        # Dynamic balance verification
        cust_bal = await get_entity_balance(session, "customer", cust_id, "YER")
        print(f"\nرصيد العميل المحتسب ديناميكياً من واقع دفتر الأستاذ العام: {cust_bal} YER")
        assert cust_bal >= Decimal("150000.00")
        print("نجاح التحقق من رصيد العميل الديناميكي من قيود دفتر الأستاذ.")


async def test_5_rounding_differences():
    print("\n======================================================================")
    print("5. اختبار التسوية التلقائية لفروقات التقريب الصغرى (Rounding Differences <= 0.05)")
    print("======================================================================")
    async with AsyncSessionLocal() as session:
        rounding_acc = await get_account_by_code(session, "5901-YER")
        cash_acc = await get_account_by_code(session, "1101-YER")
        sales_acc = await get_account_by_code(session, "4101-YER")

        # Test case A: Imbalance of 0.03 YER (<= 0.05 tolerance)
        test_lines = [
            {"account_id": cash_acc.id, "debit": Decimal("100.0300"), "credit": Decimal("0.0000"), "debit_base": Decimal("100.0300"), "credit_base": Decimal("0.0000")},
            {"account_id": sales_acc.id, "debit": Decimal("0.0000"), "credit": Decimal("100.0000"), "debit_base": Decimal("0.0000"), "credit_base": Decimal("100.0000")},
        ]
        je_test_ref = await get_next_reference_number(session, "JE")
        je_auto = await create_journal_entry(
            session=session,
            entry_number=je_test_ref,
            reference_type="TEST",
            reference_id="ROUND-01",
            currency="YER",
            description="اختبار تسوية فروقات تقريب صغرى 0.03 YER",
            lines_data=test_lines,
        )
        await session.commit()

        # Check lines of je_auto
        async with AsyncSessionLocal() as s2:
            lines = (await s2.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == je_auto.id))).scalars().all()
            print(f"تم إنشاء القيد {je_auto.entry_number} بنجاح مع أسطره التلقائية ({len(lines)} أسطر):")
            has_rounding_line = False
            for l in lines:
                acc = (await s2.execute(select(Account).where(Account.id == l.account_id))).scalar_one()
                print(f"  - {acc.code}: مدين {l.debit_base} | دائن {l.credit_base}")
                if acc.code == "5901-YER":
                    has_rounding_line = True
                    assert l.credit_base == Decimal("0.0300")
            assert has_rounding_line
            print("نجاح التسوية التلقائية للفروقات الصغرى بنجاح لحساب 5901-YER.")

        # Test case B: Imbalance of 0.20 YER (> 0.05 tolerance) -> Should raise AccountingMismatchException
        try:
            invalid_lines = [
                {"account_id": cash_acc.id, "debit": Decimal("100.2000"), "credit": Decimal("0.0000"), "debit_base": Decimal("100.2000"), "credit_base": Decimal("0.0000")},
                {"account_id": sales_acc.id, "debit": Decimal("0.0000"), "credit": Decimal("100.0000"), "debit_base": Decimal("0.0000"), "credit_base": Decimal("100.0000")},
            ]
            async with AsyncSessionLocal() as s3:
                await create_journal_entry(
                    session=s3,
                    entry_number="JE-FAIL-01",
                    reference_type="TEST",
                    reference_id="ROUND-FAIL",
                    currency="YER",
                    description="اختبار رفض فارق غير مسموح",
                    lines_data=invalid_lines,
                )
            print("خطأ: تم تمرير قيد غير متوازن أكبر من 0.05 دون استثناء!")
            assert False
        except AccountingMismatchException as e:
            print(f"تم رفض القيد غير المتوازن بنجاح عبر AccountingMismatchException: {e}")


async def test_6_cancellation_journal():
    print("\n======================================================================")
    print("6. اختبار إلغاء حجز والتحقق من قيد الإلغاء العكسي المتزن 100%")
    print("======================================================================")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        csrf_token = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf_token}

        # Create a booking specifically to cancel
        unique_passport = f"PCANCEL_{int(asyncio.get_event_loop().time() * 1000)}"
        booking_payload = {
            "type": "flight",
            "cost_price": 50000.0,
            "selling_price": 70000.0,
            "paid_amount": 40000.0,
            "currency": "YER",
            "notes": "حجز لفحص قيد الإلغاء العكسي",
            "flight_details": {
                "airline_company": "طيران بلقيس",
                "flight_number": "BQ-200",
                "departure_airport": "عدن (ADE)",
                "arrival_airport": "القاهرة (CAI)",
                "departure_date": "2026-12-01",
                "departure_time": "14:00:00",
                "ticket_type": "oneway",
                "allowed_weight": 25.0,
                "passenger_name": "سامي عبدالله المالي",
                "passenger_phone": "772223334",
                "passport_number": unique_passport,
                "birth_date": "1992-08-20",
                "birth_place": "عدن",
            },
        }
        b_res = await client.post("/api/bookings/", json=booking_payload, headers=headers)
        assert b_res.status_code == 201
        b_data = b_res.json()
        b_id = b_data["id"]
        b_ticket = b_data["ticket_number"]
        cust_id = b_data["customer"]["id"]
        print(f"تم إنشاء الحجز المراد إلغاؤه: {b_ticket} (ID: {b_id})")

        # Cancel the booking with partial refund (refund 30,000 out of 40,000 paid -> 10,000 cancellation fee retained)
        cancel_res = await client.post(
            f"/api/bookings/{b_id}/cancel",
            json={"reason": "إلغاء لظروف خاصة للراكب", "refund_amount": 30000.0},
            headers=headers,
        )
        assert cancel_res.status_code == 200
        print(f"تم تنفيذ إلغاء الحجز عبر API بنجاح: {cancel_res.json()['message']}")

    # Inspect the reverse journal entry
    async with AsyncSessionLocal() as session:
        je_res = await session.execute(
            select(JournalEntry).where(
                JournalEntry.reference_type == "CANCEL",
                JournalEntry.reference_id == b_ticket,
            )
        )
        cancel_je = je_res.scalar_one()
        print(f"\nقيد الإلغاء العكسي في دفتر الأستاذ العام:")
        print(f"  - رقم القيد: {cancel_je.entry_number}")
        print(f"  - المرجع: {cancel_je.reference_id} | البيان: {cancel_je.description}")

        lines_res = await session.execute(
            select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == cancel_je.id)
        )
        lines = lines_res.scalars().all()

        tot_d = Decimal("0.0000")
        tot_c = Decimal("0.0000")
        for idx, line in enumerate(lines, 1):
            acc = (await session.execute(select(Account).where(Account.id == line.account_id))).scalar_one()
            print(f"  [{idx}] {acc.code} ({acc.name}) | مدين: {line.debit_base} YER | دائن: {line.credit_base} YER")
            tot_d += line.debit_base
            tot_c += line.credit_base

        diff = tot_d - tot_c
        print(f"\nتوازن قيد الإلغاء العكسي:")
        print(f"  - إجمالي المدين الأساسي: {tot_d} YER")
        print(f"  - إجمالي الدائن الأساسي: {tot_c} YER")
        print(f"  - الفارق: {diff} YER")
        assert diff == Decimal("0.0000")
        print("نتيجة اختبار قيد الإلغاء العكسي: تطابق تام 100% وإثبات إيراد رسوم الإلغاء.")

        # Customer balance after cancellation: original remaining debt (30,000) cancelled
        cust_bal = await get_entity_balance(session, "customer", cust_id, "YER")
        print(f"رصيد العميل بعد الإلغاء: {cust_bal} YER (مصفى بالكامل = 0.00 YER)")
        assert cust_bal == Decimal("0.00")

    print("\n======================================================================")
    print("اكتملت جميع الاختبارات المحاسبية والأمنية بنجاح 100%!")
    print("======================================================================")


async def main():
    await test_1_pyjwt()
    await test_2_alembic_and_backfill()
    await test_3_concurrency_counter()
    await test_4_booking_balanced_journal()
    await test_5_rounding_differences()
    await test_6_cancellation_journal()


if __name__ == "__main__":
    asyncio.run(main())

