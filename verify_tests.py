import asyncio
import httpx
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))
from app.core.database import AsyncSessionLocal as async_session_maker
from app.services.ledger_service import get_ledger_statement
from app.api.routes.finance import get_entity_balance

from main import app

from app.models.user import User, UserRole
from app.api.deps import get_current_user

# Mock users
mock_admin = User(id=1, username="admin", role=UserRole.ADMIN, is_active=True)
mock_employee = User(id=2, username="employee", role=UserRole.EMPLOYEE, is_active=True)

async def test():
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # No need to login, cookies are bypassed by dependency override
        
        print("=== 1. جدول المطابقة بدون فلاتر تاريخ ===")
        print("العملة | closing_balance v3 | get_entity_balance | الفرق")
        async with async_session_maker() as db:
            v3_data = await get_ledger_statement(db, "customer", 1)
            for curr in ["YER", "SAR", "USD"]:
                v3_bal = float(v3_data["ledgers"][curr]["closing_balance"]) if curr in v3_data["ledgers"] else 0.0
                db_bal = float(await get_entity_balance(db, "customer", 1, curr))
                diff = v3_bal - db_bal
                print(f"{curr:4} | {v3_bal:<18} | {db_bal:<18} | {diff}")

        print("\n=== 2. اختبار from_date لكل عملة ===")
        async with async_session_maker() as db:
            from_dt = date.today() - timedelta(days=30)
            v3_date = await get_ledger_statement(db, "customer", 1, from_date=from_dt)
            for curr, ledger in v3_date.get("ledgers", {}).items():
                ob = float(ledger["opening_balance"])
                td = float(ledger["total_debit"])
                tc = float(ledger["total_credit"])
                cb = float(ledger["closing_balance"])
                calc = ob + td - tc
                print(f"Currency: {curr} | Opening: {ob} | +Debit: {td} | -Credit: {tc} | =Calc: {calc} | Closing: {cb} | Match: {calc == cb}")

        print("\n=== 3. كود HTTP لمستخدم employee ===")
        app.dependency_overrides[get_current_user] = lambda: mock_employee
        res1 = await client.get("/api/finance/ledger/v3/customer/1")
        print(f"GET /finance/ledger/v3/customer/1 : {res1.status_code}")
        res2 = await client.get("/api/finance/ledger/v3/customer/1/export?format=excel")
        print(f"GET /finance/ledger/v3/customer/1/export?format=excel : {res2.status_code}")
        
        print("\n=== 4. تشغيل فعلي مع أكواد HTTP للمسارات القديمة والتقارير ===")
        app.dependency_overrides[get_current_user] = lambda: mock_admin
        # Old ledger route
        old_ledger = await client.get("/api/finance/ledger/customer/1")
        print(f"Old /finance/ledger/customer/1 : {old_ledger.status_code}")
        
        # Receipt voucher
        rv = await client.post("/api/finance/receipt-voucher/v2", json={
            "date": str(date.today()),
            "entity_type": "customer",
            "entity_id": 1,
            "currency": "YER",
            "amount": 100,
            "payment_method": "cash",
            "description": "test rv",
            "shift_id": 1
        })
        print(f"POST /finance/receipt-voucher/v2 : {rv.status_code} {rv.text if rv.status_code != 200 else ''}")
        
        # Payment voucher
        pv = await client.post("/api/finance/payment-voucher/v2", json={
            "date": str(date.today()),
            "entity_type": "supplier",
            "entity_id": 1,
            "currency": "YER",
            "amount": 50,
            "payment_method": "cash",
            "description": "test pv",
            "shift_id": 1
        })
        print(f"POST /finance/payment-voucher/v2 : {pv.status_code} {pv.text if pv.status_code != 200 else ''}")
        
        # Shift
        sh_open = await client.post("/api/finance/cash-shifts", json={
            "user_id": 1, "opening_balance_yer": 0, "opening_balance_sar": 0, "opening_balance_usd": 0
        })
        print(f"POST /finance/cash-shifts (open) : {sh_open.status_code} {sh_open.text if sh_open.status_code != 200 else ''}")
        
        sh_close = await client.post("/api/finance/cash-shifts/1/close", json={
            "actual_balance_yer": 0, "actual_balance_sar": 0, "actual_balance_usd": 0
        })
        print(f"POST /finance/cash-shifts/1/close : {sh_close.status_code} {sh_close.text if sh_close.status_code != 200 else ''}")
        
        # Reports export PDF
        rep = await client.post("/api/reports/export/pdf", json={
            "report_type": "daily_activity"
        })
        print(f"POST /api/reports/export/pdf : {rep.status_code} {rep.text if rep.status_code != 200 else ''}")

if __name__ == '__main__':
    asyncio.run(test())
