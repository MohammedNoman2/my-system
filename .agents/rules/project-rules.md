# قواعس الحماية المعمارية لمشروع ARP (`my-system`)

1. **المرجع المعماري الوحيد (Single Source of Truth):**
   - الملف المرجعي الرسمي الوحيد للمشروع هو `ARP_COMPLETE_SYSTEM_MANUAL.md` إلى جانب `DEV_LOG.md`.
   - قاعدة البيانات المحلية المعتمدة للتطوير هي `backend/arp.db` حصراً (يُمنع إنشاء `arp.db` في المجلد الرئيسي).

2. **المسارات المحمية التي يُحظر المساس بوجودها (`Protected Routes`):**
   - في `backend/app/api/routes/finance.py`: يجب الحفاظ التام على مسارات `/shifts/open`, `/shifts/active`, `/shifts/close`, `/shifts/history`, `/receipt-voucher`, `/receipt-voucher/v2`, `/payment-voucher`, `/expense`, `/vouchers/{voucher_id}/void`, `/search`, `/voucher/{voucher_id}/print`, `/transactions`, `/ledger/customer/{customer_id}`, `/ledger/supplier/{supplier_id}`, `/ledger/v3/{entity_type}/{entity_id}`, `/ledger/v3/{entity_type}/{entity_id}/export`.
   - في `backend/app/api/routes/bookings.py`: يجب الحفاظ التام على مسارات `POST /`, `GET /unpaid`, `GET /search`, `GET /`, `GET /{id}`, `GET /{id}/journal`, `POST /{id}/cancel`, `POST /{id}/postpone`, `POST /{id}/reroute`, `GET /{id}/print`.

3. **قواعد المحاسبة والأمان الثابتة:**
   - حقل `cost_price` يجب أن يبقى محذوفاً تماماً من `BookingEmployeeResponse` ومن شجرة `DOM` لدور `employee`.
   - كل قيد يومية في `journal_entries` يجب أن يكون متوازناً (`sum(debit_base) == sum(credit_base)`).

4. **الإجراء الإلزامي بعد كل عملية تعديل ناجحة:**
   - تشغيل فحص `python -m py_compile` على كل ملفات `backend/app` و `npx tsc --noEmit` في `frontend`.
   - تحديث `DEV_LOG.md` و `ARP_COMPLETE_SYSTEM_MANUAL.md` بأي تغيير معماري.
   - تنفيذ `git add -A && git commit -m "..." && git push origin main` لرفع التحديث إلى مستودع GitHub.
