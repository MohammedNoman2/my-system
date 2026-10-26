#!/usr/bin/env python3
"""
Standalone PDF generation test — meant to run inside the Docker container.
Creates a mock FL-0001 flight booking and generates a real PDF via WeasyPrint
to verify that Arabic text renders correctly (connected glyphs, RTL direction).

Usage (after building the Docker image):
    docker build -t arp-backend ./backend
    docker run --rm -v %cd%/output:/output arp-backend python test_pdf_in_docker.py

The generated PDF will be saved to /output/test_voucher_FL0001.pdf
"""

import os
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Ensure the app package is importable
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.print_service import generate_voucher_html, _font_face_css, FONTS_DIR

# ---------------------------------------------------------------------------
# Verify font files exist
# ---------------------------------------------------------------------------
print(f"[INFO] FONTS_DIR resolved to: {FONTS_DIR}")
for fname in ("Cairo-Regular.ttf", "Cairo-Bold.ttf"):
    fpath = FONTS_DIR / fname
    exists = fpath.exists()
    size = fpath.stat().st_size if exists else 0
    status = f"OK ({size:,} bytes)" if exists else "MISSING!"
    print(f"  {fname}: {status}")

# ---------------------------------------------------------------------------
# Mock objects that mirror SQLAlchemy models without needing a database
# ---------------------------------------------------------------------------

mock_employee = SimpleNamespace(full_name="أحمد الموظف")

mock_flight_details = SimpleNamespace(
    passenger_name="محمد عبدالله الشريف",
    passport_number="A12345678",
    departure_airport="صنعاء الدولي (SAH)",
    arrival_airport="جدة (JED)",
    departure_date=date(2026, 10, 15),
    departure_time=time(14, 30),
    flight_number="YU 301",
    ticket_type="oneway",
    airline_company="طيران اليمنية",
)

mock_booking = SimpleNamespace(
    id=1,
    ticket_number="FL-20260915-0001",
    type=SimpleNamespace(value="flight"),     # BookingType.FLIGHT
    status=SimpleNamespace(value="confirmed"),
    booking_date=datetime(2026, 9, 15, 10, 0),
    selling_price=Decimal("85000.00"),
    paid_amount=Decimal("60000.00"),
    remaining_amount=Decimal("25000.00"),
    currency="YER",
    notes="رحلة ذهاب فقط — حجز عبر المكتب",
    employee=mock_employee,
    flight_details=mock_flight_details,
    transport_details=None,
    visa_details=None,
    passport_details=None,
    parcel_details=None,
)

# Make mock_booking.type compare equal to BookingType.FLIGHT
from app.models.booking import BookingType
mock_booking.type = BookingType.FLIGHT

mock_settings = SimpleNamespace(
    office_name="عالم النقل",
    tagline="للسفريات والنقل البري والتخليص",
    address="صنعاء - الستين الجنوبي - جوار فندق أبراج النيل",
    phone_numbers="778699440 - 771609217 - 771292978 01601217",
    email="info@alamalnaql.com",
    website="www.alamalnaql.com",
    footer_text="عالم النقل للسفريات - ثقتكم رصيدنا الأعلى",
    logo_image_url=None,
)

# ---------------------------------------------------------------------------
# Generate HTML
# ---------------------------------------------------------------------------
print("\n[INFO] Generating voucher HTML …")
html_content = generate_voucher_html(mock_booking, mock_settings, mode="thermal")

# Save intermediate HTML for debugging
html_path = "/output/test_voucher_FL0001.html"
os.makedirs("/output", exist_ok=True)
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"  ✓ HTML saved to {html_path}")

# ---------------------------------------------------------------------------
# Generate PDF via WeasyPrint
# ---------------------------------------------------------------------------
print("\n[INFO] Generating PDF via WeasyPrint …")
try:
    from weasyprint import HTML
    pdf_bytes = HTML(string=html_content).write_pdf()
    pdf_path = "/output/test_voucher_FL0001.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"  ✓ PDF saved to {pdf_path} ({len(pdf_bytes):,} bytes)")
except Exception as e:
    print(f"  ✗ PDF generation FAILED: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Basic sanity checks on the PDF
# ---------------------------------------------------------------------------
print("\n[INFO] Running sanity checks …")
# Check the PDF starts with %PDF
with open(pdf_path, "rb") as f:
    header = f.read(5)
assert header == b"%PDF-", f"PDF header mismatch: {header!r}"
print("  ✓ Valid PDF header (%PDF-)")
print(f"  ✓ PDF file size: {os.path.getsize(pdf_path):,} bytes")

print("\n═══════════════════════════════════════════════════════")
print("  ✅ SUCCESS — PDF generated. Open it to verify:")
print("     • Arabic text is connected (ligatures work)")
print("     • RTL direction is correct")
print("     • Cairo font is applied (look at the header)")
print("═══════════════════════════════════════════════════════\n")
