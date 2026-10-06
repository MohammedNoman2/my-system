import asyncio
import json
import httpx
import re

async def main():
    print("======================================================================")
    print("اختبار تسجيل الدخول الجديد بعد حذف access_token و refresh_token من JSON")
    print("======================================================================")

    client = httpx.AsyncClient(base_url="http://127.0.0.1:8000")
    login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    
    print(f"HTTP Status: {login_res.status_code}")
    print("\n--- NEW JSON RESPONSE BODY ---")
    body_json = login_res.json()
    print(json.dumps(body_json, indent=2, ensure_ascii=False))
    
    print("\n--- SECURITY CHECK ---")
    has_access = "access_token" in body_json
    has_refresh = "refresh_token" in body_json
    print(f"Contains 'access_token' in JSON: {has_access} (Should be False)")
    print(f"Contains 'refresh_token' in JSON: {has_refresh} (Should be False)")
    print(f"Contains 'csrf_token' in JSON: {'csrf_token' in body_json} (Should be True)")
    
    print("\n--- SET-COOKIE HEADERS (PROVING TOKENS ARE EXCLUSIVELY IN HTTPONLY COOKIES) ---")
    cookies_header = login_res.headers.get_list("set-cookie")
    for ch in cookies_header:
        parts = ch.split(";")
        name_val = parts[0].split("=")
        attrs = ";".join(parts[1:])
        print(f"Cookie: {name_val[0]} | Attributes:{attrs}")

    print("\n======================================================================")
    print("التحقق من ترتيب الحقول في تذكرة الطيران بعد تصحيح اتجاه الخلايا")
    print("======================================================================")
    
    csrf_token = body_json.get("csrf_token")
    client.headers["X-CSRF-Token"] = csrf_token
    
    print_res = await client.get("/api/bookings/4/print?mode=thermal&format=html")
    html_content = print_res.text
    
    rows = re.findall(r'<tr>(.*?)</tr>', html_content, re.DOTALL)
    print(f"عدد الصفوف المستخرجة: {len(rows)}")
    
    for idx, r in enumerate(rows):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
        cell_data = []
        for c in cells:
            label_m = re.search(r'>([^<]+?):</span>', c)
            val_m = re.search(r'<span class="font-[^"]*"[^>]*>([^<]*?)</span>', c)
            l_text = label_m.group(1).strip() if label_m else ""
            v_text = val_m.group(1).strip() if val_m else ""
            cell_data.append(f"{l_text}: {v_text}")
        print(f"Row {idx+1} [يمين: {cell_data[0]} | وسط: {cell_data[1]} | يسار: {cell_data[2]}]")

    with open("voucher_flight_visual.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("\nتم حفظ ملف voucher_flight_visual.html للمعاينة البصرية المباشرة.")

if __name__ == "__main__":
    asyncio.run(main())
