from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.models.booking import BookingType


class ReportFilter(BaseModel):
    report_type: str  # bookings_detailed, revenue, expenses, profit_loss, debts, employee_performance, cash_flow
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    service_type: Optional[BookingType] = None
    employee_id: Optional[int] = None
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    expense_type: Optional[str] = None
    group_by: Optional[str] = "day"  # day, week, month, year


class ReportSummary(BaseModel):
    title: str
    report_type: str
    period: str
    total_count: int = 0
    total_amount: Decimal = Decimal("0.00")
    additional_totals: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
