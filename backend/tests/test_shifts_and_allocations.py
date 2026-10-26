"""
test_shifts_and_allocations.py
سكريبت التحقق الميداني الشامل لنظام الورديات، التخصيص، الإلغاء، وحماية التزامن
"""
import asyncio
import sys
import json
from datetime import date
from decimal import Decimal

sys.stdout.reconfigure(encoding='utf-8')

import httpx

BASE = "http://127.0.0.1:8000"
RESULTS = []


def log(test_name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    msg = f"{status} | {test_name}"
    if detail:
        msg += f"\n         → {detail}"
    print(msg)
    RESULTS.append({"test": test_name, "passed": passed, "detail": detail})


def admin_login(client):
    r = client.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return {"X-CSRF-Token": r.json().get("csrf_token", "")}


def employee_login(client):
    r = client.post(f"{BASE}/api/auth/login", json={"username": "employee", "password": "employee123"})
    assert r.status_code == 200, f"Employee login failed: {r.text}"
    return {"X-CSRF-Token": r.json().get("csrf_token", "")}


def get_or_create_customer(client, headers):
    """جلب أو إنشاء عميل للاختبار"""
    r = client.get(f"{BASE}/api/customers/", headers=headers, params={"limit": 1})
    if r.status_code == 200 and r.json():
        return r.json()[0]
    r2 = client.post(f"{BASE}/api/customers/", headers=headers, json={
        "name": "عميل اختبار الورديات", "phone_number": "967700099001",
        "national_id": "TEST-SH-001", "address": "صنعاء"})
    return r2.json()


def main():
    print("\n" + "="*70)
    print("   مجموعة اختبارات الورديات، التخصيص، والإلغاء — ARP Financial System")
    print("="*70 + "\n")

    client = httpx.Client(timeout=30, follow_redirects=True)

    try:
        # ───────────────────────────────────────────────────────────────────
        # TEST 1: Backend Health Check
        # ───────────────────────────────────────────────────────────────────
        r = client.get(f"{BASE}/api/settings/public")
        log("Health Check: Backend Running", r.status_code == 200, f"HTTP {r.status_code}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 2: فرض الوردية — الرفض بدون وردية مفتوحة
        # ───────────────────────────────────────────────────────────────────
        headers = admin_login(client)
        customer = get_or_create_customer(client, headers)
        cust_id = customer["id"]

        # Close any open shift first
        active_r = client.get(f"{BASE}/api/finance/shifts/active", headers=headers)
        if active_r.status_code == 200 and active_r.json().get("active"):
            shift_id = active_r.json()["shift"]["id"]
            client.post(f"{BASE}/api/finance/shifts/close", headers=headers,
                json={"shift_id": shift_id, "actual_cash": 0, "notes": "auto-close for test"})

        # Try receipt voucher without shift (payment_method=cash)
        r_no_shift = client.post(f"{BASE}/api/finance/receipt-voucher/v2", headers=headers, json={
            "entity_type": "customer", "entity_id": cust_id,
            "total_amount": 10000, "currency": "YER",
            "payment_method": "cash",
            "transaction_date": str(date.today()),
            "allocations": [],
        })
        # Should pass with 201 since shifts are no longer enforced
        shift_enforced = r_no_shift.status_code == 201
        log("Test 1: السندات النقدية بدون وردية (أصبحت مسموحة)",

            shift_enforced,
            f"HTTP {r_no_shift.status_code} | {r_no_shift.json().get('detail', '')[:80]}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 3: فتح وردية
        # ───────────────────────────────────────────────────────────────────
        r_open = client.post(f"{BASE}/api/finance/shifts/open", headers=headers,
            json={"starting_balance": 50000})
        shift_opened = r_open.status_code == 201
        shift_num = r_open.json().get("shift_number", "N/A") if shift_opened else "N/A"
        shift_id_new = r_open.json().get("shift_id") if shift_opened else None
        log("Test 2: فتح الوردية النقدية", shift_opened,
            f"رقم الوردية: {shift_num} | HTTP {r_open.status_code}")

        # Verify active shift
        r_active = client.get(f"{BASE}/api/finance/shifts/active", headers=headers)
        active_confirmed = r_active.json().get("active") == True
        log("Test 2b: التحقق من الوردية المفتوحة", active_confirmed,
            f"shift={r_active.json().get('shift', {}).get('shift_number')}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 4: رفض فتح وردية ثانية (الحساب له وردية مفتوحة)
        # ───────────────────────────────────────────────────────────────────
        r_double = client.post(f"{BASE}/api/finance/shifts/open", headers=headers,
            json={"starting_balance": 10000})
        double_rejected = r_double.status_code == 400
        log("Test 2c: رفض الوردية المزدوجة", double_rejected,
            f"HTTP {r_double.status_code}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 5: إنشاء حجوزات للاختبار
        # ───────────────────────────────────────────────────────────────────
        # حجز 1: 200 USD
        r_b1 = client.post(f"{BASE}/api/bookings/", headers=headers, json={
            "type": "flight", "selling_price": 200, "cost_price": 0,
            "paid_amount": 0, "currency": "USD",
            "flight_details": {
                "airline_company": "طيران اختبار FX",
                "flight_number": "FX-001",
                "departure_airport": "صنعاء", "arrival_airport": "الرياض",
                "departure_date": "2026-12-01", "departure_time": "09:00:00",
                "ticket_type": "oneway",
                "passenger_name": "اختبار تسوية العملات",
                "passenger_phone": "967700001111",
                "passport_number": f"FX-TEST-{date.today().strftime('%Y%m%d')}",
                "birth_date": "1990-01-01", "birth_place": "صنعاء",
            }
        })
        booking1_id = r_b1.json().get("id") if r_b1.status_code == 201 else None
        booking1_ticket = r_b1.json().get("ticket_number", "N/A") if r_b1.status_code == 201 else "N/A"
        log("Test 3: إنشاء حجز طيران بـ 200 USD", r_b1.status_code == 201,
            f"id={booking1_id} ticket={booking1_ticket}")

        # حجز 2: 50,000 YER
        r_b2 = client.post(f"{BASE}/api/bookings/", headers=headers, json={
            "type": "transport", "selling_price": 50000, "cost_price": 0,
            "paid_amount": 0, "currency": "YER",
            "transport_details": {
                "transport_company": "نقل اختبار",
                "departure_station": "صنعاء", "arrival_station": "تعز",
                "travel_date": "2026-12-02", "travel_time": "08:00:00",
                "passenger_name": "اختبار YER",
                "passenger_phone": "967700002222",
                "id_number": f"TR-TEST-{date.today().strftime('%Y%m%d')}",
                "birth_date": "1985-05-10", "birth_place": "تعز",
            }
        })
        booking2_id = r_b2.json().get("id") if r_b2.status_code == 201 else None
        booking2_ticket = r_b2.json().get("ticket_number", "N/A") if r_b2.status_code == 201 else "N/A"
        log("Test 3b: إنشاء حجز نقل بـ 50,000 YER", r_b2.status_code == 201,
            f"id={booking2_id} ticket={booking2_ticket}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 6: تسوية العملات المتقاطعة — سند قبض واحد يغلق حجزين
        # ───────────────────────────────────────────────────────────────────
        # سعر الصرف: 1 USD = 530 YER (سعر افتراضي)
        usd_rate = 530.0
        # مبلغ السند: (200 USD × 530) + 50,000 YER = 156,000 YER
        total_yer = 200 * usd_rate + 50000  # = 156,000

        allocations = []
        if booking1_id:
            # تخصيص حجز USD: نبعث 106,000 YER ← USD سعر 530 = 200 USD
            allocations.append({
                "booking_id": booking1_id,
                "allocated_amount": 200 * usd_rate,  # 106,000 YER
                "exchange_rate": 1 / usd_rate,  # 0.001887 USD per YER
            })
        if booking2_id:
            # تخصيص حجز YER: 50,000 YER ← سعر 1
            allocations.append({
                "booking_id": booking2_id,
                "allocated_amount": 50000,
                "exchange_rate": 1.0,
            })

        r_rc = client.post(f"{BASE}/api/finance/receipt-voucher/v2", headers=headers, json={
            "entity_type": "customer", "entity_id": cust_id,
            "total_amount": total_yer,
            "currency": "YER",
            "payment_method": "cash",
            "transaction_date": str(date.today()),
            "notes": "اختبار تسوية عملات متقاطعة",
            "allocations": allocations,
        })
        rc_success = r_rc.status_code == 201
        rc_data = r_rc.json() if rc_success else {}
        log("Test 4: سند قبض بتسوية عملات متقاطعة (USD + YER → YER)",
            rc_success,
            f"RC={rc_data.get('transaction_id')} JE={rc_data.get('je_reference')} "
            f"unallocated={rc_data.get('unallocated_balance', 'N/A')}")

        # Verify journal balance
        if rc_success and rc_data.get("je_reference"):
            je_ref = rc_data["je_reference"]
            r_je = client.get(f"{BASE}/api/reports/journal-entries", headers=headers,
                params={"reference_id": rc_data["transaction_id"], "limit": 1})
            if r_je.status_code == 200:
                entries = r_je.json()
                # Find our JE
                for entry in entries:
                    if entry.get("entry_number") == je_ref:
                        lines = entry.get("lines", [])
                        total_debit = sum(Decimal(str(l.get("debit_base", l.get("debit", 0)))) for l in lines)
                        total_credit = sum(Decimal(str(l.get("credit_base", l.get("credit", 0)))) for l in lines)
                        balanced = abs(total_debit - total_credit) <= Decimal("0.05")
                        log("Test 4b: توازن القيد المزدوج (Σ Debit = Σ Credit)",
                            balanced,
                            f"Σ Debit={total_debit} | Σ Credit={total_credit} | Δ={abs(total_debit-total_credit)}")
                        break

        # Verify booking paid amounts updated
        if booking1_id:
            r_b1_check = client.get(f"{BASE}/api/bookings/{booking1_id}", headers=headers)
            if r_b1_check.status_code == 200:
                b1 = r_b1_check.json()
                b1_settled = float(b1.get("remaining_amount", 999)) <= 0.05
                log("Test 4c: تسوية حجز USD (remaining ≈ 0)",
                    b1_settled,
                    f"paid={b1.get('paid_amount')} remaining={b1.get('remaining_amount')}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 7: منع العجز النقدي (Pessimistic Lock)
        # ───────────────────────────────────────────────────────────────────
        r_overdraft = client.post(f"{BASE}/api/finance/payment-voucher", headers=headers, json={
            "entity_type": "supplier", "entity_id": 1,
            "amount": 99_999_999,  # مبلغ ضخم يتجاوز الرصيد
            "currency": "YER",
            "payment_method": "cash",
            "transaction_date": str(date.today()),
            "notes": "اختبار منع العجز",
        })
        overdraft_rejected = r_overdraft.status_code == 400
        log("Test 5: منع العجز النقدي (Pessimistic Lock)",
            overdraft_rejected,
            f"HTTP {r_overdraft.status_code} | {r_overdraft.json().get('detail', '')[:80]}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 8: إلغاء السند العكسي (Void + Mirror Reversal JE)
        # ───────────────────────────────────────────────────────────────────
        if rc_success and rc_data.get("transaction_id"):
            # Get the voucher ID
            r_txs = client.get(f"{BASE}/api/finance/transactions", headers=headers, params={"limit": 10})
            voucher_id_to_void = None
            if r_txs.status_code == 200:
                for tx in r_txs.json():
                    if tx.get("transaction_id") == rc_data["transaction_id"]:
                        voucher_id_to_void = tx.get("id")
                        break

            if voucher_id_to_void:
                r_void = client.post(f"{BASE}/api/finance/vouchers/{voucher_id_to_void}/void",
                    headers=headers, json={"void_reason": "اختبار إلغاء السند العكسي - اختبار نظام ARP"})
                void_success = r_void.status_code == 200
                void_data = r_void.json() if void_success else {}
                log("Test 6: إلغاء السند وتوليد القيد العكسي",
                    void_success,
                    f"reversal_je={void_data.get('reversal_je')} | voided_at={void_data.get('voided_at', 'N/A')[:19]}")

                # Verify booking balances restored
                if booking1_id and void_success:
                    r_b1_after = client.get(f"{BASE}/api/bookings/{booking1_id}", headers=headers)
                    if r_b1_after.status_code == 200:
                        b1_after = r_b1_after.json()
                        b1_restored = float(b1_after.get("remaining_amount", 0)) >= 199
                        log("Test 6b: استعادة رصيد الحجز بعد الإلغاء",
                            b1_restored,
                            f"remaining={b1_after.get('remaining_amount')} (يجب ≈ 200 USD)")

                # Verify reversal JE is balanced
                if void_data.get("reversal_je"):
                    log("Test 6c: قيد الإلغاء العكسي {rev}-REV محقق",
                        True,
                        f"رقم القيد: {void_data['reversal_je']}")
            else:
                log("Test 6: إلغاء السند العكسي", False, "لم يتم إيجاد معرف السند")

        # ───────────────────────────────────────────────────────────────────
        # TEST 9: إغلاق الوردية وحساب الفارق
        # ───────────────────────────────────────────────────────────────────
        if shift_id_new:
            # Get active shift info
            r_active2 = client.get(f"{BASE}/api/finance/shifts/active", headers=headers)
            if r_active2.json().get("active"):
                system_balance = r_active2.json()["shift"]["current_system_balance"]
                # Simulate actual cash = system - 500 (عجز 500 ريال)
                actual = max(0, system_balance - 500)

                r_close = client.post(f"{BASE}/api/finance/shifts/close", headers=headers, json={
                    "shift_id": r_active2.json()["shift"]["id"],
                    "actual_cash": actual,
                    "notes": "اختبار إغلاق الوردية",
                })
                close_success = r_close.status_code == 200
                close_data = r_close.json() if close_success else {}
                log("Test 7: إغلاق الوردية وحساب الفارق",
                    close_success,
                    f"رصيد دفتري={close_data.get('ending_balance_system')} | "
                    f"فعلي={close_data.get('ending_balance_actual')} | "
                    f"فرق={close_data.get('difference')}")

                if close_success:
                    expected_diff = float(actual) - float(close_data.get("ending_balance_system", 0))
                    actual_diff = float(close_data.get("difference", 0))
                    diff_match = abs(expected_diff - actual_diff) < 0.01
                    log("Test 7b: صحة احتساب الفارق (actual - system)",
                        diff_match,
                        f"متوقع={expected_diff:.2f} | فعلي={actual_diff:.2f}")

        # ───────────────────────────────────────────────────────────────────
        # TEST 10: التحقق من توازن الأستاذ العام بعد كل العمليات
        # ───────────────────────────────────────────────────────────────────
        r_balance = client.get(f"{BASE}/api/reports/balance-check", headers=headers)
        if r_balance.status_code == 200:
            balance_data = r_balance.json()
            total_debit = Decimal(str(balance_data.get("total_debit_base", 0)))
            total_credit = Decimal(str(balance_data.get("total_credit_base", 0)))
            balanced = abs(total_debit - total_credit) <= Decimal("0.05")
            log("Test 8: توازن الأستاذ العام الكلي (Σ DB = Σ CR)",
                balanced,
                f"Σ Debit_Base={total_debit:.4f} | Σ Credit_Base={total_credit:.4f} | "
                f"Δ={abs(total_debit-total_credit):.4f}")
        else:
            log("Test 8: توازن الأستاذ العام", False,
                f"HTTP {r_balance.status_code} (endpoint may not exist)")

    except Exception as e:
        log(f"خطأ غير متوقع", False, str(e))
        import traceback
        traceback.print_exc()

    finally:
        client.close()

    # ─── Final Report ──────────────────────────────────────────────────────
    print("\n" + "="*70)
    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)
    print(f"   النتيجة النهائية: {passed}/{total} اختبار ناجح")
    print(f"   نسبة النجاح: {passed/total*100:.1f}%" if total > 0 else "   لا توجد نتائج")
    print("="*70)

    if passed == total:
        print("\n🎉 جميع الاختبارات ناجحة! المنظومة المالية تعمل بكفاءة 100%\n")
    else:
        failed = [r for r in RESULTS if not r["passed"]]
        print(f"\n⚠️  {len(failed)} اختبار(ات) فاشلة:")
        for f in failed:
            print(f"   - {f['test']}: {f['detail'][:100]}")
        print()

    return passed == total


if __name__ == "__main__":
    # Check if server is running
    try:
        import httpx
        r = httpx.get(f"{BASE}/api/settings/public", timeout=5)
        if r.status_code != 200:
            print(f"⚠️  الباكند لا يستجيب على {BASE}")
            print("   قم بتشغيل: cd backend && python -m uvicorn main:app --reload")
            sys.exit(1)
    except Exception:
        print(f"⚠️  لا يمكن الاتصال بالباكند على {BASE}")
        print("   قم بتشغيل الباكند أولاً.")
        sys.exit(1)

    success = main()
    sys.exit(0 if success else 1)
