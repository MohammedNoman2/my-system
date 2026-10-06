from datetime import date
from typing import Optional
from pydantic import BaseModel


class OcrPassportResponse(BaseModel):
    passenger_name: Optional[str] = None
    passport_number: Optional[str] = None
    birth_date: Optional[date] = None
    birth_place: Optional[str] = None
    nationality: Optional[str] = None
    raw_text: Optional[str] = None
    mocked: bool = False


class OcrIdResponse(BaseModel):
    passenger_name: Optional[str] = None
    id_number: Optional[str] = None
    birth_date: Optional[date] = None
    birth_place: Optional[str] = None
    raw_text: Optional[str] = None
    mocked: bool = False
