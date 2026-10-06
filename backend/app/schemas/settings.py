from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr


class SettingsBase(BaseModel):
    office_name: str
    tagline: str  # Mandatory field
    address: str
    phone_numbers: str
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    logo_image_url: Optional[str] = None
    logo_data: Optional[str] = None
    default_currency: str = "YER"
    footer_text: str


class SettingsUpdate(BaseModel):
    office_name: Optional[str] = None
    tagline: Optional[str] = None
    address: Optional[str] = None
    phone_numbers: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    logo_image_url: Optional[str] = None
    logo_data: Optional[str] = None
    default_currency: Optional[str] = None
    footer_text: Optional[str] = None


class PublicSettingsResponse(BaseModel):
    office_name: str
    tagline: str
    address: str
    phone_numbers: str
    email: Optional[str] = None
    website: Optional[str] = None
    logo_image_url: Optional[str] = None
    logo_data: Optional[str] = None
    default_currency: str = "YER"
    footer_text: str

    class Config:
        from_attributes = True


class SettingsResponse(SettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExchangeRateBase(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal


class ExchangeRateCreate(ExchangeRateBase):
    pass


class ExchangeRateUpdate(BaseModel):
    rate: Decimal


class ExchangeRateResponse(ExchangeRateBase):
    id: int
    updated_at: datetime
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True
