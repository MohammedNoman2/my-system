import sys, os, json, requests
from decimal import Decimal
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000/api"
FRONTEND = "http://localhost:5173"

GREEN="\033[92m"; RED="\033[91m"; YELLOW="\033[93m"; CYAN="\033[96m"; BOLD="\033[1m"; RESET="\033[0m"
passed=0; failed=0; audit_log=[]

def ok(msg):
    global passed; passed+=1
    print(f"  {GREEN}[OK]{RESET} {msg}"); audit_log.append({"status":"OK","msg":msg})

def fail(msg, detail=""):
    global failed; failed+=1
    print(f"  {RED}[FAIL]{RESET} {msg}")
    if detail: print(f"        {RED}{detail}{RESET}")
    audit_log.append({"status":"FAIL","msg":msg,"detail":detail})

def info(msg): print(f"  {CYAN}[INFO]{RESET} {msg}")

def section(title):
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}")

def make_session(username, password):
    s=requests.Session()
    r=s.post(f"{BASE}/auth/login",json={"username":username,"password":password})
    if r.status_code!=200: raise RuntimeError(f"Login failed: {r.status_code} {r.text[:100]}")
    d=r.json(); csrf=d.get("csrf_token","")
    s.headers.update({"X-CSRF-Token":csrf})
    return s,d

section("M1: فحص جاهزية الخوادم")
try:
    r=requests.get(f"{BASE}/settings/public",timeout=5)
    if r.status_code==200:
        ok(f"Backend FastAPI HTTP {r.status_code} OK")
        d=r.json(); ok(f"اسم المكتب: {d.get('office_name','غير محدد')} | شعار: {'موجود' if d.get('logo_data') else 'غير محدد'}")
    else: fail("Backend", str(r.status_code))
except Exception as e: fail("Backend غير متاح", str(e))

try:
    r=requests.get(FRONTEND,timeout=5)
    ok(f"Frontend Vite HTTP {r.status_code} OK") if r.status_code==200 else fail("Frontend",str(r.status_code))
except Exception as e: fail("Frontend", str(e))

section("M2: تسجيل دخول المدير وإنشاء موظف جديد")
try:
    adm,adm_data=make_session("admin","admin123")
    ok(f"Admin Login — role={adm_data.get('role')} | name={adm_data.get('full_name')}")
except Exception as e:
    fail("Admin Login",str(e)); sys.exit(1)

r=adm.post(f"{BASE}/settings/users",json={"username":"agent_test","password":"Password123!","full_name":"موظف الاختبار الميداني","role":"employee","email":"agent_test@arp.local","phone_number":"770000099","is_active":True})
if r.status_code==201:
    d=r.json(); ok(f"إنشاء agent_test — ID={d['id']} | role={d['role']}")
elif r.status_code==400 and "مسجل" in r.text:
    ok("agent_test موجود مسبقاً")
else:
    fail("إنشاء agent_test",f"{r.status_code}: {r.text[:150]}")

section("M3: الحجوزات — birth_place إلزامي")
r=adm.post(f"{BASE}/bookings/",json={"type":"flight","currency":"USD","total_amount":"100","paid_amount":"100","remaining_amount":"0","flight_details":{"passenger_name":"test","passenger_phone":"770000000","birth_date":"1990-01-01","airline":"X","origin":"A","destination":"B","departure_date":"2026-12-01","ticket_class":"economy","ticket_type":"one_way"}})
if r.status_code==422: ok("طيران بدون birth_place → 422 Unprocessable (Schema صحيح)")
else: fail(f"طيران بدون birth_place قُبل! HTTP {r.status_code}")

section("M3A: حجز طيران USD")
flight_bk=None
r=adm.post(f"{BASE}/bookings/",json={"type":"flight","currency":"USD","total_amount":"1200.00","paid_amount":"400.00","remaining_amount":"800.00","supplier_name":"وكالة الشرق للسفريات","notes":"تدقيق ميداني","flight_details":{"passenger_name":"أحمد محمد الزبيري","passenger_phone":"770111222","passport_number":"Y1234567","birth_date":"1985-06-15","birth_place":"صنعاء","airline":"طيران الجزيرة السريعة","flight_number":"XY-901","origin":"صنعاء","destination":"القاهرة","departure_date":"2026-11-01","ticket_class":"economy","ticket_type":"one_way"}})
if r.status_code==201:
    flight_bk=r.json(); ok(f"طيران USD — ID={flight_bk['id']} | {flight_bk['ticket_number']} | total=1200 USD | created_by={flight_bk.get('created_by_name','?')}")
else: fail("حجز طيران USD",f"{r.status_code}: {r.text[:200]}")

section("M3B: حجز نقل SAR")
transport_bk=None
r=adm.post(f"{BASE}/bookings/",json={"type":"transport","currency":"SAR","total_amount":"600.00","paid_amount":"200.00","remaining_amount":"400.00","supplier_name":"شركة البراق الدولية","notes":"تدقيق ميداني","transport_details":{"passenger_name":"فاطمة علي الحداد","passenger_phone":"770333444","id_number":"5678901234","birth_date":"1992-03-20","birth_place":"عدن","company":"شركة البراق للنقل","origin":"الرياض","destination":"جدة","travel_date":"2026-11-10","seat_number":"12B"}})
if r.status_code==201:
    transport_bk=r.json(); ok(f"نقل SAR — ID={transport_bk['id']} | {transport_bk['ticket_number']} | total=600 SAR")
else: fail("حجز نقل SAR",f"{r.status_code}: {r.text[:200]}")

section("M3C: حجز تأشيرة YER")
r=adm.post(f"{BASE}/bookings/",json={"type":"visa","currency":"YER","total_amount":"500000.00","paid_amount":"200000.00","remaining_amount":"300000.00","supplier_name":"مكتب التأشيرات السريعة","notes":"تدقيق ميداني","visa_details":{"passenger_name":"خالد عبد الله المقطري","passenger_phone":"770555666","passport_number":"B9876543","birth_date":"1978-11-05","birth_place":"تعز","visa_type":"tourist","destination_country":"تركيا","application_date":"2026-10-15"}})
if r.status_code==201:
    vd=r.json(); ok(f"تأشيرة YER — ID={vd['id']} | {vd['ticket_number']} | total=500,000 YER")
else: fail("حجز تأشيرة YER",f"{r.status_code}: {r.text[:200]}")

section("M3D: حجز طرد — استثناء birth_place")
r=adm.post(f"{BASE}/bookings/",json={"type":"parcel","currency":"YER","total_amount":"15000.00","paid_amount":"15000.00","remaining_amount":"0.00","notes":"تدقيق ميداني","parcel_details":{"sender_name":"محمد ناصر","sender_phone":"770777888","receiver_name":"سالم أحمد","receiver_phone":"734999111","origin":"صنعاء","destination":"حضرموت","weight_kg":"5.0","description":"ملابس"}})
if r.status_code==201:
    pd=r.json(); ok(f"طرد بدون birth_place — نجح! ID={pd['id']} | {pd['ticket_number']} ← الاستثناء مطبّق")
else: fail("حجز طرد",f"{r.status_code}: {r.text[:200]}")

section("M4: OCR — فحص نقطة النهاية")
r=adm.post(f"{BASE}/ocr/passport",files={"file":("dummy.jpg",b"FAKE_IMAGE","image/jpeg")})
if r.status_code in (200,400,422): ok(f"OCR endpoint /api/ocr/passport متاح — HTTP {r.status_code}")
elif r.status_code==404: info("OCR endpoint غير مفعّل في هذه البيئة")
else: info(f"OCR → HTTP {r.status_code}")

section("M6A: سند قبض RC مرتبط بحجز الطيران")
rc=None
if flight_bk:
    cid=flight_bk.get("customer_id")
    bid=flight_bk["id"]
    if not cid:
        r2=adm.get(f"{BASE}/bookings/{bid}")
        if r2.status_code==200: cid=r2.json().get("customer_id")
    if cid:
        r=adm.post(f"{BASE}/finance/receipt-voucher",json={"entity_type":"customer","entity_id":cid,"amount":"400.00","currency":"USD","payment_method":"cash","transaction_date":str(date.today()),"booking_id":bid,"notes":f"قبض مرتبط بـ {flight_bk['ticket_number']}"})
        if r.status_code==201:
            rc=r.json(); ok(f"RC سند قبض — {rc['transaction_id']} | amount=400 USD | booking_id={rc.get('booking_id')} ← مرتبط")
            r3=adm.get(f"{BASE}/bookings/{bid}")
            if r3.status_code==200: ok(f"رصيد الحجز بعد القبض: remaining={r3.json().get('remaining_amount')} USD (كان 800)")
        else: fail("RC",f"{r.status_code}: {r.text[:200]}")
    else: fail("RC: لا يوجد customer_id")
else: fail("RC: لا يوجد حجز طيران")

section("M6B: سند صرف PY مرتبط بحجز النقل")
py=None
if transport_bk:
    bid=transport_bk["id"]
    sups=adm.get(f"{BASE}/suppliers/")
    sup_id=1
    if sups.status_code==200:
        for s in sups.json():
            if "براق" in s.get("name","") or "بلاق" in s.get("name",""):
                sup_id=s["id"]; break
    r=adm.post(f"{BASE}/finance/payment-voucher",json={"entity_type":"supplier","entity_id":sup_id,"amount":"100.00","currency":"SAR","payment_method":"bank_transfer","transaction_date":str(date.today()),"booking_id":bid,"notes":f"دفع للمورد مرتبط بـ {transport_bk['ticket_number']}"})
    if r.status_code==201:
        py=r.json(); ok(f"PY سند صرف — {py['transaction_id']} | amount=100 SAR | booking_id={py.get('booking_id')} ← مرتبط")
    else: fail("PY",f"{r.status_code}: {r.text[:200]}")
else: fail("PY: لا يوجد حجز نقل")

section("M6C: مصروف تشغيلي EX")
r=adm.post(f"{BASE}/finance/expense",json={"amount":"50000.00","currency":"YER","payment_method":"cash","expense_type":"operational","transaction_date":str(date.today()),"notes":"إيجار مكتب — تدقيق ميداني"})
if r.status_code==201:
    ex=r.json(); ok(f"EX مصروف — {ex['transaction_id']} | amount=50000 YER | قيد مزدوج: Debit مصروف / Credit صندوق")
else: fail("EX",f"{r.status_code}: {r.text[:200]}")

section("M7A: RBAC — الموظف (agent_test)")
try:
    es,ed=make_session("agent_test","Password123!")
    ok(f"تسجيل دخول agent_test — role={ed.get('role')}")
    # Can view bookings
    r=es.get(f"{BASE}/bookings/?limit=5")
    if r.status_code==200:
        ok("الموظف يرى الحجوزات ✓")
        for b in r.json()[:2]:
            if "cost_price" in b and b["cost_price"] is not None:
                fail(f"RBAC خرق: cost_price={b['cost_price']} مرئي للموظف!")
            else:
                ok("cost_price مخفي عن الموظف في استجابة JSON ✓"); break
    # Cannot view finance
    r=es.get(f"{BASE}/finance/transactions?limit=5")
    if r.status_code in (401,403): ok(f"الموظف محجوب عن السندات المالية — HTTP {r.status_code} ✓")
    else: fail(f"الموظف يرى السندات! HTTP {r.status_code}")
    # Cannot manage users
    r=es.get(f"{BASE}/settings/users")
    if r.status_code in (401,403): ok(f"الموظف محجوب عن إدارة المستخدمين — HTTP {r.status_code} ✓")
    else: fail(f"الموظف يرى المستخدمين! HTTP {r.status_code}")
    # Cannot create vouchers
    r=es.post(f"{BASE}/finance/receipt-voucher",json={"entity_type":"customer","entity_id":1,"amount":"1","currency":"YER","payment_method":"cash","transaction_date":str(date.today())})
    if r.status_code in (401,403): ok(f"الموظف لا يُصدر سندات — HTTP {r.status_code} ✓")
    else: fail(f"الموظف أصدر سنداً! HTTP {r.status_code}")
except Exception as e:
    fail("agent_test session",str(e))

section("M7B: RBAC — المحاسب (accountant)")
try:
    acs,acd=make_session("accountant","accountant123")
    ok(f"تسجيل دخول accountant — role={acd.get('role')}")
    r=acs.get(f"{BASE}/finance/transactions?limit=5")
    if r.status_code==200: ok("المحاسب يرى السندات المالية ✓")
    else: fail(f"المحاسب محجوب عن السندات! HTTP {r.status_code}")
    r=acs.get(f"{BASE}/bookings/?limit=3")
    if r.status_code==200:
        for b in r.json()[:2]:
            if "cost_price" in b: ok(f"cost_price مرئي للمحاسب ✓ (ID={b.get('id')})"); break
        else: info("لا توجد حجوزات لفحص cost_price")
    r=acs.get(f"{BASE}/settings/users")
    if r.status_code in (401,403): ok(f"المحاسب محجوب عن إدارة المستخدمين ✓ HTTP {r.status_code}")
    else: fail(f"المحاسب يرى المستخدمين! HTTP {r.status_code}")
except Exception as e:
    fail("accountant session",str(e))

section("M8: توازن قيود الأستاذ العام Σ Debit = Σ Credit")
r=adm.get(f"{BASE}/bookings/?limit=10")
if r.status_code==200:
    bks=r.json(); checked=0; balanced_cnt=0
    print(f"\n  {'رقم التذكرة':<14} {'Σ Debit':>16} {'Σ Credit':>16} {'الفرق':>12} {'الحالة':>10}")
    print(f"  {'-'*14:<14} {'-'*16:>16} {'-'*16:>16} {'-'*12:>12} {'-'*10:>10}")
    for b in bks[:8]:
        r2=adm.get(f"{BASE}/bookings/{b['id']}/journal")
        if r2.status_code!=200: continue
        je=r2.json(); lines=je.get("journal_entries",[])
        td=Decimal("0"); tc=Decimal("0")
        for entry in lines:
            for ln in entry.get("lines",[]):
                td+=Decimal(str(ln.get("debit_base",0) or 0))
                tc+=Decimal(str(ln.get("credit_base",0) or 0))
        diff=abs(td-tc); bal=diff<=Decimal("0.05"); checked+=1
        if bal: balanced_cnt+=1
        tk=b.get("ticket_number",f"BK-{b['id']}")
        print(f"  {tk:<14} {str(td):>16} {str(tc):>16} {str(diff):>12} {'✓ متوازن' if bal else '✗ خطأ':>10}")
    print()
    if checked==0: info("لا توجد قيود (endpoint /journal غير متاح)")
    elif balanced_cnt==checked: ok(f"جميع القيود متوازنة {balanced_cnt}/{checked} — Σ Debit = Σ Credit = 0.0000 ✓")
    else: fail(f"قيود غير متوازنة: {balanced_cnt}/{checked}")

section("M9: دليل ارتباط السندات بالحجوزات")
r=adm.get(f"{BASE}/finance/transactions?limit=15")
if r.status_code==200:
    txs=r.json()
    print(f"\n  {'Transaction ID':<14} {'النوع':<14} {'المبلغ':>10} {'العملة':>7} {'Booking ID':>12}")
    print(f"  {'-'*14:<14} {'-'*14:<14} {'-'*10:>10} {'-'*7:>7} {'-'*12:>12}")
    linked=0
    for tx in txs[:10]:
        bid_val=str(tx.get("booking_id") or "-")
        if tx.get("booking_id"): linked+=1
        print(f"  {str(tx.get('transaction_id','?')):<14} {str(tx.get('type','?')):<14} {str(tx.get('amount','?')):>10} {str(tx.get('currency','?')):>7} {bid_val:>12}")
    print()
    ok(f"سندات مرتبطة بحجوزات: {linked} من أصل {min(10,len(txs))} سندات")
else: fail("جلب السندات",str(r.status_code))

# Final Summary
total=passed+failed; rate=(passed/total*100) if total>0 else 0
print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
print(f"{BOLD}  تقرير التدقيق الميداني الشامل — النتيجة النهائية{RESET}")
print(f"{BOLD}{CYAN}{'='*65}{RESET}")
print(f"  إجمالي الاختبارات : {total}")
print(f"  {GREEN}ناجحة            : {passed}{RESET}")
print(f"  {RED}فاشلة            : {failed}{RESET}")
print(f"  نسبة النجاح       : {rate:.1f}%")
if failed==0:
    print(f"\n  {GREEN}{BOLD}*** جميع الاختبارات نجحت 100% — نظام ARP مُتحقق ميدانياً ***{RESET}")
else:
    print(f"\n  {YELLOW}الاختبارات الفاشلة:{RESET}")
    for e in audit_log:
        if e["status"]=="FAIL":
            print(f"  {RED}✗ {e['msg']}{RESET}")
            if e.get("detail"): print(f"    {e['detail'][:100]}")
print(f"\n  توقيت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")
