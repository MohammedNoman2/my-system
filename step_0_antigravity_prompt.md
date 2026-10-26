# برومبت المرحلة التمهيدية (Step 0) لـ Antigravity: تثبيت دستور القواعد الصارمة، تنظيف المشروع، توحيد التوثيق، والمزامنة مع GitHub

انسخ النص الموجود داخل الإطار أدناه بالكامل والصقه مباشرة في محادثة **Antigravity IDE**؛ سيقوم هو تلقائياً بإنشاء ملفات القواعد الدائمة في مساراتها الصحيحة على جهازك، وتنظيف الملفات المتضاربة، وتحديث الوثيقة المرجعية، ومزامنة كل شيء مع **GitHub**:

---

## النص المخصص للنسخ واللصق في Antigravity:

أنت الآن تنفذ **المرحلة التمهيدية الصارمة (Step 0: Governance, Cleanup & Documentation Unification)** لمشروع `my-system`.
يُمنع منعاً باتاً لمس أو تعديل أي ملف كود مصدري تشغيلي داخل `backend/app/` أو `frontend/src/` في هذه المرحلة. نفّذ الخطوات الخمس التالية بالترتيب الحرفي دون زيادة أو نقصان:

### الخطوة 1: إنشاء نقطة حفظ آمنة (Git Checkpoint)
نفّذ في الطرفية داخل مجلد المشروع `C:\Users\Mohammed\Desktop\my-system`:
```powershell
git add -A
git commit -m "checkpoint: before step 0 cleanup and governance rules"
```

### الخطوة 2: إنشاء وتثبيت ملفات "دستور القواعد الصارمة" (Global & Workspace Rules)
قم بإنشاء ملفين للقواعد الصارمة لضمان التزامك بها في كل جلسة حالية أو مستقبلية:

**أ) الملف الأول (قواعد عامة دائمة لجميع المشاريع على الجهاز):**
أنشئ الملف `C:\Users\Mohammed\.gemini\GEMINI.md` (وأنشئ المجلد إذا لم يكن موجوداً) واكتب فيه المحتوى التالي حرفياً:
```markdown
# STRICT GLOBAL ENGINEERING PROTOCOL (دستور الهندسة البرمجية الصارم)

يجب الالتزام بهذه القواعد الإلزامية في كل مشروع وفي كل خطوة برمجية دون استثناء:

1. **التعديل الجراحي المحدود (Surgical Edits Only):**
   - يُمنع إعادة كتابة الملفات الكبيرة بالكامل. عدّل فقط الأسطر والدوال المحددة في الطلب.
   - يُمنع حذف أو إعادة تسمية أي مسار API قائم (`@router.get/post/put/patch/delete`) أو دالة قائمة إلا بأمر صريح بالاسم.

2. **التطابق الصارم بين الواجهة والخادم (Strict Schema Parity):**
   - قبل تعديل أي نموذج في الواجهة الأمامية أو الخلفية، اقرأ ملف الـ Schema في الخادم وملف `types` في الواجهة الأمامية وتأكد من تطابق أسماء الحقول وقيم الـ `Enum` حرفياً بنسبة 100%.

3. **حظر الارتجال والالتفاف (Zero Improvisation / Hard Stop Rule):**
   - إذا واجهت خطأ غير متوقع، أو تعارضاً في الأسطر، أو فشل اختبار التحقق، **توقف فوراً (STOP)**.
   - يُمنع منعاً باتاً اختراع مسارات بديلة أو تعديل ملفات غير مذكورة في الطلب أو تعطيل فحوصات الأمان لتمرير الاختبار. اطبع نص الخطأ الحرفي (`Traceback`) للمستخدم وانتظر التوجيه.

4. **التحقق الآلي الإلزامي قبل إعلان النجاح (Mandatory Verification Gate):**
   - لا تكتب "تم بنجاح" أبداً قبل تشغيل أوامر فحص المترجم (`python -m py_compile` للباك إند و `npx tsc --noEmit` للفرونت إند) والتأكد من أن عدد المسارات لم ينقص.

5. **بروتوكول التوثيق والمزامنة التلقائية مع GitHub (Post-Task Sync Protocol):**
   - بعد نجاح التحقق الآلي لأي مرحلة تعديل أو تطوير:
     أ) حدّث سجل `DEV_LOG.md` والوثيقة المرجعية للمشروع بما تم إنجازه فعلياً.
     ب) نفّذ `git add -A` ثم `git commit` برسالة واضحة ثم `git push origin main` لمزامنة التعديلات مع GitHub.
```

**ب) الملف الثاني (قواعد خاصة بمشروع `my-system` داخل مجلد المشروع):**
أنشئ الملف `C:\Users\Mohammed\Desktop\my-system\GEMINI.md` (ونسخة منه في `C:\Users\Mohammed\Desktop\my-system\.agent\rules\project-rules.md`) واكتب فيه المحتوى التالي حرفياً:
```markdown
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
```

### الخطوة 3: تنظيف الملفات القديمة والمؤقتة والمتضاربة
1. **حذف ملفات التوثيق القديمة المتضاربة من جذر المشروع** (لأنها تحتوي على مواصفات قديمة تتعارض مع الكود الفعلي):
   - احذف `ARP_SYSTEM_FULL_DOCUMENTATION.md`
   - احذف `implementation_plan.md`
   - احذف `برومبت التعليمات الشامل .md`
2. **حذف الملفات المؤقتة وقاعدة البيانات الفارغة المكررة:**
   - احذف قاعدة البيانات الفارغة في الجذر `C:\Users\Mohammed\Desktop\my-system\arp.db` (واحذر: **لا تلمس** قاعدة البيانات الحقيقية الموجودة في `backend\arp.db`).
   - احذف `verify_tests.py` من الجذر.
   - احذف `backend\db_out.txt` و `backend\db_out_2.txt`.
   - احذف ملفات HTML التجريبية المؤقتة: `backend\test_print.html`، `backend\voucher_flight_visual.html`، و `docs\test_voucher_output.html`.
3. **تنظيم ملفات الاختبار في مجلد مخصص:**
   - أنشئ مجلداً باسم `backend\tests` وانقل إليه الملفات الـ 8 التالية من `backend\`:
     `check_db.py`, `test_erp_verification.py`, `test_full_audit.py`, `test_live_all.py`, `test_pdf_in_docker.py`, `test_point1_and_print.py`, `test_shifts_and_allocations.py`, `test_tickets_and_branding.py`.
4. **تحديث `.gitignore` في الجذر:**
   - تأكد من إضافة `*.db` و `db_out*.txt` إلى `.gitignore` حتى لا تُرفع ملفات قواعد البيانات المؤقتة بالخطأ.

### الخطوة 4: تحديث `DEV_LOG.md`
حدّث ملف `DEV_LOG.md` ليوضح أن:
- تم اعتماد دستور القواعد الصارمة (`GEMINI.md`) وتوحيد التوثيق في `ARP_COMPLETE_SYSTEM_MANUAL.md`.
- تم تنظيف الجذر من الوثائق القديمة المتضاربة ونقل سكربتات الاختبار إلى `backend/tests/`.
- المشروع جاهز الآن للبدء بـ **المرحلة الجراحية 1 (إصلاح أعطال التوافق الـ 10 الحرجة)**.

### الخطوة 5: التحقق الآلي والمزامنة مع GitHub
1. نفّذ أمر التحقق للتأكد من سلامة جميع ملفات الباك إند والفرونت إند:
```powershell
python -m py_compile (Get-ChildItem -Path backend/app -Recurse -Filter *.py).FullName backend/main.py
cd frontend; npx tsc --noEmit; cd ..
```
2. نفّذ المزامنة مع GitHub:
```powershell
git add -A
git commit -m "chore(governance): add strict GEMINI.md rules, unify docs, and clean obsolete files"
git push origin main
```
3. اعرض لي مخرجات `git status` وآخر سجل `git log -n 2` كدليل إثبات.
