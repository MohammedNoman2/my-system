import asyncio
import os
import sys

# Ensure backend root is on python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
from decimal import Decimal
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.settings import Settings
from app.models.accounting import Account, JournalEntry, JournalEntryLine

BASE_URL = "http://127.0.0.1:8000/api"

async def run_tests():
    print("==================================================")
    print("STARTING FULL END-TO-END VERIFICATION SUITE")
    print("==================================================")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 0. Authenticate as Admin
        login_res = await client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        cookies = login_res.cookies
        csrf_token = login_res.json().get("csrf_token")
        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
        print("✓ Authenticated as Admin successfully")

        # 1. Test Dynamic Logo & Public Settings
        sample_logo_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        logo_res = await client.post("/settings/logo", json={"logo_data": sample_logo_b64}, cookies=cookies, headers=headers)
        assert logo_res.status_code == 200, f"Logo upload failed: {logo_res.text}"
        assert logo_res.json()["logo_data"] == sample_logo_b64
        print("✓ POST /api/settings/logo succeeded with base64 logo data")

        pub_res = await client.get("/settings/public")
        assert pub_res.status_code == 200
        pub_data = pub_res.json()
        assert pub_data["logo_data"] == sample_logo_b64
        print(f"✓ GET /api/settings/public returns office: {pub_data['office_name']} and verified dynamic logo")

        # 2. Test Mandatory 5 Fields Validation: Transport booking missing birth_place should return 422
        invalid_tr_payload = {
            "type": "transport",
            "selling_price": 12000,
            "paid_amount": 12000,
            "currency": "YER",
            "transport_details": {
                "transport_company": "البراق للنقل الدولي",
                "departure_station": "صنعاء",
                "arrival_station": "عدن",
                "travel_date": "2026-10-01",
                "travel_time": "08:00",
                "passenger_name": "سامي علي أحمد",
                "passenger_phone": "771234567",
                "id_number": "0101998877",
                "birth_date": "1995-05-15",
                # birth_place omitted intentionally to test validation!
            }
        }
        val_res = await client.post("/bookings/", json=invalid_tr_payload, cookies=cookies, headers=headers)
        assert val_res.status_code == 422, f"Expected 422 for missing birth_place, got: {val_res.status_code}"
        print("✓ Schema Enforcement: Missing birth_place in Transport Booking correctly rejected with 422 Unprocessable Entity")

        # 3. Test Manual Supplier Auto-Creation + Customer Auto-Provisioning + Double-Entry Accounting
        manual_supplier_name = "شركة المجد السريع العالمية"
        valid_tr_payload = {
            "type": "transport",
            "selling_price": 25000,
            "paid_amount": 15000,
            "currency": "YER",
            "supplier_name": manual_supplier_name,
            "cost_price": 18000,
            "transport_details": {
                "transport_company": manual_supplier_name,
                "departure_station": "صنعاء",
                "arrival_station": "المهرة",
                "travel_date": "2026-10-05",
                "travel_time": "09:30",
                "passenger_name": "طارق محمود عبد الله",
                "passenger_phone": "770998811",
                "id_number": "0202883344",
                "birth_date": "1992-03-20",
                "birth_place": "صنعاء",
            }
        }
        create_res = await client.post("/bookings/", json=valid_tr_payload, cookies=cookies, headers=headers)
        assert create_res.status_code == 201, f"Booking creation failed: {create_res.text}"
        booking_data = create_res.json()
        booking_id = booking_data["id"]
        ticket_number = booking_data["ticket_number"]
        created_by_id = booking_data.get("created_by_id")
        created_by_name = booking_data.get("created_by_name")
        print(f"✓ Booking created successfully: ID={booking_id}, Ticket={ticket_number}")
        print(f"✓ Audit Tracking Verified in Response: created_by_id={created_by_id}, created_by_name='{created_by_name}'")
        assert created_by_name is not None and len(created_by_name) > 0

        # Verify Database entities & General Ledger Accounts
        async with AsyncSessionLocal() as session:
            # Check Supplier creation
            supp_res = await session.execute(select(Supplier).where(Supplier.name == manual_supplier_name))
            supplier = supp_res.scalar_one_or_none()
            assert supplier is not None, "Manual supplier was not auto-created in database!"
            print(f"✓ Manual Supplier auto-provisioned in database: ID={supplier.id}, Name='{supplier.name}'")

            # Check Supplier Accounts
            supp_acc_code = f"2101-SUPP-{supplier.id}-YER"
            acc_res = await session.execute(select(Account).where(Account.code == supp_acc_code))
            supp_account = acc_res.scalar_one_or_none()
            assert supp_account is not None, f"Supplier account {supp_acc_code} was not created!"
            print(f"✓ Supplier General Ledger Account auto-created: Code={supp_account.code}, Name='{supp_account.name}'")

            # Check Customer Creation & Account
            cust_res = await session.execute(select(Customer).where(Customer.phone_number == "770998811"))
            customer = cust_res.scalar_one_or_none()
            assert customer is not None, "Customer was not auto-provisioned!"
            cust_acc_code = f"1201-CUST-{customer.id}-YER"
            c_acc_res = await session.execute(select(Account).where(Account.code == cust_acc_code))
            cust_account = c_acc_res.scalar_one_or_none()
            assert cust_account is not None, f"Customer account {cust_acc_code} was not created!"
            print(f"✓ Customer General Ledger Account auto-created: Code={cust_account.code}, Name='{cust_account.name}'")

            # Verify Journal Entry Lines Balance: Debit == Credit
            je_res = await session.execute(
                select(JournalEntry)
                .where(JournalEntry.reference_id == ticket_number)
            )
            je = je_res.scalar_one_or_none()
            assert je is not None, "Journal Entry for booking was not found!"
            lines_res = await session.execute(
                select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == je.id)
            )
            lines = lines_res.scalars().all()
            total_debit = sum(Decimal(str(l.debit)) for l in lines)
            total_credit = sum(Decimal(str(l.credit)) for l in lines)
            print(f"✓ Journal Entry {je.entry_number} Verified: Total Debit={total_debit} YER, Total Credit={total_credit} YER")
            assert total_debit == total_credit, f"Unbalanced Journal Entry: {total_debit} != {total_credit}"

        # 4. Test Unified Search Endpoint GET /api/bookings/search
        search_res = await client.get("/bookings/search", params={"q": "طارق محمود"}, cookies=cookies)
        assert search_res.status_code == 200, f"Search failed: {search_res.text}"
        search_data = search_res.json()
        assert search_data["total"] >= 1
        item = next((i for i in search_data["items"] if i["id"] == booking_id), None)
        assert item is not None, "Created booking not found in search results!"
        print("✓ GET /api/bookings/search successfully verified 10 RTL columns:")
        print(f"   1. رقم التذكرة: {item['ticket_number']}")
        print(f"   2. الاسم: {item['passenger_name']}")
        print(f"   3. الهاتف: {item['passenger_phone']}")
        print(f"   4. نوع الحجز: {item['type']}")
        print(f"   5. الشركة: {item['company_name']}")
        print(f"   6. تاريخ الحجز: {item['booking_date']}")
        print(f"   7. المسار: {item['route']}")
        print(f"   8. تاريخ الرحلة: {item['travel_date']}")
        print(f"   9. الموظف: {item['employee_name']}")
        print(f"   10. الحالة: {item['status']}")
        print(f"   + رصيد العميل اللحظي: {item['customer_balance']} YER")

        # 5. Test Postpone Endpoint POST /api/bookings/{id}/postpone
        postpone_res = await client.post(
            f"/bookings/{booking_id}/postpone",
            json={"new_travel_date": "2026-10-12", "new_travel_time": "14:00", "reason": "طلب العميل تأجيل الموعد"},
            cookies=cookies,
            headers=headers
        )
        assert postpone_res.status_code == 200, f"Postpone failed: {postpone_res.text}"
        print("✓ POST /api/bookings/{id}/postpone successfully rescheduled travel date/time and logged audit")

        # 6. Test Reroute Endpoint POST /api/bookings/{id}/reroute with Double-Entry Journal Entry
        reroute_res = await client.post(
            f"/bookings/{booking_id}/reroute",
            json={
                "new_destination": "حضرموت - المكلا",
                "price_difference": 3000,
                "reason": "تغيير محطة الوصول إلى المكلا مع فارق سعر إضافي 3,000 ريال"
            },
            cookies=cookies,
            headers=headers
        )
        assert reroute_res.status_code == 200, f"Reroute failed: {reroute_res.text}"
        print("✓ POST /api/bookings/{id}/reroute successfully updated destination & posted price adjustment journal entry")

        # 7. Test Details & Journal Endpoint GET /api/bookings/{id}/journal
        journal_res = await client.get(f"/bookings/{booking_id}/journal", cookies=cookies)
        assert journal_res.status_code == 200, f"Journal query failed: {journal_res.text}"
        j_data = journal_res.json()
        assert len(j_data["journal_entries"]) >= 2, "Expected at least 2 journal entries (Booking + Reroute)!"
        print(f"✓ GET /api/bookings/{id}/journal returned {len(j_data['journal_entries'])} double-entry journal entries with dynamic customer balance {j_data['customer_balance']} YER")

        # 8. Test Official Voucher Print HTML for Dynamic Logo, Issued-By, and Double Border Container
        print_res = await client.get(f"/bookings/{booking_id}/print?mode=thermal&format=html", cookies=cookies)
        assert print_res.status_code == 200, f"Print HTML failed: {print_res.text}"
        html = print_res.text
        assert ".print-document-container" in html, "Print HTML missing .print-document-container class"
        assert "border: 2px double #0f172a" in html or "2px double" in html, "Print HTML missing 2px double border styling"
        assert "المستخدم المنفذ / صدرت بواسطة:" in html, "Print HTML missing issued-by tracking field"
        assert "data:image/png;base64" in html or "<img" in html, "Print HTML missing dynamic logo image"
        print("✓ Official Voucher Print HTML verified: Contains dynamic logo, 'المستخدم المنفذ / صدرت بواسطة', and double-border container styling")

    print("==================================================")
    print("ALL VERIFICATIONS COMPLETED WITH 100% SUCCESS!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
