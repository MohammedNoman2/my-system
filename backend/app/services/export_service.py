import io
import logging
from typing import Any, Dict, List
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from app.schemas.report import ReportSummary

logger = logging.getLogger("arp.export")

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    WEASYPRINT_AVAILABLE = False
    logger.warning(f"WeasyPrint native libraries not loaded ({e}); PDF export fallback active.")


def export_report_to_excel(report: ReportSummary) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.sheet_view.rightToLeft = True

    # Title header
    ws.merge_cells("A1:G1")
    ws["A1"] = f"{report.title} - منصة ARP"
    ws["A1"].font = Font(name="Cairo", size=14, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws["A2"] = f"الفترة / المعيار: {report.period}"
    ws["A2"].font = Font(name="Cairo", size=11, italic=True)

    if not report.rows:
        ws["A4"] = "لا توجد بيانات متاحة لهذا التقرير"
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    headers = list(report.rows[0].keys())
    row_idx = 4
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=row_idx, column=col_idx, value=str(header))
        cell.font = Font(name="Cairo", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    thin_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )

    for item in report.rows:
        row_idx += 1
        for col_idx, header in enumerate(headers, 1):
            val = item.get(header, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=str(val) if val is not None else "")
            cell.font = Font(name="Cairo", size=10)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

    # Adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def export_report_to_pdf(report: ReportSummary) -> bytes:
    headers_html = ""
    rows_html = ""

    if report.rows:
        headers = list(report.rows[0].keys())
        headers_html = "".join([f"<th style='padding: 8px; border: 1px solid #ddd; background: #1e3a8a; color: white;'>{h}</th>" for h in headers])
        for r in report.rows:
            cells = "".join([f"<td style='padding: 6px; border: 1px solid #ddd; text-align: center;'>{r.get(h, '')}</td>" for h in headers])
            rows_html += f"<tr>{cells}</tr>"
    else:
        rows_html = "<tr><td colspan='7' style='text-align: center; padding: 15px;'>لا توجد بيانات متاحة</td></tr>"

    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4 landscape; margin: 10mm; }}
            body {{ font-family: 'Cairo', sans-serif; direction: rtl; margin: 0; color: #111827; }}
            .title-box {{ text-align: center; margin-bottom: 15px; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; }}
            h1 {{ margin: 0; color: #1e3a8a; font-size: 20px; }}
            p {{ margin: 4px 0; color: #4b5563; font-size: 12px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="title-box">
            <h1>{report.title}</h1>
            <p>الفترة / المعيار: {report.period}</p>
            <p>إجمالي العمليات: {report.total_count} | الإجمالي المالي: {report.total_amount}</p>
        </div>
        <table>
            <thead><tr>{headers_html}</tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </body>
    </html>
    """
    if WEASYPRINT_AVAILABLE:
        return HTML(string=html_content).write_pdf()
    else:
        return html_content.encode("utf-8")
