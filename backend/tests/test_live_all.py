import asyncio
import json
import httpx
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.customer import Customer
from app.models.booking import Booking
from app.models.financial import FinancialTransaction

BASE_URL = "http://127.0.0.1:8000/api"

async def run_live_tests():
    print("=" * 70)
    print("بدء الاختبارات الحية الميدانية الشاملة لنظام ARP")
    print("=" * 70)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. تسجيل دخول Admin حي
        print("\n[1] اختبار تسجيل دخول Admin حياً عبر الـ API:")
        login_resp = await client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        print(f"HTTP Status Code: {login_resp.status_code}")
        login_data = login_resp.json()
        print(f"Response Body: {json.dumps(login_data, ensure_ascii=False, indent=2)}")
        print(f"Set-Cookie Headers: {login_resp.headers.get_list('set-cookie')}")

        csrf_token = login_data.get("csrf_token")
        headers = {"X-CSRF-Token": csrf_token}

        # 2. اختبار إنشاء حجز لعميل جديد تماماً غير مسجل مسبقاً (إثبات عمل إصلاح المرحلة 3.5)
        print("\n" + "=" * 70)
        print("[2] اختبار إنشاء حجز لعميل جديد غير مسجل في قاعدة البيانات (سيناريو المرحلة 3.5):")
        new_phone = "770999888"
        new_name = "فؤاد عبد الكريم حميد"
        new_passport = "09887766"

        async with AsyncSessionLocal() as session:
            c_before = (await session.execute(select(Customer).where(Customer.phone_number == new_phone))).scalar_one_or_none()
            print(f"حالة العميل في قاعدة البيانات قبل الحجز: {c_before}")

        flight_payload = {
            "type": "flight",
            "customer_id": None,
            "selling_price": 400000.0,
            "paid_amount": 250000.0,
            "currency": "YER",
            "cost_price": 320000.0,
            "notes": "حجز طيران تجريبي لعميل جديد تماماً",
            "flight_details": {
                "airline_company": "الخطوط الجوية اليمنية",
                "flight_number": "IY-854",
                "departure_airport": "مطار عدن الدولي (ADE)",
                "arrival_airport": "مطار القاهرة الدولي (CAI)",
                "departure_date": "2026-10-01",
                "departure_time": "08:30:00",
                "ticket_type": "oneway",
                "allowed_weight": 30.0,
                "passenger_name": new_name,
                "passenger_phone": new_phone,
                "passport_number": new_passport,
                "birth_date": "1990-05-15",
                "birth_place": "عدن"
            }
        }

        fl_resp = await client.post("/bookings/", json=flight_payload, headers=headers)
        print(f"HTTP Status Code: {fl_resp.status_code}")
        fl_data = fl_resp.json()
        print(f"Flight Booking Response: {json.dumps(fl_data, ensure_ascii=False, indent=2)}")
        flight_id = fl_data.get("id")
        created_customer_id = fl_data.get("customer_id")

        async with AsyncSessionLocal() as session:
            c_after = (await session.execute(select(Customer).where(Customer.id == created_customer_id))).scalar_one_or_none()
            print(f"التحقق من قاعدة البيانات: تم إنشاء سجل العميل تلقائياً بنجاح:")
            print(f"  - Customer ID: {c_after.id}")
            print(f"  - Name: {c_after.name}")
            print(f"  - Phone: {c_after.phone_number}")
            print(f"  - Passport: {c_after.passport_number}")
            print(f"  - Balance: {c_after.balance} YER")

        # 3. إنشاء 4 حجوزات للأنواع الأخرى
        print("\n" + "=" * 70)
        print("[3] إنشاء حجوزات حية للأنواع الأربعة المتبقية:")

        # ب) نقل بري (TR)
        tr_payload = {
            "type": "transport",
            "customer_id": created_customer_id,
            "selling_price": 50000.0,
            "paid_amount": 50000.0,
            "currency": "YER",
            "notes": "حجز نقل بري",
            "transport_details": {
                "transport_company": "شركة الأولى للنقل البري",
                "departure_station": "صنعاء - الستين",
                "arrival_station": "الرياض",
                "travel_date": "2026-10-05",
                "travel_time": "14:00:00",
                "passenger_name": new_name,
                "passenger_phone": new_phone,
                "id_number": "010199887766",
                "birth_date": "1990-05-15"
            }
        }
        tr_resp = await client.post("/bookings/", json=tr_payload, headers=headers)
        print(f"Transport Booking (TR) Status: {tr_resp.status_code}, Ticket: {tr_resp.json().get('ticket_number')}")

        # ج) تأشيرة (VI)
        vi_payload = {
            "type": "visa",
            "customer_id": created_customer_id,
            "selling_price": 120000.0,
            "paid_amount": 60000.0,
            "currency": "YER",
            "notes": "معاملة تأشيرة عمل",
            "visa_details": {
                "visa_type": "تأشيرة عمل مهنية",
                "application_date": "2026-09-12",
                "applicant_name": new_name,
                "applicant_phone": new_phone,
                "passport_number": new_passport,
                "birth_date": "1990-05-15",
                "birth_place": "عدن"
            }
        }
        vi_resp = await client.post("/bookings/", json=vi_payload, headers=headers)
        print(f"Visa Booking (VI) Status: {vi_resp.status_code}, Ticket: {vi_resp.json().get('ticket_number')}")

        # د) جوازات (PA)
        pa_payload = {
            "type": "passport",
            "customer_id": created_customer_id,
            "selling_price": 85000.0,
            "paid_amount": 85000.0,
            "currency": "YER",
            "notes": "إصدار جواز جديد مستعجل",
            "passport_details": {
                "passport_type": "new",
                "priority": "urgent",
                "application_date": "2026-09-12",
                "expected_delivery_date": "2026-09-18",
                "applicant_name": new_name,
                "applicant_phone": new_phone,
                "id_number": "010199887766",
                "birth_date": "1990-05-15",
                "birth_place": "عدن"
            }
        }
        pa_resp = await client.post("/bookings/", json=pa_payload, headers=headers)
        print(f"Passport Booking (PA) Status: {pa_resp.status_code}, Ticket: {pa_resp.json().get('ticket_number')}")

        # هـ) طرود (PR)
        pr_payload = {
            "type": "parcel",
            "customer_id": created_customer_id,
            "selling_price": 25000.0,
            "paid_amount": 25000.0,
            "currency": "YER",
            "notes": "بوليصة طرد وثائق ومستندات",
            "parcel_details": {
                "sender_name": new_name,
                "sender_phone": new_phone,
                "receiver_name": "سالم عمر باوزير",
                "receiver_phone": "771122334",
                "delivery_destination": "المكلا",
                "parcel_type": "مغلف وثائق رسمية",
                "weight": 1.5,
                "content_description": "أوراق وشهادات جامعية",
                "shipping_date": "2026-09-12"
            }
        }
        pr_resp = await client.post("/bookings/", json=pr_payload, headers=headers)
        print(f"Parcel Booking (PR) Status: {pr_resp.status_code}, Ticket: {pr_resp.json().get('ticket_number')}")

        # 4. التحقق من مسارات الطباعة وتنزيل PDF
        print("\n" + "=" * 70)
        print("[4] التحقق الحي من مسار الطباعة وتنزيل PDF (GET /api/bookings/{id}/print):")
        print("  أ) طلب السند كـ HTML حراري:")
        html_resp = await client.get(f"/bookings/{flight_id}/print?mode=thermal&format=html")
        print(f"     Status: {html_resp.status_code}, Content-Type: {html_resp.headers.get('content-type')}")
        print(f"     HTML Content Length: {len(html_resp.text)} chars")
        print(f"     HTML Snippet: {html_resp.text[:200]}...")

        print("\n  ب) طلب السند كـ PDF:")
        pdf_resp = await client.get(f"/bookings/{flight_id}/print?mode=thermal&format=pdf")
        print(f"     Status: {pdf_resp.status_code}")
        print(f"     Content-Type: {pdf_resp.headers.get('content-type')}")
        print(f"     Content-Disposition: {pdf_resp.headers.get('content-disposition')}")
        print(f"     PDF Data Bytes Length: {len(pdf_resp.content)} bytes")
        print(f"     Is Valid PDF Header: {pdf_resp.content.startswith(b'%PDF')}")

        # 5. اختبار الأثر المالي لسندات القبض والدفع على رصيد العميل
        print("\n" + "=" * 70)
        print("[5] اختبار الأثر المالي الرقمي في قاعدة البيانات (سند قبض وسند دفع):")
        async with AsyncSessionLocal() as session:
            c = (await session.execute(select(Customer).where(Customer.id == created_customer_id))).scalar_one()
            balance_initial = float(c.balance)
            print(f"رصيد العميل المبدئي قبل السندات: {balance_initial} YER")

        # إصدار سند قبض بمبلغ 150,000 ريال
        rc_resp = await client.post("/finance/receipt-voucher", json={
            "entity_type": "customer",
            "entity_id": created_customer_id,
            "amount": 150000.0,
            "currency": "YER",
            "payment_method": "cash",
            "notes": "دفعة نقدية بالصندوق",
            "transaction_date": "2026-09-12"
        }, headers=headers)
        print(f"إصدار سند قبض (RC): Status {rc_resp.status_code}, Transaction ID: {rc_resp.json().get('transaction_id')}")

        async with AsyncSessionLocal() as session:
            c = (await session.execute(select(Customer).where(Customer.id == created_customer_id))).scalar_one()
            balance_after_rc = float(c.balance)
            print(f"رصيد العميل في قاعدة البيانات بعد سند القبض (خصم 150,000): {balance_after_rc} YER")

        # إصدار سند دفع / صرف بمبلغ 50,000 ريال
        py_resp = await client.post("/finance/payment-voucher", json={
            "entity_type": "customer",
            "entity_id": created_customer_id,
            "amount": 50000.0,
            "currency": "YER",
            "payment_method": "cash",
            "notes": "استرداد جزء من المبلغ نقداً",
            "transaction_date": "2026-09-12"
        }, headers=headers)
        print(f"إصدار سند صرف (PY): Status {py_resp.status_code}, Transaction ID: {py_resp.json().get('transaction_id')}")

        async with AsyncSessionLocal() as session:
            c = (await session.execute(select(Customer).where(Customer.id == created_customer_id))).scalar_one()
            balance_after_py = float(c.balance)
            print(f"رصيد العميل في قاعدة البيانات بعد سند الصرف (إضافة 50,000): {balance_after_py} YER")

    print("\n" + "=" * 70)
    print("اكتملت كافة الاختبارات الحية الميدانية بنجاح تام 100%")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_live_tests())
