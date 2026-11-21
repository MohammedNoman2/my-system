import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.settings import Settings
from app.core.config import format_office_dt

logger = logging.getLogger("arp.print")

# Resolve the fonts directory relative to this file
# Works both on local dev (Windows) and inside Docker (Linux)
FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"


def _font_face_css() -> str:
    """Generate @font-face declarations pointing to local Cairo .ttf files."""
    regular = (FONTS_DIR / "Cairo-Regular.ttf").as_uri()
    bold = (FONTS_DIR / "Cairo-Bold.ttf").as_uri()
    return f"""
        @font-face {{
            font-family: 'Cairo';
            src: url('{regular}') format('truetype');
            font-weight: normal;
            font-style: normal;
        }}
        @font-face {{
            font-family: 'Cairo';
            src: url('{bold}') format('truetype');
            font-weight: bold;
            font-style: normal;
        }}
    """

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    WEASYPRINT_AVAILABLE = False
    logger.warning(f"WeasyPrint native libraries not loaded on this host ({e}). HTML printing is fully active; PDF generation will use fallback.")

POLICIES = {
    BookingType.FLIGHT: "سياسة الإلغاء: يخصم 25% قبل 24 ساعة من موعد الرحلة. الإلغاء يوم الرحلة يعتبر الراكب متخلفاً وتفقد التذكرة قيمتها.<br/>سياسة التأجيل: التأجيل قبل 48 ساعة مجاناً، وقبلها بـ 24 ساعة بغرامة 25%. التأجيل يوم الرحلة غرامة 50%.<br/>سياسة العفش: يسمح للراكب بوزن 40 كجم مجاناً وما زاد يدفع بسعر الكيلو الزائد عند التحميل.",
    BookingType.TRANSPORT: "سياسة الإلغاء: يخصم 25% قبل 24 ساعة من موعد الرحلة. الإلغاء في يوم الرحلة يعتبر الراكب متخلفاً وتفقد التذكرة قيمتها.<br/>سياسة التأجيل: التأجيل قبل 48 ساعة مجاناً، ومن 48 إلى 24 ساعة غرامة 25%. التأجيل يوم الرحلة غرامة 50%.<br/>سياسة العفش: لكل راكب 40 كيلوجرام مجاناً، الوزن الزائد يتم احتسابه بسعر 4 ريال سعودي لكل كيلوجرام إضافي.",
    BookingType.VISA: "سياسة التأشيرات: المكتب غير مسؤول عن رفض التأشيرة من قبل السفارات، وسيتم خصم رسوم الخدمة في حال الرفض.<br/>المتطلبات: يجب توفير كافة الوثائق المطلوبة للتقديم في الوقت المحدد، أي تأخير قد يؤثر على موعد صدور التأشيرة.<br/>التواصل: سيتم إخطاركم عبر الواتساب فور صدور التأشيرة لمراجعة المكتب أو لإرسالها إليكم إلكترونياً.",
    BookingType.PASSPORT: "سياسة الاستلام: يجب إبراز هذا السند عند مراجعة المكتب لاستلام الجواز. المكتب غير مسؤول عن السندات المفقودة.<br/>المدة الزمنية: تستغرق معاملة الجواز العادي من 7-10 أيام عمل، والمستعجل من 2-4 أيام عمل من تاريخ توريد الملف للجهات المختصة.<br/>التواصل: سيتم إبلاغكم عبر رسالة نصية أو واتساب فور جاهزية الجواز للاستلام.",
    BookingType.PARCEL: "سياسة الشحن: المكتب غير مسؤول عن المحتويات القابلة للكسر أو التلف في حال عدم التغليف الجيد. يجب فحص الطرد عند الاستلام.<br/>سياسة الضياع: في حال فقدان الطرد، يتم التعويض بحد أقصى ضعف قيمة الشحن إلا إذا تم التأمين على محتويات الطرد مسبقاً.<br/>التخزين: يتم الاحتفاظ بالطرد لمدة 7 أيام في فرع الوصول، تفرض رسوم أرضية بعد ذلك بمقدار 500 ريال يومياً.",
}

TITLES = {
    BookingType.FLIGHT: "تذكرة طيران",
    BookingType.TRANSPORT: "تذكرة سفر",
    BookingType.VISA: "سند تأشيرات",
    BookingType.PASSPORT: "سند جوازات",
    BookingType.PARCEL: "بوليسة شحن",
}


def build_cell_html(label: str, value: Any, bold_value: bool = True) -> str:
    val_str = str(value) if value is not None and str(value).strip() != "" else "--"
    weight_class = "font-bold" if bold_value else "font-normal"
    return f"""
    <td style="border: 1px solid #1f2937; padding: 6px 8px; vertical-align: middle; text-align: right; font-size: 13px;">
        <span style="color: #4b5563; font-size: 11px; display: inline-block; margin-left: 6px;">{label}:</span>
        <span class="{weight_class}" style="color: #111827; font-weight: {'bold' if bold_value else 'normal'};">{val_str}</span>
    </td>
    """


def build_field_table_html(rows: List[List[Dict[str, Any]]]) -> str:
    """
    RTL Table Builder:
    Builds a 5 rows x 3 columns table.
    Each row is passed logically as [right_field, middle_field, left_field].
    Per strict instruction, we iterate reversed(row) when generating <td> tags
    so that under dir="rtl" the browser/WeasyPrint maps them visually correctly.
    """
    table_rows_html = []
    for row in rows:
        cells_html = []
        for cell in reversed(row):
            label = cell.get("label", "")
            val = cell.get("value", "--")
            bold = cell.get("bold", True)
            cells_html.append(build_cell_html(label, val, bold))
        row_str = f"<tr>{''.join(cells_html)}</tr>"
        table_rows_html.append(row_str)

    return f"""
    <table style="width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 12px; border: 1.5px solid #1f2937;">
        <tbody>
            {''.join(table_rows_html)}
        </tbody>
    </table>
    """


def get_booking_rows(booking: Booking) -> List[List[Dict[str, Any]]]:
    curr = booking.currency or "YER"
    total_price = f"{booking.selling_price:,.2f} {curr}"
    paid = f"{booking.paid_amount:,.2f} {curr}"
    remaining = f"{booking.remaining_amount:,.2f} {curr}"
    date_str = format_office_dt(booking.booking_date)
    emp_name = booking.employee.full_name if booking.employee else "مدير النظام"
    notes = booking.notes or "لا توجد ملاحظات إضافية"

    if booking.status == BookingStatus.CANCELLED or str(booking.status) == "cancelled":
        status_ar = "ملغي"
    elif booking.remaining_amount == 0 and booking.paid_amount > 0:
        status_ar = "مؤكد (مسدد بالكامل)"
    elif booking.paid_amount > 0:
        status_ar = "مؤكد (مدفوع جزئياً)"
    else:
        status_ar = "معلق (آجل)"

    financial_row = [
        {"label": "المتبقي", "value": remaining, "bold": True},
        {"label": "المبلغ المدفوع", "value": paid, "bold": True},
        {"label": "السعر الإجمالي", "value": total_price, "bold": True},
    ]

    rows: List[List[Dict[str, Any]]] = []

    if booking.type == BookingType.FLIGHT:
        fd = booking.flight_details
        rows = [
            [
                {"label": "رقم الجواز", "value": fd.passport_number if fd else "--", "bold": True},
                {"label": "رقم الهاتف", "value": fd.passenger_phone if fd else "--", "bold": True},
                {"label": "اسم المسافر", "value": fd.passenger_name if fd else "--", "bold": True},
            ],
            [
                {"label": "تاريخ السفر", "value": f"{fd.departure_date} {fd.departure_time}" if fd else "--", "bold": True},
                {"label": "إلى الوصول", "value": fd.arrival_airport if fd else "--", "bold": True},
                {"label": "من المغادرة", "value": fd.departure_airport if fd else "--", "bold": True},
            ],
            [
                {"label": "وقت الحضور", "value": "قبل 3 ساعات", "bold": True},
                {"label": "شركة الطيران", "value": fd.airline_company if fd else "--", "bold": True},
                {"label": "الرحلة", "value": f"{fd.flight_number} ({'ذهاب وعودة' if fd and fd.ticket_type == 'roundtrip' else 'ذهاب فقط'})" if fd else "--", "bold": True},
            ],
            [
                {"label": "الحالة", "value": status_ar, "bold": True},
                {"label": "تفاصيل إضافية", "value": notes, "bold": False},
                {"label": "تاريخ الإصدار", "value": date_str, "bold": False},
            ],
            financial_row,
        ]

    elif booking.type == BookingType.TRANSPORT:
        td = booking.transport_details
        rows = [
            [
                {"label": "اليوم", "value": str(td.travel_date) if td else "--", "bold": True},
                {"label": "رقم الهاتف", "value": td.passenger_phone if td else "--", "bold": True},
                {"label": "اسم الراكب", "value": td.passenger_name if td else "--", "bold": True},
            ],
            [
                {"label": "وقت الرحلة", "value": str(td.travel_time) if td else "--", "bold": True},
                {"label": "إلى الوصول", "value": td.arrival_station if td else "--", "bold": True},
                {"label": "من الانطلاق", "value": td.departure_station if td else "--", "bold": True},
            ],
            [
                {"label": "الموظف المصدر", "value": emp_name, "bold": True},
                {"label": "رقم الهوية", "value": td.id_number if td else "--", "bold": True},
                {"label": "شركة النقل", "value": td.transport_company if td else "--", "bold": True},
            ],
            [
                {"label": "ملاحظات", "value": notes, "bold": False},
                {"label": "الحالة", "value": status_ar, "bold": True},
                {"label": "تاريخ الإصدار", "value": date_str, "bold": False},
            ],
            financial_row,
        ]

    elif booking.type == BookingType.VISA:
        vd = booking.visa_details
        app_date_str = str(vd.application_date) if vd and vd.application_date else date_str
        rows = [
            [
                {"label": "تاريخ التقديم", "value": app_date_str, "bold": True},
                {"label": "رقم الهاتف", "value": vd.applicant_phone if vd else "--", "bold": True},
                {"label": "اسم المتقدم", "value": vd.applicant_name if vd else "--", "bold": True},
            ],
            [
                {"label": "مكان الميلاد", "value": vd.birth_place if vd else "--", "bold": True},
                {"label": "نوع التأشيرة", "value": vd.visa_type if vd else "--", "bold": True},
                {"label": "رقم الجواز", "value": vd.passport_number if vd else "--", "bold": True},
            ],
            [
                {"label": "الحالة", "value": status_ar, "bold": True},
                {"label": "رقم المرجع", "value": booking.ticket_number, "bold": True},
                {"label": "الموظف المسؤول", "value": emp_name, "bold": True},
            ],
            [
                {"label": "تاريخ الإصدار", "value": date_str, "bold": False},
                {"label": "تاريخ الميلاد", "value": str(vd.birth_date) if vd and vd.birth_date else "--", "bold": True},
                {"label": "ملاحظات المعاملة", "value": notes, "bold": False},
            ],
            financial_row,
        ]

    elif booking.type == BookingType.PASSPORT:
        pd = booking.passport_details
        pt_ar = {"new": "جديد", "renewal": "تجديد", "lost": "بدل فاقد", "damaged": "بدل تالف"}.get(
            pd.passport_type.value if pd and hasattr(pd.passport_type, "value") else "new", "جديد"
        )
        prio_ar = "مستعجل" if pd and (getattr(pd.priority, "value", pd.priority) == "urgent") else "عادي"
        rows = [
            [
                {"label": "تاريخ الاستلام", "value": date_str, "bold": False},
                {"label": "رقم الهاتف", "value": pd.applicant_phone if pd else "--", "bold": True},
                {"label": "اسم المتقدم", "value": pd.applicant_name if pd else "--", "bold": True},
            ],
            [
                {"label": "الأولوية", "value": prio_ar, "bold": True},
                {"label": "رقم الهوية الوطنية", "value": pd.id_number if pd else "--", "bold": True},
                {"label": "نوع الجواز", "value": pt_ar, "bold": True},
            ],
            [
                {"label": "حالة الطلب", "value": status_ar, "bold": True},
                {"label": "رقم المرجع", "value": booking.ticket_number, "bold": True},
                {"label": "الموظف المسؤول", "value": emp_name, "bold": True},
            ],
            [
                {"label": "تاريخ الميلاد", "value": str(pd.birth_date) if pd and pd.birth_date else "--", "bold": True},
                {"label": "تاريخ التسليم المتوقع", "value": str(pd.expected_delivery_date) if pd and pd.expected_delivery_date else "حسب الجوازات", "bold": True},
                {"label": "ملاحظات المعاملة", "value": notes, "bold": False},
            ],
            financial_row,
        ]

    elif booking.type == BookingType.PARCEL:
        pld = booking.parcel_details
        ship_date = str(pld.shipping_date) if pld and pld.shipping_date else date_str
        rows = [
            [
                {"label": "تاريخ الشحن", "value": ship_date, "bold": True},
                {"label": "هاتف المرسل", "value": pld.sender_phone if pld else "--", "bold": True},
                {"label": "المرسل", "value": pld.sender_name if pld else "--", "bold": True},
            ],
            [
                {"label": "إلى الوجهة", "value": pld.delivery_destination if pld else "--", "bold": True},
                {"label": "هاتف المستلم", "value": pld.receiver_phone if pld else "--", "bold": True},
                {"label": "المستلم", "value": pld.receiver_name if pld else "--", "bold": True},
            ],
            [
                {"label": "نوع الطرد", "value": pld.parcel_type if pld else "--", "bold": True},
                {"label": "وصف الطرد", "value": pld.content_description or pld.parcel_type if pld else "--", "bold": True},
                {"label": "الوزن التقديري", "value": f"{pld.weight} كجم" if pld else "--", "bold": True},
            ],
            [
                {"label": "الحالة", "value": status_ar, "bold": True},
                {"label": "الموظف", "value": emp_name, "bold": True},
                {"label": "ملاحظات الشحن", "value": notes, "bold": False},
            ],
            financial_row,
        ]

    return rows

def generate_voucher_html(booking: Booking, office_settings: Settings, mode: str = "thermal") -> str:
    title = TITLES.get(booking.type, "سند حجز")
    policy = POLICIES.get(booking.type, "")
    rows = get_booking_rows(booking)
    table_html = build_field_table_html(rows)

    if office_settings.logo_image_url and os.path.exists(office_settings.logo_image_url):
        logo_content = f'<img src="{office_settings.logo_image_url}" style="max-width: 100%; max-height: 75px; object-fit: contain;" />'
    else:
        logo_content = f'<div style="font-size: 14px; font-weight: bold; color: #111827; text-align: center;">{office_settings.office_name}</div>'

    is_thermal = (mode == "thermal")
    container_width = "76mm" if is_thermal else "280mm"
    container_padding = "2mm" if is_thermal else "20px"

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>{title} - {booking.ticket_number}</title>
    <style>
        {_font_face_css()}
        @page {{
            size: {'80mm 60mm' if is_thermal else 'A4 landscape'};
            margin: {'2mm' if is_thermal else '10mm'};
        }}
        * {{
            box-sizing: border-box;
            font-family: 'Cairo', 'Noto Sans Arabic', sans-serif;
        }}
        body {{
            margin: 0;
            padding: 0;
            background: #ffffff;
            direction: rtl;
            font-size: {'9px' if is_thermal else '12px'};
            color: #111827;
        }}
        .voucher-container {{
            width: {container_width};
            max-width: 100%;
            margin: 0 auto;
            padding: {container_padding};
            background: #ffffff;
        }}
        .header {{
            display: flex;
            flex-direction: row-reverse;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #111827;
            padding-bottom: 8px;
            margin-bottom: 6px;
        }}
        .logo-box {{
            width: 110px;
            height: 75px;
            border: 1.5px solid #374151;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4px;
        }}
        .center-info {{
            text-align: center;
            flex-grow: 1;
        }}
        .center-title {{
            font-size: 22px;
            font-weight: 900;
            margin: 0;
            color: #000000;
        }}
        .center-ref {{
            font-size: 15px;
            font-weight: bold;
            margin-top: 4px;
            color: #374151;
            direction: ltr;
        }}
        .office-identity {{
            text-align: right;
            max-width: 260px;
        }}
        .office-name {{
            font-size: 18px;
            font-weight: 900;
            color: #000000;
            margin: 0;
        }}
        .office-tagline {{
            font-size: 12px;
            font-weight: 700;
            color: #374151;
            margin: 2px 0;
        }}
        .office-address {{
            font-size: 10px;
            color: #4b5563;
            margin: 1px 0;
        }}
        .office-phones {{
            font-size: 10px;
            font-weight: bold;
            color: #1f2937;
            margin: 1px 0;
            direction: ltr;
            text-align: right;
        }}
        .policy-box {{
            font-size: 9px;
            color: #4b5563;
            line-height: 1.35;
            border-top: 1px solid #d1d5db;
            padding-top: 6px;
            margin-top: 4px;
        }}
        .footer {{
            text-align: center;
            font-size: 11px;
            font-weight: bold;
            color: #111827;
            margin-top: 8px;
            padding-top: 4px;
            border-top: 1.5px solid #111827;
        }}
    </style>
</head>
<body>
    <div class="voucher-container">
        <div class="header">
            <div class="logo-box">
                {logo_content}
            </div>
            <div class="center-info">
                <h1 class="center-title">{title}</h1>
                <div class="center-ref">رقم: {booking.ticket_number}</div>
            </div>
            <div class="office-identity">
                <div class="office-name">{office_settings.office_name}</div>
                <div class="office-tagline">{office_settings.tagline}</div>
                <div class="office-address">{office_settings.address}</div>
                <div class="office-phones">{office_settings.phone_numbers}</div>
            </div>
        </div>

        {table_html}

        <div class="policy-box">
            {policy}
        </div>

        <div class="footer">
            {office_settings.footer_text}
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_voucher_pdf(booking: Booking, office_settings: Settings, mode: str = "thermal") -> bytes:
    html_content = generate_voucher_html(booking, office_settings, mode)
    if WEASYPRINT_AVAILABLE:
        return HTML(string=html_content).write_pdf()
    else:
        # Fallback to HTML string encoded as bytes if weasyprint dynamic library is absent on host
        return html_content.encode("utf-8")


def generate_financial_voucher_html(
    voucher: Any,
    entity_name: str,
    entity_phone: Optional[str],
    office_settings: Optional[Settings],
    allocations: List[Dict[str, Any]],
    issued_by_name: str,
    mode: str = "thermal",
) -> str:
    """توليد قالب HTML رسمي لطباعة سند القبض (RC) أو سند الصرف (PY) بوضع حراري أو A4."""
    if not office_settings:
        office_settings = Settings()

    tx_type_val = voucher.type.value if hasattr(voucher.type, "value") else str(voucher.type)
    is_receipt = tx_type_val == "payment_in"
    title = "سند قبض" if is_receipt else "سند صرف"
    entity_label = "استلمنا من السيد / السادة" if is_receipt else "صرفنا للسيد / السادة"

    pm_val = voucher.payment_method.value if hasattr(voucher.payment_method, "value") else str(voucher.payment_method)
    pm_ar = {
        "cash": "نقداً (الصندوق)",
        "bank_transfer": "حوالة / تحويل بنكي",
        "check": "شيك مصرفي",
    }.get(pm_val, pm_val)

    curr = getattr(voucher, "currency", "YER") or "YER"
    amount_str = f"{voucher.amount:,.2f} {curr}"
    date_str = str(voucher.transaction_date) if voucher.transaction_date else "--"
    ref_num = getattr(voucher, "reference_number", None) or "--"
    notes = getattr(voucher, "notes", None) or "لا توجد ملاحظات إضافية"
    is_void = getattr(voucher, "is_void", False)
    status_str = f"ملغي ({getattr(voucher, 'void_reason', '') or ''})" if is_void else "معتمد ونشط"

    rows = [
        [
            {"label": "التاريخ", "value": date_str, "bold": True},
            {"label": "رقم الهاتف", "value": entity_phone or "--", "bold": True},
            {"label": entity_label, "value": entity_name or "--", "bold": True},
        ],
        [
            {"label": "رقم المرجع / الحوالة", "value": ref_num, "bold": True},
            {"label": "طريقة الدفع", "value": pm_ar, "bold": True},
            {"label": "المبلغ والعملة", "value": amount_str, "bold": True},
        ],
        [
            {"label": "حالة السند", "value": status_str, "bold": True},
            {"label": "الموظف المصدر", "value": issued_by_name or "النظام", "bold": True},
            {"label": "البيان والملاحظات", "value": notes, "bold": False},
        ],
    ]
    table_html = build_field_table_html(rows)

    alloc_html = ""
    if allocations:
        total_alloc_dec = sum((Decimal(str(a.get("allocated_amount") or 0)) for a in allocations), Decimal("0.00"))
        surplus_dec = (Decimal(str(voucher.amount or 0)) - total_alloc_dec).quantize(Decimal("0.01"))
        alloc_rows = "".join(
            f"<tr>"
            f"<td style='border:1px solid #1f2937;padding:4px 6px;text-align:center;font-weight:bold;'>{a.get('ticket_number') or ('#' + str(a.get('booking_id')))}</td>"
            f"<td style='border:1px solid #1f2937;padding:4px 6px;text-align:center;'>{float(a.get('allocated_amount') or 0):,.2f} {curr}</td>"
            f"<td style='border:1px solid #1f2937;padding:4px 6px;text-align:center;'>{a.get('exchange_rate')}</td>"
            f"<td style='border:1px solid #1f2937;padding:4px 6px;text-align:center;'>{float(a.get('allocated_in_booking_currency') or 0):,.2f} {a.get('target_currency')}</td>"
            f"</tr>"
            for a in allocations
        )
        surplus_note = ""
        if is_receipt and surplus_dec > Decimal("0.00"):
            surplus_note = (
                f"<div style='margin-top:4px;font-size:11px;font-weight:bold;color:#065f46;'>"
                f"فائض غير مخصص (مرحل كرصيد دائن للعميل): {surplus_dec:,.2f} {curr}</div>"
            )
        alloc_html = f"""
        <div style="margin-top:8px;margin-bottom:8px;">
            <div style="font-size:11px;font-weight:bold;margin-bottom:4px;">تفاصيل تخصيص السداد على التذاكر:</div>
            <table style="width:100%;border-collapse:collapse;font-size:11px;border:1px solid #1f2937;">
                <thead>
                    <tr style="background:#f3f4f6;">
                        <th style="border:1px solid #1f2937;padding:4px;">رقم التذكرة / الحجز</th>
                        <th style="border:1px solid #1f2937;padding:4px;">المبلغ المخصص</th>
                        <th style="border:1px solid #1f2937;padding:4px;">سعر الصرف</th>
                        <th style="border:1px solid #1f2937;padding:4px;">المعادل بعملة التذكرة</th>
                    </tr>
                </thead>
                <tbody>{alloc_rows}</tbody>
            </table>
            {surplus_note}
        </div>
        """

    logo_src = getattr(office_settings, "logo_data", None) or (
        office_settings.logo_image_url if office_settings.logo_image_url and os.path.exists(office_settings.logo_image_url) else None
    )
    if logo_src:
        logo_content = f'<img src="{logo_src}" style="max-width: 100%; max-height: 75px; object-fit: contain;" />'
    else:
        logo_content = f'<div style="font-size: 14px; font-weight: bold; color: #111827; text-align: center;">{office_settings.office_name}</div>'

    is_thermal = (mode == "thermal")
    container_width = "615px" if is_thermal else "280mm"
    container_padding = "10px" if is_thermal else "20px"

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>{title} - {voucher.transaction_id}</title>
    <style>
        {_font_face_css()}
        @page {{
            size: {'615px 420px' if is_thermal else 'A4 landscape'};
            margin: {'4mm' if is_thermal else '10mm'};
        }}
        * {{
            box-sizing: border-box;
            font-family: 'Cairo', 'Noto Sans Arabic', sans-serif;
        }}
        body {{
            margin: 0;
            padding: 0;
            background: #ffffff;
            direction: rtl;
            font-size: 12px;
            color: #111827;
        }}
        .voucher-container {{
            width: {container_width};
            max-width: 100%;
            margin: 0 auto;
            padding: {container_padding};
            background: #ffffff;
        }}
        .header {{
            display: flex;
            flex-direction: row-reverse;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #111827;
            padding-bottom: 8px;
            margin-bottom: 6px;
        }}
        .logo-box {{
            width: 110px;
            height: 75px;
            border: 1.5px solid #374151;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4px;
        }}
        .center-info {{ text-align: center; flex-grow: 1; }}
        .center-title {{ font-size: 22px; font-weight: 900; margin: 0; color: #000000; }}
        .center-ref {{ font-size: 15px; font-weight: bold; margin-top: 4px; color: #374151; direction: ltr; }}
        .office-identity {{ text-align: right; max-width: 260px; }}
        .office-name {{ font-size: 18px; font-weight: 900; color: #000000; margin: 0; }}
        .office-tagline {{ font-size: 12px; font-weight: 700; color: #374151; margin: 2px 0; }}
        .office-address {{ font-size: 10px; color: #4b5563; margin: 1px 0; }}
        .office-phones {{ font-size: 10px; font-weight: bold; color: #1f2937; margin: 1px 0; direction: ltr; text-align: right; }}
        .signatures {{ display: flex; justify-content: space-around; margin-top: 16px; padding-top: 8px; font-size: 11px; font-weight: bold; }}
        .footer {{ text-align: center; font-size: 11px; font-weight: bold; color: #111827; margin-top: 10px; padding-top: 4px; border-top: 1.5px solid #111827; }}
    </style>
</head>
<body onload="window.print()">
    <div class="voucher-container">
        <div class="header">
            <div class="logo-box">{logo_content}</div>
            <div class="center-info">
                <h1 class="center-title">{title}</h1>
                <div class="center-ref">رقم: {voucher.transaction_id}</div>
            </div>
            <div class="office-identity">
                <div class="office-name">{office_settings.office_name}</div>
                <div class="office-tagline">{office_settings.tagline}</div>
                <div class="office-address">{office_settings.address}</div>
                <div class="office-phones">{office_settings.phone_numbers}</div>
            </div>
        </div>
        {table_html}
        {alloc_html}
        <div class="signatures">
            <div>توقيع المستلم: ........................</div>
            <div>أمين الصندوق / المحاسب: {issued_by_name}</div>
            <div>الختم الرسمي</div>
        </div>
        <div class="footer">{office_settings.footer_text}</div>
    </div>
</body>
</html>
"""

