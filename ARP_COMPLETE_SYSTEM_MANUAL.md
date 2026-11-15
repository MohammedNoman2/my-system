# الوثيقة الهندسية والمرجعية الشاملة لنظام ARP (الإصدار الموحّد 3.2 — بعد إتمام الدفعات الجراحية 4-A إلى 4-D)

## Advanced Reservation Platform — منصة الحجوزات المتقدمة (عالم النقل)

## 1. نظرة عامة على النظام (System Overview)

**نظام ARP (Advanced Reservation Platform)** هو نظام تخطيط موارد مؤسسية وحجوزات (Travel ERP) مصمم لمكاتب السفر والسياحة والنقل البري وتخليص المعاملات والشحن. يجمع النظام بين إدارة **5 قطاعات تشغيلية للحجوزات** وبين **محرك محاسبي متكامل بالقيد المزدوج (Double-Entry Ledger)** متعدد العملات (`YER`, `SAR`, `USD`)، مع إدارة الورديات النقدية (`Cash Shifts`)، وتخصيص السداد المتقاطع (`Cross-Currency Allocations`) بتقريب صارم إلى خانتين عشريتين (`0.01`)، واستهلاك واستعادة الرصيد الدائن المتاح للعميل تلقائياً (`credit_applied`)، وتوحيد المنطقة الزمنية للمكتب على توقيت صنعاء (`UTC+3`).

## 2. المكدس التقني الفعلي المعتمد (Verified Tech Stack)

### 2.1 الواجهة الخلفية (`backend/`)

* **الإطار واللغة:** `Python 3.11+` مع `FastAPI >= 0.110.0` وخادم `Uvicorn`، مع معالجات استثناءات مركزية تسجل أخطاء `4xx` و`422` بالتوقيت الدقيق مع الحفاظ على ترويسات الاستجابة.

* **قاعدة البيانات والـ ORM:** `SQLAlchemy >= 2.0.28` (نمط غير متزامن بالكامل `AsyncSession`)، مع محرك `aiosqlite` للتطوير المحلي (`backend/arp.db`) و`asyncpg` لقاعدة بيانات `PostgreSQL 16` في الإنتاج (مع عزل المنافذ الداخلية `5432` و`6379` واعتماد متغيرات البيئة في `.env`).

* **إدارة الترحيلات (Migrations):** `Alembic >= 1.13.0` مع دوال الترحيل والتسوية المحاسبية الآمنة (`backfill_historical_bookings`).

* **الأمان والمصادقة:**

  * تشفير كلمات المرور: `bcrypt >= 4.1.2` و`passlib`.

  * رموز الجلسات: `PyJWT >= 2.9.0` مخزنة حصراً داخل `HttpOnly Cookies` (`access_token` و`refresh_token`).

  * حماية تزوير الطلبات: `CSRFMiddleware` بنمط `Double-Submit Cookie` (`csrf_token` + ترويسة `X-CSRF-Token`) مع مقارنة زمنية ثابتة آمنة عبر `hmac.compare_digest` وترميز `UTF-8`.

  * تقييد الطلبات: `slowapi >= 0.1.9` (`100/minute` عام، و`20/minute` لمسار تسجيل الدخول).

  * رموز استعادة كلمة المرور: `itsdangerous >= 2.1.2` (صلاحية الرمز 3600 ثانية = ساعة واحدة) مع إرسال البريد عبر `aiosmtplib`.

  * فحص المرفوعات: فحص الحجم الأقصى (`2MB`) والتوقيع الثنائي الفعلي (`Magic Bytes`) لصور الشعار (`PNG/JPEG/WEBP`) وحظر ملفات `SVG` لمنع ثغرات `Stored XSS`، مع عزل مسار الرفع عبر `STATIC_UPLOADS_DIR`.

* **المطبوعات والتقارير والـ OCR:**

  * الطباعة وتوليد PDF: `WeasyPrint >= 61.0` مع خطوط `Cairo-Regular.ttf` و`Cairo-Bold.ttf` المحلية، وفحص توفر `WEASYPRINT_AVAILABLE` لتفعيل الحفظ القياسي عبر المتصفح (`Save as PDF`) تلقائياً على بيئات Windows دون تنزيل ملفات تالفة.

  * تصدير الجداول: `openpyxl >= 3.1.2` مع فصل مجاميع العملات والمعادل التقديري بالريال اليمني.

  * القراءة الضوئية للوثائق: `pytesseract >= 0.3.10` + `Pillow` مع الكشف التلقائي عن مسار التثبيت على Windows وتفريق استثناء `TesseractNotFoundError` عن رداءة الصور.

### 2.2 الواجهة الأمامية (`frontend/`)

* **الإطار واللغة:** `React 18.3.1` + `TypeScript 5.6.3` + أداة البناء `Vite 6.0.0`.

* **التصميم والتنسيق:** `Tailwind CSS v4.0.0` عبر `@tailwindcss/vite` (بدون مكتبات مكونات خارجية مثل Shadcn؛ جميع المكونات المشتركة مبنية يدوياً في `src/components/common/`).

* **إدارة الحالة العامة:** `Zustand 5.0.3` عبر 3 مخازن (`authStore.ts`, `settingsStore.ts`, `uiStore.ts`).

* **النماذج والتحقق:** `React Hook Form 7.54.2` + `Yup 1.6.1` + `@hookform/resolvers`.

* **الرسوم البيانية والأيقونات:** `Recharts 2.15.0` + `lucide-react 0.475.0`.

* **الاتصال بالخادم:** `Axios 1.7.9` (`src/services/api.ts`) مزود بـ Interceptors لإرفاق `X-CSRF-Token` وتجديد الجلسة تلقائياً عند استلام `401`.

## 3. مصفوفة الصلاحيات والأدوار (RBAC Matrix)

تُفرض الصلاحيات من الخادم عبر `backend/app/api/deps.py` (`require_admin`, `require_accountant_or_admin`, `require_booking_role`) وفي الواجهة عبر `ProtectedRoute.tsx`:

| الوحدة / الصلاحية | مدير النظام (`admin`) | المحاسب (`accountant`) | الموظف (`employee`) | 
| ----- | ----- | ----- | ----- | 
| **لوحة التحكم (`/dashboard`)** | شاملة (المبيعات، التكاليف، الأرباح، التنبيهات) | شاملة (المبيعات، التكاليف، الأرباح، التنبيهات) | مبيعات وحجوزات الموظف نفسه فقط بدون تكاليف أو أرباح | 
| **حقل سعر التكلفة (`cost_price`)** | متاح في الإدخال والعرض والتقارير | متاح في الإدخال والعرض والتقارير | **محذوف كلياً من استجابة الخادم (`BookingEmployeeResponse`) ومن شجرة `DOM`** | 
| **الحجوزات الخمسة (`/bookings`)** | إنشاء، عرض الكل، إلغاء، تأجيل، تغيير مسار، طباعة | عرض ومراجعة الأثر المالي والقيود (لا ينشئ ولا يلغي حجوزات) | إنشاء وعرض وإلغاء وتأجيل حجوزاته الخاصة فقط (خلال 24 ساعة من الإنشاء) | 
| **السندات المالية والورديات (`/finance`)** | كامل الصلاحيات (قبض، صرف، مصروف، إلغاء سند عكسي، ورديات) | كامل الصلاحيات (قبض، صرف، مصروف، إلغاء سند عكسي، ورديات) | فتح/إغلاق ورديته النقدية وإصدار سندات قبض مرتبطة بحجوزاته | 
| **العملاء (`/customers`)** | إضافة، تعديل، بحث، كشف حساب | إضافة، تعديل، بحث، كشف حساب | إضافة، بحث، عرض | 
| **الموردون (`/suppliers`)** | إضافة، تعديل، بحث، كشف حساب | إضافة، تعديل، بحث، كشف حساب | قراءة القائمة لأغراض اختيار المورد في الحجز فقط | 
| **التقارير (`/reports`)** | جميع التقارير الـ 7 + كشف الحساب المتعدد العملات (`Ledger v3`) | جميع التقارير الـ 7 + كشف الحساب المتعدد العملات (`Ledger v3`) | **تقرير الحجوزات التفصيلي الخاص به فقط** (`employee_id` مفروض من الخادم) | 
| **الإعدادات والمستخدمون (`/settings`)** | كامل الصلاحيات (بيانات المكتب، الشعار، الصرف، المستخدمون، سجل التدقيق) | غير مصرح | غير مصرح | 

## 4. هيكلة قاعدة البيانات والجداول الـ 20 الفعلية (Database Schema)

### 4.1 جداول الهوية والإعدادات والرقابة

1. **`users`**: بيانات المستخدمين، الأدوار (`admin`, `employee`, `accountant`)، حالة التفعيل (`is_active`)، عداد المحاولات الفاشلة (`failed_login_attempts`)، القفل المؤقت (`locked_until`)، و`refresh_token`.

2. **`settings`**: هوية المكتب (`office_name`, `tagline`, `address`, `phone_numbers`, `email`, `website`, `default_currency`, `footer_text`) والشعار (`logo_image_url` و`logo_data` بصيغة Base64).

3. **`exchange_rates`**: أسعار الصرف المعتمدة بين العملات (`from_currency`, `to_currency`, `rate`).

4. **`reference_counters`**: العدادات الذرية الـ 10 لتوليد الأرقام التسلسلية بصيغة `{PREFIX}-{XXXX}` باستخدام قفل `SELECT ... FOR UPDATE`:

   * الحجوزات: `FL` (طيران)، `TR` (نقل بري)، `VI` (تأشيرات)، `PA` (جوازات)، `PR` (طرود).

   * المالية والمحاسبة: `RC` (سند قبض)، `PY` (سند صرف)، `EX` (مصروف)، `JE` (قيد يومية)، `SH` (وردية نقدية).

5. **`audit_logs`**: السجل الرقابي غير القابل للتعديل (`user_id`, `action`, `table_name`, `record_id`, `old_data`, `new_data`, `ip_address`, `user_agent`, `timestamp`).

### 4.2 جداول الأطراف والحجوزات الخمسة

 6. **`customers`**: بيانات العملاء (`name`, `phone_number` بفهرس غير فريد `ix_customers_phone_number` مع تطبيع مفتاح اليمن إلى 9 أرقام محلية ودعم مشاركة الهاتف بين أفراد العائلة, `email`, `passport_number`, `id_number`, `nationality`, `address`, `balance`) مع إرجاع `credit_balances` للعملات الثلاث دون استعلامات متكررة (`Batch Query`).

 7. **`suppliers`**: بيانات الموردين وشركات الطيران والنقل (`name`, `contact_person`, `phone_number`, `service_type`, `address`, `balance`).

 8. **`bookings`**: الجدول الأب لجميع الحجوزات (`booking_id`, `ticket_number`, `type`, `customer_id`, `employee_id`, `supplier_id`, `cost_price`, `selling_price`, `paid_amount`, `credit_applied` لتوثيق الرصيد الدائن المخصوم واستعادته عند الإلغاء, `remaining_amount`, `currency`, `status`: `pending|confirmed|cancelled`, `cancelled_at`, `cancelled_by`, `cancellation_reason`, `refund_amount`).

 9. **`flight_booking_details`**: تفاصيل الطيران (`airline_company`, `flight_number`, `departure_airport`, `arrival_airport`, `departure_date`, `departure_time`, `return_date`, `return_time`, `ticket_type`, `allowed_weight`, `passenger_name`, `passenger_phone`, `passport_number`, `birth_date`, `birth_place`, `passport_image_url`).

10. **`transport_booking_details`**: تفاصيل النقل البري (`transport_company`, `departure_station`, `arrival_station`, `travel_date`, `travel_time`, `passenger_name`, `passenger_phone`, `id_number`, `birth_date`, `birth_place`, `id_image_url`) — *بدون حقل `seat_number`*.

11. **`visa_booking_details`**: تفاصيل التأشيرات (`visa_type`, `application_date`, `applicant_name`, `applicant_phone`, `passport_number`, `birth_date`, `birth_place`, `passport_image_url`) — *بدون حقول `country`, `duration`, `expected_issue_date`*.

12. **`passport_booking_details`**: تفاصيل الجوازات (`passport_type`: `new|renewal|lost|damaged`, `priority`: `normal|urgent`, `application_date`, `expected_delivery_date`, `applicant_name`, `applicant_phone`, `id_number`, `birth_date`, `birth_place`, `id_image_url`).

13. **`parcel_booking_details`**: تفاصيل شحن الطرود (`sender_name`, `sender_phone`, `receiver_name`, `receiver_phone`, `delivery_destination`, `parcel_type` نص حر, `weight`, `content_description`, `shipping_date`) — *بدون حقل `quantity`*.

### 4.3 جداول المنظومة المحاسبية (Double-Entry ERP) والورديات

14. **`accounts`**: دليل الحسابات الشجري (`code` فريد، `name`, `account_type`: `ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE`, `currency`: `YER|SAR|USD`, `entity_type`: `CUSTOMER|SUPPLIER|NONE`, `entity_id`).

    * الحسابات الأساسية: الصناديق (`1101-{CURR}`)، مبيعات الحجوزات (`4101-{CURR}`)، رسوم الإلغاء (`4201-{CURR}`)، تكلفة المبيعات (`5101-{CURR}`)، المصروفات التشغيلية (`5201-{CURR}`)، الأرباح المبقاة (`3101-YER`)، فروق الصرف والتقريب (`4901-{CURR}` و`5901-{CURR}`).

    * الحسابات الفرعية التلقائية: لكل عميل `1201-CUST-{ID}-{CURR}` ولكل مورد `2101-SUPP-{ID}-{CURR}` بالعملات الثلاث.

15. **`journal_entries`**: رأس قيد اليومية العام (`entry_number`, `date`, `reference_type`: `BOOKING|BOOKING_BACKFILL|RECEIPT|PAYMENT|EXPENSE|CANCEL|REROUTE|VOID|OPENING`, `reference_id`, `currency`, `exchange_rate`, `description`, `is_posted`).

16. **`journal_entry_lines`**: أسطر قيد اليومية (`journal_entry_id`, `account_id`, `debit`, `credit`, `debit_base`, `credit_base`) محمية بقيد `CheckConstraint: (debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)`.

17. **`cash_shifts`**: الورديات النقدية (`shift_number`, `user_id`, `opened_at`, `closed_at`, `starting_balance`, `ending_balance_system`, `ending_balance_actual`, `difference`, `status`: `open|closed`, `closing_notes`).

18. **`financial_transactions`**: السندات والحركات المالية (`transaction_id`, `type`: `payment_in|payment_out|expense`, `entity_type`, `entity_id`, `amount`, `currency`, `payment_method`: `cash|bank_transfer|check`, `reference_number`, `expense_type`, `notes`, `transaction_date`, `booking_id`, `shift_id`, `is_void`, `voided_at`, `voided_by_id`, `void_reason`, `reversal_je_number`).

19. **`voucher_allocations`**: تخصيص السندات على التذاكر (`voucher_id`, `booking_id`, `allocated_amount`, `target_currency`, `exchange_rate`, `allocated_in_booking_currency`).

20. **`alembic_version`**: تتبع إصدار ترحيل قاعدة البيانات.

## 5. المسارات البرمجية المعتمدة (Canonical REST API Endpoints)

### 5.1 المصادقة (`/api/auth`)

* `POST /api/auth/login` — تسجيل الدخول وإصدار الكوكيز و`csrf_token`.

* `POST /api/auth/refresh` — تجديد `access_token` عبر `refresh_token`.

* `POST /api/auth/logout` — تسجيل الخروج وإتلاف الجلسة.

* `GET /api/auth/me` — بيانات المستخدم الحالي.

* `POST /api/auth/forgot-password` و`POST /api/auth/reset-password` — استعادة كلمة المرور.

### 5.2 الحجوزات والبحث الموحد (`/api/bookings`)

* `POST /api/bookings/` — إنشاء حجز جديد (مع إنشاء العميل/المورد وحساباتهما وتوليد قيد اليومية وسند القبض المبدئي).

* `GET /api/bookings/` — قائمة الحجوزات مع فلاتر `booking_type`, `status_filter`, `search`.

* `GET /api/bookings/unpaid` — جلب الحجوزات غير المسددة بالكامل لعميل محدد (`customer_id`).

* `GET /api/bookings/search` — محرك البحث الموحد عن التذاكر (10 أعمدة: بالاسم `q_name`، الرقم/الهاتف/الهوية `q_number`، رقم التذكرة `q_ticket`، النوع، والحالة).

* `GET /api/bookings/{id}` — تفاصيل حجز محدد.

* `GET /api/bookings/{id}/journal` — جلب قيود اليومية العامة (`JournalEntry`) المرتبطة بالحجز ورصيد العميل.

* `POST /api/bookings/{id}/cancel` — إلغاء الحجز وتوليد قيد عكسي محاسبي وإثبات رسوم الإلغاء والمسترد.

* `POST /api/bookings/{id}/postpone` — تأجيل موعد الرحلة وتوثيق السبب في سجل التدقيق.

* `POST /api/bookings/{id}/reroute` — تعديل مسار الرحلة وتوليد قيد تسوية لفارق السعر (`REROUTE`).

* `GET /api/bookings/{id}/print` — طباعة سند الحجز (`mode=thermal|a4`, `format=html|pdf`).

### 5.3 المالية والورديات والأستاذ العام (`/api/finance`)

* `POST /api/finance/shifts/open` — فتح وردية نقدية جديدة (`SH-XXXX`).

* `GET /api/finance/shifts/active` — حالة الوردية النشطة للمستخدم الحالي وحركة النقدية.

* `POST /api/finance/shifts/close` — إغلاق الوردية وحساب الفارق بين الرصيد الدفتري والفعلي.

* `GET /api/finance/shifts/history` — سجل الورديات السابقة.

* `POST /api/finance/receipt-voucher` — سند قبض بسيط.

* `POST /api/finance/receipt-voucher/v2` — سند قبض متقدم يدعم تعدد التخصيصات (`allocations`) والمصارفة بين العملات وفروق الصرف.

* `POST /api/finance/payment-voucher` — سند صرف محمي بقفل تشاؤمي (`get_cash_balance_with_lock`) لمنع العجز النقدي.

* `POST /api/finance/expense` — تسجيل مصروف تشغيلي (`EX-XXXX`).

* `POST /api/finance/vouchers/{voucher_id}/void` — إلغاء سند مالي وتوليد قيد عكسي مطابق (`Mirror Reversal JE`) وعكس التخصيصات.

* `GET /api/finance/search` — البحث في السندات المالية بالرقم المرجعي (`RC-` أو `PY-`).

* `GET /api/finance/voucher/{voucher_id}/print` — طباعة السند المالي (`thermal|a4`).

* `GET /api/finance/transactions` — قائمة الحركات المالية.

* `GET /api/finance/ledger/customer/{id}` و`GET /api/finance/ledger/supplier/{id}` — كشف الحساب التوافقي (`v2`).

* `GET /api/finance/ledger/v3/{entity_type}/{entity_id}` — محرك كشف الحساب المتعدد العملات المعتمد على قيود اليومية (`Ledger v3`) مع الأرصدة الافتتاحية والختامية.

* `GET /api/finance/ledger/v3/{entity_type}/{entity_id}/export` — تصدير كشف الحساب إلى `excel` أو `pdf` (مع `HTML Print View` توافقي).

### 5.4 العملاء والموردون والتقارير والإعدادات

* `/api/customers`: `GET /search`, `GET /`, `POST /`, `GET /{id}`, `PUT /{id}`.

* `/api/suppliers`: `GET /`, `POST /`, `GET /{id}`, `PUT /{id}`.

* `/api/dashboard`: `GET /summary`, `GET /alerts`.

* `/api/reports`: `POST /generate`, `POST /export/excel`, `POST /export/pdf`.

* `/api/settings`: `GET /public`, `GET /office`, `PUT /office`, `POST /logo`, `GET /exchange-rates`, `POST /exchange-rates`, `GET /users`, `POST /users`, `PUT /users/{id}`, `PATCH /users/{user_id}/status`, `POST /users/{user_id}/reset-password`, `GET /audit-logs`.

* `/api/ocr`: `POST /extract-passport`, `POST /extract-id`.

## 6. سجل المراحل الهندسية والعمليات الجراحية المنجزة (Completed Engineering Stages 1 to 4-D)

تم تنفيذ وإنجاز كافة المراحل الجراحية واجتياز بوابات التحقق الآلي بنجاح 100%:

1. **المرحلة الجراحية 1 (`4bce974` — توحيد العقود البرمجية وإصلاح أعطال التشغيل الـ 10) [مكتملة 100%]:** مطابقة أسماء الحقول والـ Enums بين الواجهة والخادم، إضافة `generate_financial_voucher_html`، إصلاح مسار التذاكر غير المسددة في سند القبض، إظهار اسم المستخدم في سجل التدقيق، وتثبيت `ToastContainer` في `App.tsx`.

2. **المرحلة الجراحية 2 (`b3cccdc` — إحكام المحرك المحاسبي والورديات والتقارير) [مكتملة 100%]:** تحديث `supplier.balance` عند الحجز والإلغاء، معالجة تعدد العملات في أرصدة الأطراف، استبعاد السندات والحجوزات الملغاة من الإحصائيات والتقارير، وإحكام الورديات النقدية.

3. **المرحلة الجراحية 3 (`714e3ce` — إحكام الصلاحيات RBAC، قيد الـ 24 ساعة، الـ OCR، ونوافذ التعديل) [مكتملة 100%]:** تطبيق قيد الـ 24 ساعة الصارم على تعديل وإلغاء وتغيير مسار حجوزات الموظف، تأمين مسار إعدادات المكتب `/settings/office` بالمصادقة، ترقية محلل القراءة الضوئية الذكي (`Smart OCR MRZ Parser`)، وإضافة نوافذ تعديل بيانات العملاء والموردين بالواجهة.

4. **الدفعة الجراحية 4-أ (`833e4c1` — فهرس الهاتف والمطابقة الذكية، قوالب التذاكر، وحالة الحجز/السداد) [مكتملة 100%]:** تحويل فهرس هاتف العميل إلى غير فريد مع تطبيع الأرقام اليمنية، تطبيق المطابقة الذكية للأسماء ومنع انتحال الوثائق (`409 Conflict`) والأرقام الوهمية (`12345678`)، توحيد الصف المالي في التذاكر الخمس، فصل شارة حالة الحجز عن شارة السداد، تحسين رسائل أخطاء `Tesseract OCR`، وتسجيل أخطاء `4xx/422` (`verify_stage_4a.py`).

5. **الدفعة الجراحية 4-ب (`0ce39ad` — فصل العملات في التقارير، توقيت صنعاء `UTC+3`، ولوحة التحكم الحية) [مكتملة 100%]:** توحيد المنطقة الزمنية للمكتب على توقيت صنعاء (`OFFICE_TZ = UTC+3`) عبر `office_date_range_utc` و`format_office_dt`، فصل مجاميع العملات (`totals_by_currency`) في كافة التقارير الـ 7 وتصديري `PDF/Excel`، تحويل تقرير المديونيات إلى قراءة فقط (`Read-Only`)، وربط رسوم لوحة التحكم بالبيانات الحية (`verify_stage_4b.py`).

6. **الدفعة الجراحية 4-ج (`3e53d94` — قيود الاستحقاق والدفعة المقدمة، الرصيد الدائن للعميل، وتفصيل كشف الحساب) [مكتملة 100%]:** تسجيل كامل `selling_price` في قيد الحجز (`BOOKING`) وإنشاء قيد مستقل للدفعة المقدمة (`RECEIPT`) مع تسوية الحجوزات التاريخية عبر `BOOKING_BACKFILL`، وحساب واستهلاك الرصيد الدائن المتاح للعميل تلقائياً (`credit_applied`) مع استعادته الكاملة عند الإلغاء، وتقريب تحويل العملات إلى خانتين (`0.01`) مع تفصيل البيان وحالة الرصيد (`عليه / له - رصيد دائن / متزن`) في كشف الحساب (`verify_stage_4c.py`).

7. **الدفعة الجراحية 4-د (`a979d34` & `a2d3fe6` — التحصين الأمني، أسعار الصرف الحية، وتغليف `ErrorBoundary`) [مكتملة 100%]:** إغلاق المنافذ الداخلية (`5432` و`6379`) في `docker-compose.yml` ونقل الأسرار إلى `.env`، تطبيق `hmac.compare_digest` في `csrf.py`، فحص التوقيع الثنائي (`Magic Bytes`) والحجم (`2MB`) للشعارات وحظر `SVG` مع عزل مجلد الاختبار `STATIC_UPLOADS_DIR` والحفاظ على شعار المكتب الأصلي (`324,985 بايت`)، ربط أسعار الصرف الحية في `ReceiptVoucherModal.tsx`، رفع سقف قوائم العملاء والموردين إلى `1000`/`2000`، وإضافة `ErrorBoundary` بالواجهة (`verify_stage_4d.py`).

## 7. حالة الإصدار المعتمد للنظام (System Release Status)
* **رقم الإصدار:** `v3.2 Verified & Hardened (Stage 4-D Complete)`
* **المسارات النشطة:** 53 مساراً محمياً تجتاز بوابات التحقق الأربع (`verify_stage_4a.py` إلى `verify_stage_4d.py`) بنسبة 100%.
* **المحرك المحاسبي:** قيد مزدوج متوازن بالعملات الثلاث (`YER`, `SAR`, `USD`) بتوقيت صنعاء (`UTC+3`) مع استهلاك واستعادة الأرصدة الدائنة وتقريب فروق الصرف.
* **الواجهة:** مبنية ومختبرة بنجاح عبر `React 18` و`TypeScript` و`Tailwind CSS v4` ومحمية بـ `ErrorBoundary`.
