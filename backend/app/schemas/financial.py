from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field
from app.core.config import office_today
from app.models.financial import EntityType, PaymentMethod, TransactionType


class PaymentVoucherCreate(BaseModel):
    entity_type: EntityType = EntityType.SUPPLIER  # customer or supplier
    entity_id: int
    amount: Decimal = Field(..., gt=0)
    currency: str = "YER"
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None
    booking_id: Optional[int] = None
    notes: Optional[str] = None
    transaction_date: date = Field(default_factory=office_today)


class ReceiptVoucherCreate(BaseModel):
    entity_type: EntityType = EntityType.CUSTOMER  # customer or supplier
    entity_id: int
    amount: Decimal = Field(..., gt=0)
    currency: str = "YER"
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None
    booking_id: Optional[int] = None
    notes: Optional[str] = None
    transaction_date: date = Field(default_factory=office_today)


class ExpenseCreate(BaseModel):
    expense_type: str
    amount: Decimal = Field(..., gt=0)
    currency: str = "YER"
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    transaction_date: date = Field(default_factory=office_today)


class FinancialTransactionResponse(BaseModel):
    id: int
    transaction_id: str
    type: TransactionType
    entity_type: EntityType
    entity_id: Optional[int] = None
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    reference_number: Optional[str] = None
    expense_type: Optional[str] = None
    notes: Optional[str] = None
    transaction_date: date
    booking_id: Optional[int] = None
    is_reconciled: bool
    reconciled_at: Optional[datetime] = None
    is_void: bool = False
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None
    reversal_je_number: Optional[str] = None
    shift_id: Optional[int] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    entity_name: Optional[str] = None

    class Config:
        from_attributes = True


class LedgerEntryResponse(BaseModel):
    id: int
    date: date
    description: str
    reference_id: str
    debit: Decimal   # مدين
    credit: Decimal  # دائن
    balance: Decimal # الرصيد التراكمي
    notes: Optional[str] = None
