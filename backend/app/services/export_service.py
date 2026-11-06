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


def _format_currency_totals_summary(report: ReportSummary) -> str:
    tbc = getattr(report, "totals_by_currency", None) or {}
    if not tbc:
        return f"الإجمالي المعادل: {float(report.total_amount):,.2f} YER"
    parts = []
    for curr, val in tbc.items():
        if isinstance(val, dict):
            if "sales" in val:
                parts.append(f"{curr}: مبيعات {val['sales']:,.2f} | صافي {val['net']:,.2f}")
            elif "inflow" in val:
                parts.append(f"{curr}: مقبوضات {val['inflow']:,.2f} | مدفوعات {val['outflow']:,.2f} | صافي {val['net']:,.2f}")
        else:
            parts.append(f"{curr}: {float(val):,.2f}")
    joined = "  ||  ".join(parts)
    return f"{joined}  (المعادل التقديري: {float(report.total_amount):,.2f} YER)"


def export_report_to_excel(report: ReportSummary) -> bytes:
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Report"
        ws.sheet_view.rightToLeft = True
    
        # Title header
        ws["A1"] = f"{report.title} - منصة ARP"
        ws["A1"].font = Font(name="Cairo", size=14, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells("A1:G1")
    
        ws["A2"] = f"الفترة / المعيار: {report.period} | {_format_currency_totals_summary(report)}"
        ws["A2"].font = Font(name="Cairo", size=11, italic=True)
        ws.merge_cells("A2:G2")
    
        if not report.rows:
            ws["A4"] = "لا توجد بيانات متاحة لهذا التقرير"
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
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
    
        def safe_float(val):
            if val is None: return 0.0
            try: return float(val)
            except: return val
    
        for item in report.rows:
            row_idx += 1
            for col_idx, header in enumerate(headers, 1):
                val = item.get(header, "")
                if val is None: val = ""
                # Optional: convert numeric values
                if isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('.','',1).isdigit()):
                    val = safe_float(val)
                else:
                    val = str(val)
                
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = Font(name="Cairo", size=10)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
    
        from openpyxl.utils import get_column_letter
        for col_idx in range(1, len(headers) + 1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 20
    
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Excel export error: {str(e)}")
        raise


def export_report_to_pdf(report: ReportSummary) -> tuple[bytes, bool]:
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
            body {{ font-family: 'Cairo', sans-serif; direction: rtl; margin: 0; color: #111827; background: #fff; }}
            .title-box {{ text-align: center; margin-bottom: 15px; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; }}
            h1 {{ margin: 0; color: #1e3a8a; font-size: 20px; }}
            p {{ margin: 4px 0; color: #4b5563; font-size: 12px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; page-break-inside: auto; }}
            tr {{ page-break-inside: avoid; page-break-after: auto; }}
            th {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            
            @media print {{
                body {{ padding: 20px; }}
                th {{ background: #1e3a8a !important; color: white !important; border: 1px solid #ddd; }}
                td {{ border: 1px solid #ddd; }}
                .no-print {{ display: none !important; }}
            }}
        </style>
    </head>
    <body onload="window.print()">
        <div class="title-box">
            <h1>{report.title}</h1>
            <p>الفترة / المعيار: {report.period}</p>
            <p>إجمالي العمليات: {report.total_count} | {_format_currency_totals_summary(report)}</p>
        </div>
        <table>
            <thead><tr>{headers_html}</tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </body>
    </html>
    """
    if WEASYPRINT_AVAILABLE:
        return HTML(string=html_content).write_pdf(), True
    else:
        return html_content.encode("utf-8"), False

def export_ledger_to_excel(data: dict) -> bytes:
    try:
        wb = openpyxl.Workbook()
        wb.remove(wb.active) # Remove default sheet
        
        entity_name = data.get("entity", {}).get("name", "غير محدد")
        period = f"من {data['period']['from_date']} إلى {data['period']['to_date']}" if data['period']['from_date'] else "كل الفترات"
        
        thin_border = Border(
            left=Side(style="thin", color="D1D5DB"),
            right=Side(style="thin", color="D1D5DB"),
            top=Side(style="thin", color="D1D5DB"),
            bottom=Side(style="thin", color="D1D5DB"),
        )
        
        for currency, ledger in data.get("ledgers", {}).items():
            if not ledger["entries"] and ledger["opening_balance"] == 0:
                continue # skip empty currencies
                
            ws = wb.create_sheet(title=currency)
            ws.sheet_view.rightToLeft = True
            
            # Format A1 before merging
            ws["A1"] = f"كشف حساب - {entity_name} ({currency})"
            ws["A1"].font = Font(name="Cairo", size=14, bold=True, color="FFFFFF")
            ws["A1"].fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
            ws.merge_cells("A1:F1")
            
            # Format A2 before merging
            ws["A2"] = f"الفترة: {period}"
            ws["A2"].font = Font(name="Cairo", size=11, italic=True)
            ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
            ws.merge_cells("A2:F2")
            
            def safe_float(val):
                if val is None: return 0.0
                try: return float(val)
                except: return 0.0
            
            # Summary row
            ws.append(["الرصيد الافتتاحي", safe_float(ledger["opening_balance"]), "إجمالي مدين", safe_float(ledger["total_debit"]), "إجمالي دائن", safe_float(ledger["total_credit"])])
            ws.append(["الرصيد الختامي", safe_float(ledger["closing_balance"]), "", "", "", ""])
            ws.append([]) # Empty row
            
            headers = ["التاريخ", "المرجع", "البيان", "مدين", "دائن", "الرصيد"]
            ws.append(headers)
            
            header_row = ws[ws.max_row]
            for cell in header_row:
                cell.font = Font(name="Cairo", size=11, bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                
            for e in ledger["entries"]:
                # Ensure date is string
                date_val = str(e["date"]) if e["date"] is not None else ""
                row = [date_val, e["reference_id"], e["description"], safe_float(e["debit"]), safe_float(e["credit"]), safe_float(e["balance"])]
                ws.append(row)
                for cell in ws[ws.max_row]:
                    if type(cell).__name__ == 'MergedCell': continue
                    cell.font = Font(name="Cairo", size=10)
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = thin_border
                    
            from openpyxl.utils import get_column_letter
            for col_idx in range(1, 7):
                col_letter = get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = 20
                
        if not wb.sheetnames:
            wb.create_sheet(title="No Data")
            
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Excel export error: {str(e)}")
        raise


def export_ledger_to_pdf(data: dict) -> tuple[bytes, bool]:
    entity_name = data.get("entity", {}).get("name", "غير محدد")
    period = f"من {data['period']['from_date']} إلى {data['period']['to_date']}" if data['period']['from_date'] else "كل الفترات"
    
    sections_html = ""
    for currency, ledger in data.get("ledgers", {}).items():
        if not ledger["entries"] and ledger["opening_balance"] == 0:
            continue
            
        rows_html = ""
        for e in ledger["entries"]:
            rows_html += f"<tr><td>{e['date']}</td><td>{e['reference_id']}</td><td>{e['description']}</td><td>{e['debit']}</td><td>{e['credit']}</td><td>{e['balance']}</td></tr>"
            
        sections_html += f"""
        <div style="margin-top: 20px;">
            <h2 style="color: #1e3a8a; font-size: 16px;">كشف حساب ({currency})</h2>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 10px; padding: 10px; background: #f3f4f6;">
                <div>الرصيد الافتتاحي: <strong>{ledger['opening_balance']}</strong></div>
                <div>إجمالي مدين: <strong>{ledger['total_debit']}</strong></div>
                <div>إجمالي دائن: <strong>{ledger['total_credit']}</strong></div>
                <div>الرصيد الختامي: <strong>{ledger['closing_balance']}</strong></div>
            </div>
            <table>
                <thead>
                    <tr><th>التاريخ</th><th>المرجع</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الرصيد</th></tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        """
        
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4; margin: 10mm; }}
            body {{ font-family: 'Cairo', sans-serif; direction: rtl; margin: 0; color: #111827; background: #fff; }}
            .title-box {{ text-align: center; margin-bottom: 15px; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; }}
            h1 {{ margin: 0; color: #1e3a8a; font-size: 20px; }}
            p {{ margin: 4px 0; color: #4b5563; font-size: 12px; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 11px; page-break-inside: auto; }}
            tr {{ page-break-inside: avoid; page-break-after: auto; }}
            th, td {{ padding: 6px; border: 1px solid #ddd; text-align: center; }}
            th {{ background: #1e3a8a; color: white; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            
            @media print {{
                body {{ padding: 20px; }}
                th {{ background: #1e3a8a !important; color: white !important; }}
                .no-print {{ display: none !important; }}
                .summary-box {{ background: #f3f4f6 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            }}
        </style>
    </head>
    <body onload="window.print()">
        <div class="title-box">
            <h1>كشف حساب - {entity_name}</h1>
            <p>الفترة: {period}</p>
        </div>
        {sections_html.replace('background: #f3f4f6;', 'background: #f3f4f6;').replace('<div style="display: flex;', '<div class="summary-box" style="display: flex;') or "<p style='text-align:center;'>لا توجد حركات مالية</p>"}
    </body>
    </html>
    """
    
    if WEASYPRINT_AVAILABLE:
        return HTML(string=html_content).write_pdf(), True
    else:
        return html_content.encode("utf-8"), False
