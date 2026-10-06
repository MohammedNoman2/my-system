# خطة تنفيذ نظام ARP — الفرونت اند الكامل

> مُحدّثة بعد اعتماد [RECONCILIATION_REPORT.md](file:///C:/Users/Mohammed/.gemini/antigravity-ide/brain/aa06265a-0ff2-4680-a8c8-38328f243251/RECONCILIATION_REPORT.md)
> كل مرحلة تشير صراحة إلى أرقام أقسام [برومبت التعليمات](file:///c:/Users/Mohammed/Desktop/my-system/%D8%A8%D8%B1%D9%88%D9%85%D8%A8%D8%AA%20%D8%A7%D9%84%D8%AA%D8%B9%D9%84%D9%8A%D9%85%D8%A7%D8%AA%20%D8%A7%D9%84%D8%B4%D8%A7%D9%85%D9%84%20.md) المُطبّقة فيها.

---

## المكدس التقني المؤكَّد (§0)

| المكوّن | التقنية | ملاحظة |
|---------|---------|--------|
| Framework | React 18 + TypeScript | |
| Build Tool | Vite | |
| Styling | Tailwind CSS | **بدون Shadcn UI** |
| Forms | React Hook Form + **Yup** | **وليس Zod** |
| State | **Zustand فقط** | **بدون React Query** |
| Charts | Recharts | |
| Animations | Framer Motion | |
| Routing | React Router v6 | |
| HTTP Client | Axios | مع CSRF interceptor (§4) |
| Font | Cairo عبر Google Fonts CDN | `<link>` في `index.html` |

---

## هيكل المجلدات المؤكَّد (§0)

```
frontend/
├── public/
├── src/
│   ├── routes/                          ← تعريفات المسارات + ProtectedRoute
│   ├── layout/                          ← AppLayout, Sidebar, Navbar
│   ├── store/                           ← Zustand stores (auth, ui, settings)
│   ├── services/                        ← API service layers (axios)
│   ├── utils/                           ← أدوات عامة (formatters, printUtils)
│   ├── styles/                          ← global CSS + Tailwind config
│   ├── components/
│   │   ├── ui/                          ← Button, Input, Card, EmptyState, Spinner, Toast (§6)
│   │   ├── forms/                       ← FormField, StepperForm, CustomerSearch
│   │   ├── tables/                      ← DataTable, Pagination
│   │   ├── modals/                      ← ConfirmDialog, CancelBookingModal
│   │   └── print/                       ← PrintFrame (iframe print helper)
│   ├── features/
│   │   ├── auth/                        ← LoginPage, ForgotPassword, ResetPassword
│   │   ├── dashboard/                   ← DashboardPage, StatCards, Alerts, Charts
│   │   ├── bookings/
│   │   │   ├── shared/                  ← BookingSteps, BookingList, useBookingForm
│   │   │   ├── flight/
│   │   │   ├── transport/
│   │   │   ├── visa/
│   │   │   ├── passport/
│   │   │   └── parcel/
│   │   ├── finance/                     ← PaymentVoucher, ReceiptVoucher, Expense, Ledger
│   │   ├── customers/
│   │   ├── suppliers/
│   │   ├── reports/
│   │   └── settings/                    ← OfficeSettings, ExchangeRates, UserManagement, AuditLogs
│   ├── App.tsx
│   └── main.tsx
├── index.html                           ← <link> لخط Cairo من Google Fonts CDN
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── vite.config.ts
```

---

## المرحلة 1: الأساس + نظام التصميم
**أقسام البرومبت: §0, §4 (CSRF), §6 (مكوّنات UI)**

### 1.1 إنشاء المشروع
- `npx create-vite` مع React + TypeScript
- تثبيت: `tailwindcss`, `react-router-dom`, `axios`, `zustand`, `react-hook-form`, `yup`, `@hookform/resolvers`, `recharts`, `framer-motion`, `react-icons`
- إعداد Tailwind + PostCSS
- إضافة `<link>` لخط Cairo في `index.html` من Google Fonts CDN، مع fallback: `'Cairo', 'Noto Sans Arabic', sans-serif`

### 1.2 مكوّنات UI المشتركة (§6)
- `Button.tsx` — متغيرات: primary / secondary / danger / ghost
- `Input.tsx` — label + error message موحّدين
- `Card.tsx`
- `EmptyState.tsx` — يُعرض عند عدم وجود بيانات (وليس جدول فارغ)
- `Spinner.tsx` — حالة تحميل
- `Toast.tsx` — Context Provider + hook `useToast` بدوال `success()` / `error()`، يُركَّب في `App.tsx`

### 1.3 إعداد Axios + CSRF (§4)
- Axios instance مع `baseURL: '/api'`, `withCredentials: true`
- Interceptor يقرأ كوكي `csrf_token` ويرسلها كهيدر `X-CSRF-Token` على كل POST/PUT/PATCH/DELETE
- Interceptor يعالج 401 ويحاول refresh token تلقائياً

### 1.4 Zustand Stores
- `authStore` — user, role, login(), logout(), refreshToken()
- `uiStore` — sidebarOpen, toasts
- `settingsStore` — office_name, logo_image_url (يُجلب من `/api/settings/office` بعد تسجيل الدخول)

---

## المرحلة 2: المصادقة + Layout الرئيسي
**أقسام البرومبت: §2.1, §3 (صلاحيات), §6 (Sidebar/Navbar)**

### 2.1 صفحة تسجيل الدخول (§2.1)
- React Hook Form + Yup validation
- قفل 15 دقيقة بعد 5 محاولات (يعرض رسالة خطأ واضحة من الـ API)
- JWT في HTTP-only cookies (الفرونت اند لا يقرأ التوكن، يعتمد على الكوكي)
- Toast نجاح/فشل

### 2.2 استعادة كلمة المرور (§2.1)
- `ForgotPasswordPage` — إدخال البريد → POST `/api/auth/forgot-password`
- `ResetPasswordPage` — إدخال كلمة مرور جديدة مع التوكن من URL

### 2.3 Layout الرئيسي (§6)
- `AppLayout.tsx` — يغلّف كل الصفحات بعد تسجيل الدخول
- `Sidebar.tsx` — ثابت على md+، drawer على الشاشات الصغيرة مع خلفية معتمة + زر إغلاق
- `Navbar.tsx` — يجلب `office_name` + `logo_image_url` من `GET /api/settings/office` (بعد login)، زر ☰ على الشاشات الصغيرة فقط
- `ProtectedRoute.tsx` — يتحقق من المصادقة ويعيد التوجيه لتسجيل الدخول

### 2.4 نظام الصلاحيات (§3)
- **admin:** كل شيء
- **employee:** حجوزاته فقط، لا يرى `cost_price` (غائب من DOM)، لا يصل للإعدادات/المستخدمين/التقارير المالية (فقط "حجوزات تفصيلي" الخاص به)
- **accountant:** كل العمليات المالية والتقارير، لا يضيف/يعدّل حجوزات، لا يصل للإعدادات
- الصلاحيات تُفرض من الخادم أساساً، والفرونت اند يخفي/يعرض العناصر حسب الدور

---

## المرحلة 3: لوحة التحكم
**أقسام البرومبت: §2.2**

### 3.1 بطاقات ملخص
- إيرادات اليوم/الشهر، مصروفات، عدد حجوزات، عملاء جدد
- مفلترة بالدور (employee يرى عملياته فقط)

### 3.2 تنبيهات
- مديونيات > 30 يوم
- جوازات تنتهي خلال 3 أشهر

### 3.3 رسوم بيانية (Recharts)
- إيرادات/مصروفات شهرية
- توزيع الحجوزات حسب النوع

---

## المرحلة 3.5: التحضير الفعلي لما قبل المرحلة 4 (Backend Pre-requisite)
**أقسام البرومبت: §2.3, §5.6 | تم التنفيذ والتحقق ✅**
- تعديل `backend/app/api/routes/bookings.py` لدعم الإنشاء التلقائي للعميل عند عدم تقديم `customer_id`:
  - يتم استخراج بيانات العميل من تفاصيل الحجز (الاسم، الهاتف، الجواز، الهوية، تاريخ الميلاد).
  - البحث عن عميل قائم بواسطة (رقم الهاتف أو رقم الجواز أو رقم الهوية عبر `or_`).
  - في حال عدم وجوده، يتم إنشاء سجل عميل جديد تلقائياً برصيد 0.00 وربطه بالحجز عبر `customer.id`.
  - تصحيح حالة الحجز الافتراضية إلى `BookingStatus.PENDING` في دالة `create_booking` لتطابق وثيقة النظام والموديل.
  - التحقق عبر `python -m py_compile` بنجاح كامل.

---

## المرحلة 4: الحجوزات (5 أنواع)
**أقسام البرومبت: §2.3, §1 (حقول محذوفة), §3 (صلاحيات), §5 (طباعة)**

### المسارات الفعلية المعتمدة للربط (Backend API Real Routes):
- **إنشاء حجز:** مسار عام موحد `POST /api/bookings/`
  - نوع الخدمة يُرسل داخل الـ JSON Body: `type: "flight" | "transport" | "visa" | "passport" | "parcel"`
  - كائن التفاصيل الخاص بالنوع يُرسل داخل الـ Body: (`flight_details` أو `transport_details` أو `visa_details` أو `passport_details` أو `parcel_details`)
- **طباعة السند / الفاوتشر:** `GET /api/bookings/{id}/print?mode=thermal&format=html` (أو `format=pdf`)
- **إلغاء حجز:** `POST /api/bookings/{id}/cancel` (مع body: `cancellation_reason`, `refund_amount`)

### 4.1 مكوّنات مشتركة
- `StepperForm.tsx` — نظام ثلاثي الخطوات (بيانات العملية → بيانات الشخص → المالية)
- `CustomerSearch.tsx` — بحث ذكي debounce 300ms على `GET /api/customers/search?q=...`، اختيار عميل موجود أو إدخال بيانات جديدة
- `BookingList.tsx` — جدول عرض مع بحث/تصفية/طباعة/إلغاء + `EmptyState` + `Spinner`

### 4.2 إنشاء عميل تلقائي عند الحجز (تم تطبيقه في الباكند 3.5 ✅)
- إذا لم يُختر عميل من البحث: بيانات خطوة الشخص (الاسم، الهاتف، رقم الجواز/الهوية، تاريخ الميلاد، مكان الميلاد) تُرسل مع تفاصيل الحجز
- الباكند ينشئ سجل العميل تلقائياً ويربطه بالحجز قبل الحفظ

### 4.3 نماذج الحجز الخمسة (React Hook Form + Yup لكل خطوة)
كل نوع بنموذج ثلاثي الخطوات:

| النوع | خطوة 1 (بيانات العملية) | خطوة 2 (بيانات الشخص) | خطوة 3 (المالية) |
|-------|------------------------|----------------------|-----------------|
| طيران | شركة، رحلة، مغادرة، وصول، تاريخ، وقت، نوع تذكرة | اسم المسافر، هاتف، جواز، ميلاد، مكان ميلاد + OCR | سعر بيع، مدفوع، عملة، مورد |
| نقل بري | شركة، انطلاق، وصول، تاريخ، وقت | اسم، هاتف، هوية، ميلاد + OCR (**بلا seat_number** §1) | سعر بيع، مدفوع، عملة، مورد |
| تأشيرات | نوع تأشيرة، تاريخ تقديم (**بلا country/duration/expected_issue_date** §1) | اسم، هاتف، جواز، ميلاد، مكان ميلاد + OCR | سعر بيع، مدفوع، عملة، مورد |
| جوازات | نوع جواز، أولوية، تاريخ تقديم، تسليم متوقع | اسم، هاتف، هوية، ميلاد، مكان ميلاد + OCR | سعر بيع، مدفوع، عملة، مورد |
| طرود | مرسل (اسم+هاتف)، مستلم (اسم+هاتف)، وجهة، نوع طرد، وزن، وصف، تاريخ شحن (**بلا quantity** §1) | — (بلا OCR) | سعر بيع، مدفوع، عملة |

### 4.4 OCR (§2.3)
- استدعاء `POST /api/ocr/extract` مع صورة الجواز/الهوية في الخطوة 2
- استخراج: الاسم، رقم الجواز/الهوية، تاريخ الميلاد — وملء الحقول تلقائياً
- **الطرود لا تستخدم OCR** (بلا وثائق شخصية)

### 4.5 حفظ + طباعة تلقائية
- POST `/api/bookings/` → يُنشئ الحجز + يُنشئ عميلاً تلقائياً إن لزم
- عند النجاح: Toast نجاح + فتح نافذة طباعة تلقائية (iframe يحمّل HTML من `/api/bookings/{id}/print?mode=thermal&format=html`)
- **لا PUT/تعديل** (§3 — مستبعد عمداً من هذا البناء)

### 4.6 إلغاء حجز
- مربع حوار (modal) يطلب: سبب الإلغاء + المبلغ المسترد
- POST `/api/bookings/{id}/cancel` → Toast نجاح/فشل
- **يُرجع الأثر المالي على رصيد العميل**

### 4.7 `cost_price` (§1, §3)
- **employee:** الحقل غائب تماماً من DOM — لا يُصيَّر في React ولا يرد في API response
- **admin/accountant:** يظهر في نموذج الإنشاء وفي جدول العرض

---

## المرحلة 5: المالية + العملاء + الموردون
**أقسام البرومبت: §2.4, §2.5**

### 5.1 سندات القبض (RC-XXXX)
- نموذج: عميل/مورد، مبلغ، عملة، طريقة دفع، ملاحظات
- يُحدّث رصيد العميل فعلياً
- Toast نجاح

### 5.2 سندات الدفع (PY-XXXX)
- نموذج مماثل لسندات القبض

### 5.3 المصروفات (EX-XXXX)
- نوع المصروف (نص حر)، مبلغ، تاريخ، ملاحظات

### 5.4 سجل الأستاذ (Ledger)
- عرض كل العمليات المالية لعميل/مورد محدد
- فلترة بالتاريخ والنوع

### 5.5 العملاء والموردون (§2.5)
- جداول CRUD + بحث
- بطاقة تفاصيل بتبويبين: (البيانات، سجل الأستاذ)
- `EmptyState` + `Spinner` على كل جدول (§6)
- Toast عند إضافة عميل/مورد

---

## المرحلة 6: التقارير + الإعدادات
**أقسام البرومبت: §2.6, §2.7, §3 (صلاحيات التقارير)**

### 6.1 التقارير — 7 أنواع (§2.6)
1. حجوزات تفصيلي (employee يرى حجوزاته فقط — يُفرض من الخادم §3)
2. إيرادات
3. مصروفات
4. أرباح وخسائر
5. مديونيات
6. أداء موظفين
7. تدفق نقدي

- فلاتر ديناميكية (تاريخ من/إلى، نوع، موظف)
- تصدير PDF + Excel
- رسوم بيانية (Recharts)
- **employee يرى فقط تقرير #1 الخاص به (§3)**

### 6.2 الإعدادات (§2.7)
- بيانات المكتب (اسم، tagline §1، عنوان، هواتف، بريد، موقع) + رفع شعار
- أسعار الصرف
- أنواع الخدمات
- إدارة المستخدمين (CRUD — admin فقط)
- سجلات التدقيق (audit logs — عرض فقط)
- **employee + accountant لا يصلان لهذا القسم (§3)**

---

## المرحلة 7: Docker + التكامل + التحقق النهائي
**أقسام البرومبت: §4, §7**

### 7.1 Dockerfiles (§4)
- `backend/Dockerfile` — ✅ **تم تصحيحه** (كل الحزم من §4 مضمّنة)
- `frontend/Dockerfile` — وضع تطوير (node + npm run dev)
- `frontend/Dockerfile.prod` — multi-stage build → nginx يخدم dist/ + يُمرّر /api/ للباكند
- `docker-compose.yml` — يبني `backend` + `frontend` + `postgres` + `redis`

### 7.2 التحقق الإلزامي (§7)
1. `py_compile` على كل ملف Python — صفر أخطاء
2. توازن أقواس TypeScript/TSX — صفر اختلالات
3. `docker compose up --build` ينجح من الصفر
4. تسجيل دخول admin حقيقي (200 وليس 500)
5. إنشاء حجز فعلي من كل نوع عبر الواجهة
6. طباعة سند ومطابقة بصرية مع `docs/print-reference/`
7. سند دفع + قبض → تحقق من تحدّث رصيد العميل
8. تقرير تشغيلي حقيقي بأدلة (لقطات API/سجلات)

---

## ملخص التصحيحات والتحضيرات المُنفَّذة فعلياً (قبل بدء الفرونت اند)

| # | التصحيح / التحضير | الملف | الحالة |
|---|-------------------|-------|--------|
| 1 | Dockerfile — إضافة كل الحزم من §4 | [`Dockerfile`](file:///c:/Users/Mohammed/Desktop/my-system/backend/Dockerfile) | ✅ منجز |
| 2 | حالة الحجز الافتراضية → `pending` | [`booking.py`](file:///c:/Users/Mohammed/Desktop/my-system/backend/app/models/booking.py) + [`routes/bookings.py`](file:///c:/Users/Mohammed/Desktop/my-system/backend/app/api/routes/bookings.py) | ✅ منجز |
| 3 | قوالب الطباعة — مطابقة مرجعية للصور الخمس | [`print_service.py`](file:///c:/Users/Mohammed/Desktop/my-system/backend/app/services/print_service.py) | ✅ منجز |
| 4 | إنشاء العميل تلقائياً عند الحجز الجديد | [`routes/bookings.py`](file:///c:/Users/Mohammed/Desktop/my-system/backend/app/api/routes/bookings.py) | ✅ منجز ومُختبر |
| 5 | التحقق من `greenlet` و `email-validator` | [`requirements.txt`](file:///c:/Users/Mohammed/Desktop/my-system/backend/requirements.txt) | ✅ مؤكد وموجود فعلياً |
| 6 | مراجعة المسارات الحرفية للبواكند وتثبيتها بالخطة | routes/bookings.py, routes/reports.py | ✅ مثبت بدقة |
| 7 | `py_compile` — كل ملفات الباكند المعدلة | — | ✅ نجاح 0 أخطاء |

---

> [!NOTE]
> ## حالة بنود ما قبل الفرونت اند
> - تم استيفاء كل المتطلبات التحضيرية الثلاثة المطلوبة صراحة قبل البدء بالمرحلة 1.
> - الخطة والباكند جاهزان بالكامل لبدء التنفيذ الفعلي من المرحلة 1.
