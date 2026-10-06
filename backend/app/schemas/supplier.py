from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr


class SupplierBase(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone_number: str
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(SupplierBase):
    id: int
    balance: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
