from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr


class CustomerBase(BaseModel):
    name: str
    phone_number: str
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    passport_number: Optional[str] = None
    id_number: Optional[str] = None
    nationality: Optional[str] = None
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    passport_number: Optional[str] = None
    id_number: Optional[str] = None
    nationality: Optional[str] = None
    notes: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: int
    balance: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerSearchItem(BaseModel):
    id: int
    name: str
    phone_number: str
    passport_number: Optional[str] = None
    id_number: Optional[str] = None
    nationality: Optional[str] = None
    balance: Decimal

    class Config:
        from_attributes = True
