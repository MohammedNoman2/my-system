from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, computed_field, model_validator
from app.core.config import office_today
from app.models.booking import BookingStatus, BookingType
from app.models.booking_details.flight import FlightTicketType
from app.models.booking_details.passport import PassportPriority, PassportType
from app.models.financial import PaymentMethod


import re

DUMMY_DOC_NUMBERS = {
    "123456", "1234567", "12345678", "123456789", "1234567890", "12345678901",
    "01234567", "012345678", "0123456789", "87654321", "987654321",
}


def validate_clean_phone(val: str, field_label: str = "رقم الهاتف") -> str:
    digits = re.sub(r"\D", "", (val or "").strip())
    if digits.startswith("00967") and len(digits) == 14:
        digits = digits[5:]
    elif digits.startswith("967") and len(digits) == 12:
        digits = digits[3:]
    if len(digits) < 9 or len(digits) > 15:
        raise ValueError(f"{field_label} غير صالح ({val})؛ يجب أن يتكون من 9 أرقام على الأقل")
    return digits


def validate_clean_doc_number(val: str, field_label: str = "رقم الوثيقة") -> str:
    cleaned = re.sub(r"\s+", "", (val or "").strip()).upper()
    if len(cleaned) < 6:
        raise ValueError(f"{field_label} قصير جداً")
    if cleaned in DUMMY_DOC_NUMBERS or len(set(cleaned)) == 1:
        raise ValueError(f"{field_label} المدخل ({val}) يبدو رقماً تجريبياً غير حقيقي؛ يرجى إدخال الرقم الصحيح")
    return cleaned


VALID_FLIGHT_CATEGORIES = {"adult", "child", "infant"}


def compute_flight_passenger_category(birth_date: date, departure_date: date) -> str:
    """حساب فئة مسافر الطيران تلقائياً من تاريخ الميلاد مقارنةً بتاريخ السفر."""
    age_years = (
        departure_date.year
        - birth_date.year
        - ((departure_date.month, departure_date.day) < (birth_date.month, birth_date.day))
    )
    if age_years < 2:
        return "infant"
    if age_years < 12:
        return "child"
    return "adult"


def _resolve_3part_name(
    first_middle_name: Optional[str],
    last_name: Optional[str],
    full_name: Optional[str],
    entity_label: str = "المسافر",
) -> Tuple[Optional[str], Optional[str], str]:
    fm = re.sub(r"\s+", " ", (first_middle_name or "").strip())
    ln = re.sub(r"\s+", " ", (last_name or "").strip())
    if fm or ln:
        if not fm or len(fm.split(" ")) != 3:
            raise ValueError(f"الاسم الثلاثي لـ{entity_label} يجب أن يتكون من 3 أسماء بالضبط")
        if not ln:
            raise ValueError(f"لقب {entity_label} مطلوب")
        return fm, ln, f"{fm} {ln}".strip()
    pn = re.sub(r"\s+", " ", (full_name or "").strip())
    if not pn:
        raise ValueError(f"اسم {entity_label} مطلوب")
    return None, None, pn


# Detail Creation Schemas
class FlightDetailCreate(BaseModel):
    airline_company: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_date: date
    departure_time: time
    return_date: Optional[date] = None
    return_time: Optional[time] = None
    ticket_type: FlightTicketType = FlightTicketType.ONEWAY
    allowed_weight: Optional[Decimal] = None
    passenger_name: Optional[str] = None
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    passenger_category: Optional[str] = None
    passenger_phone: str
    passport_number: str
    birth_date: date
    birth_place: str
    passport_image_url: Optional[str] = None

    @model_validator(mode="after")
    def _clean_fields(self) -> "FlightDetailCreate":
        fm, ln, full = _resolve_3part_name(
            self.first_middle_name, self.last_name, self.passenger_name, "المسافر"
        )
        self.first_middle_name = fm
        self.last_name = ln
        self.passenger_name = full
        self.passenger_phone = validate_clean_phone(self.passenger_phone, "هاتف المسافر")
        self.passport_number = validate_clean_doc_number(self.passport_number, "رقم الجواز")
        self.passenger_category = compute_flight_passenger_category(
            self.birth_date, self.departure_date
        )
        return self


VALID_TRANSPORT_ID_TYPES = {"passport", "national_id", "birth_certificate"}


class TransportInfantCreate(BaseModel):
    full_name: str
    id_type: str = "birth_certificate"
    id_number: Optional[str] = ""
    birth_date: date

    @model_validator(mode="after")
    def _validate_infant(self) -> "TransportInfantCreate":
        self.full_name = re.sub(r"\s+", " ", (self.full_name or "").strip())
        if not self.full_name:
            raise ValueError("اسم الرضيع مطلوب")
        if self.id_type not in VALID_TRANSPORT_ID_TYPES:
            raise ValueError("نوع هوية الرضيع غير صالح")
        doc = (self.id_number or "").strip()
        if self.id_type == "passport" and not re.fullmatch(r"[A-Za-z0-9]{8}", doc):
            raise ValueError("رقم جواز الرضيع يجب أن يتكون من 8 خانات")
        elif self.id_type == "national_id" and not re.fullmatch(r"\d{11}", doc):
            raise ValueError("رقم البطاقة الشخصية للرضيع يجب أن يتكون من 11 رقماً")
        self.id_number = doc
        return self


class TransportDetailCreate(BaseModel):
    transport_company: str
    departure_station: str
    arrival_station: str
    travel_date: date
    travel_time: time
    # NO seat_number per specification
    passenger_name: Optional[str] = None
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    passenger_phone: str
    id_type: Optional[str] = None
    id_number: Optional[str] = ""
    birth_date: date
    birth_place: str
    id_image_url: Optional[str] = None
    infants: List[TransportInfantCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _clean_fields(self) -> "TransportDetailCreate":
        fm = re.sub(r"\s+", " ", (self.first_middle_name or "").strip())
        ln = re.sub(r"\s+", " ", (self.last_name or "").strip())
        if fm or ln:
            if not fm or len(fm.split(" ")) != 3:
                raise ValueError("الاسم الثلاثي للمسافر يجب أن يتكون من 3 أسماء بالضبط")
            if not ln:
                raise ValueError("لقب المسافر مطلوب")
            self.first_middle_name = fm
            self.last_name = ln
            self.passenger_name = f"{fm} {ln}".strip()
        else:
            pn = re.sub(r"\s+", " ", (self.passenger_name or "").strip())
            if not pn:
                raise ValueError("اسم المسافر مطلوب")
            self.passenger_name = pn

        self.passenger_phone = validate_clean_phone(self.passenger_phone, "هاتف الراكب")

        doc = (self.id_number or "").strip()
        if self.id_type is not None:
            if self.id_type not in VALID_TRANSPORT_ID_TYPES:
                raise ValueError("نوع الهوية غير صالح")
            if self.id_type == "passport":
                if not re.fullmatch(r"[A-Za-z0-9]{8}", doc):
                    raise ValueError("رقم جواز السفر يجب أن يتكون من 8 خانات بالضبط")
            elif self.id_type == "national_id":
                if not re.fullmatch(r"\d{11}", doc):
                    raise ValueError("رقم البطاقة الشخصية يجب أن يتكون من 11 رقماً بالضبط")
            elif self.id_type == "birth_certificate":
                if doc:
                    doc = validate_clean_doc_number(doc, "رقم شهادة الميلاد")
            self.id_number = doc
        else:
            self.id_number = validate_clean_doc_number(doc, "رقم الهوية")
        return self


class TransportBatchCreate(BaseModel):
    """إنشاء عدة مقاعد نقل بري في عملية واحدة (تذكرة مستقلة لكل راكب + سند قبض واحد موزع)."""
    customer_id: Optional[int] = None
    cost_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    selling_price: Decimal = Field(gt=0)
    paid_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = "YER"
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    notes: Optional[str] = None
    use_credit_balance: bool = True
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None
    passengers: List[TransportDetailCreate] = Field(min_length=1)


class VisaDetailCreate(BaseModel):
    visa_type: str
    # NO country, expected_issue_date, duration per specification
    application_date: date
    applicant_name: Optional[str] = None
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    applicant_phone: str
    passport_number: str
    birth_date: date
    birth_place: str
    passport_image_url: Optional[str] = None

    @model_validator(mode="after")
    def _clean_fields(self) -> "VisaDetailCreate":
        fm, ln, full = _resolve_3part_name(
            self.first_middle_name, self.last_name, self.applicant_name, "المتقدم"
        )
        self.first_middle_name = fm
        self.last_name = ln
        self.applicant_name = full
        self.applicant_phone = validate_clean_phone(self.applicant_phone, "هاتف المتقدم")
        self.passport_number = validate_clean_doc_number(self.passport_number, "رقم الجواز")
        return self


def compute_passport_24_48_status(application_date: date, ref_date: Optional[date] = None) -> tuple[str, str]:
    today = ref_date or office_today()
    days = (today - application_date).days
    if days <= 0:
        return "under_24h", "قيد المراجعة (أقل من 24 ساعة)"
    if days == 1:
        return "within_48h", "تحت الإجراء (24–48 ساعة)"
    return "over_48h", "جاهز للمتابعة / التسليم (+48 ساعة)"


class PassportDetailCreate(BaseModel):
    passport_type: PassportType = PassportType.NEW
    priority: PassportPriority = PassportPriority.NORMAL
    issuing_office: Optional[str] = None
    application_date: date
    expected_delivery_date: Optional[date] = None
    applicant_name: Optional[str] = None
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    applicant_phone: str
    id_number: str
    birth_date: date
    birth_place: str
    id_image_url: Optional[str] = None

    @model_validator(mode="after")
    def _clean_fields(self) -> "PassportDetailCreate":
        fm, ln, full = _resolve_3part_name(
            self.first_middle_name, self.last_name, self.applicant_name, "المتقدم"
        )
        self.first_middle_name = fm
        self.last_name = ln
        self.applicant_name = full
        self.applicant_phone = validate_clean_phone(self.applicant_phone, "هاتف المتقدم")
        self.id_number = validate_clean_doc_number(self.id_number, "رقم الهوية")
        return self


class BookingBatchItem(BaseModel):
    flight_details: Optional[FlightDetailCreate] = None
    transport_details: Optional[TransportDetailCreate] = None
    visa_details: Optional[VisaDetailCreate] = None
    passport_details: Optional[PassportDetailCreate] = None


class BookingBatchCreate(BaseModel):
    """إنشاء عدة حجوزات في القطاعات الأربعة (طيران، نقل بري، تأشيرات، جوازات) بسند قبض موحد."""
    type: BookingType
    customer_id: Optional[int] = None
    cost_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    selling_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    category_prices: Optional[Dict[str, Decimal]] = None
    category_costs: Optional[Dict[str, Decimal]] = None
    paid_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = "YER"
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    notes: Optional[str] = None
    use_credit_balance: bool = True
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None
    items: List[BookingBatchItem] = Field(min_length=1)


class ParcelDetailCreate(BaseModel):
    sender_name: str
    sender_phone: str
    receiver_name: str
    receiver_phone: str
    delivery_destination: str
    parcel_type: str  # Free text per specification
    weight: Decimal
    # NO quantity per specification
    content_description: Optional[str] = None
    shipping_date: date

    @model_validator(mode="after")
    def _clean_fields(self) -> "ParcelDetailCreate":
        self.sender_name = re.sub(r"\s+", " ", self.sender_name.strip())
        self.receiver_name = re.sub(r"\s+", " ", self.receiver_name.strip())
        self.sender_phone = validate_clean_phone(self.sender_phone, "هاتف المرسل")
        self.receiver_phone = validate_clean_phone(self.receiver_phone, "هاتف المستلم")
        return self



# Booking Creation
class BookingCreate(BaseModel):
    type: BookingType
    customer_id: Optional[int] = None
    # For employee, cost_price is optional or omitted; admin/accountant can provide it
    cost_price: Optional[Decimal] = Decimal("0.00")
    selling_price: Decimal = Field(..., gt=0)
    paid_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = "YER"
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    notes: Optional[str] = None
    use_credit_balance: bool = True
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None

    # Exactly one of the detail models will be populated
    flight_details: Optional[FlightDetailCreate] = None
    transport_details: Optional[TransportDetailCreate] = None
    visa_details: Optional[VisaDetailCreate] = None
    passport_details: Optional[PassportDetailCreate] = None
    parcel_details: Optional[ParcelDetailCreate] = None


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    refund_amount: Decimal = Decimal("0.00")
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="after")
    def ensure_reason(self) -> "BookingCancelRequest":
        resolved = (self.reason or self.cancellation_reason or "").strip()
        if not resolved:
            raise ValueError("سبب الإلغاء مطلوب")
        self.reason = resolved
        return self


class BookingPostponeRequest(BaseModel):
    new_departure_date: Optional[date] = None
    new_travel_date: Optional[date] = None
    new_departure_time: Optional[time] = None
    new_travel_time: Optional[time] = None
    reason: Optional[str] = None


class BookingRerouteRequest(BaseModel):
    new_destination: str
    new_departure_station: Optional[str] = None
    price_difference: Decimal = Decimal("0.00")
    reason: Optional[str] = None


# Detail Response Schemas
class FlightDetailResponse(BaseModel):
    airline_company: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_date: date
    departure_time: time
    return_date: Optional[date] = None
    return_time: Optional[time] = None
    ticket_type: FlightTicketType
    allowed_weight: Optional[Decimal] = None
    passenger_name: str
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    passenger_category: Optional[str] = "adult"
    passenger_phone: str
    passport_number: str
    birth_date: date
    birth_place: str
    passport_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class TransportInfantResponse(BaseModel):
    id: int
    full_name: str
    id_type: str
    id_number: str
    birth_date: date

    class Config:
        from_attributes = True


class TransportDetailResponse(BaseModel):
    transport_company: str
    departure_station: str
    arrival_station: str
    travel_date: date
    travel_time: time
    passenger_name: str
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    passenger_phone: str
    id_type: Optional[str] = "national_id"
    id_number: str
    birth_date: date
    birth_place: str
    id_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class VisaDetailResponse(BaseModel):
    visa_type: str
    application_date: date
    applicant_name: str
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    applicant_phone: str
    passport_number: str
    birth_date: date
    birth_place: str
    passport_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class PassportDetailResponse(BaseModel):
    passport_type: PassportType
    priority: PassportPriority
    issuing_office: Optional[str] = None
    application_date: date
    expected_delivery_date: Optional[date] = None
    applicant_name: str
    first_middle_name: Optional[str] = None
    last_name: Optional[str] = None
    applicant_phone: str
    id_number: str
    birth_date: date
    birth_place: str
    id_image_url: Optional[str] = None

    @computed_field
    @property
    def processing_status_code(self) -> str:
        return compute_passport_24_48_status(self.application_date)[0]

    @computed_field
    @property
    def processing_status_label(self) -> str:
        return compute_passport_24_48_status(self.application_date)[1]

    class Config:
        from_attributes = True


class ParcelDetailResponse(BaseModel):
    sender_name: str
    sender_phone: str
    receiver_name: str
    receiver_phone: str
    delivery_destination: str
    parcel_type: str
    weight: Decimal
    content_description: Optional[str] = None
    shipping_date: date

    class Config:
        from_attributes = True


# Customer summary for booking response
class CustomerSummary(BaseModel):
    id: int
    name: str
    phone_number: str

    class Config:
        from_attributes = True


# User summary for booking response
class UserSummary(BaseModel):
    id: int
    full_name: str
    username: str

    class Config:
        from_attributes = True


# Supplier summary for booking response
class SupplierSummary(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# -------------------------------------------------------------
# STRICT ROLE-BASED SCHEMAS:
# BookingEmployeeResponse DELIBERATELY EXCLUDES cost_price!
# -------------------------------------------------------------
class BookingEmployeeResponse(BaseModel):
    id: int
    booking_id: str
    ticket_number: str
    type: BookingType
    customer_id: int
    employee_id: int
    booking_date: datetime
    # NOTE: cost_price is completely excluded here!
    selling_price: Decimal
    paid_amount: Decimal
    credit_applied: Decimal = Decimal("0.00")
    remaining_amount: Decimal
    currency: str
    supplier_id: Optional[int] = None
    notes: Optional[str] = None
    status: BookingStatus
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[int] = None
    cancellation_reason: Optional[str] = None
    refund_amount: Decimal
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None

    customer: Optional[CustomerSummary] = None
    employee: Optional[UserSummary] = None
    supplier: Optional[SupplierSummary] = None

    flight_details: Optional[FlightDetailResponse] = None
    transport_details: Optional[TransportDetailResponse] = None
    visa_details: Optional[VisaDetailResponse] = None
    passport_details: Optional[PassportDetailResponse] = None
    parcel_details: Optional[ParcelDetailResponse] = None

    class Config:
        from_attributes = True


class BookingAdminResponse(BaseModel):
    id: int
    booking_id: str
    ticket_number: str
    type: BookingType
    customer_id: int
    employee_id: int
    booking_date: datetime
    cost_price: Decimal  # Present ONLY for Admin and Accountant
    selling_price: Decimal
    paid_amount: Decimal
    credit_applied: Decimal = Decimal("0.00")
    remaining_amount: Decimal
    currency: str
    supplier_id: Optional[int] = None
    notes: Optional[str] = None
    status: BookingStatus
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[int] = None
    cancellation_reason: Optional[str] = None
    refund_amount: Decimal
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None

    customer: Optional[CustomerSummary] = None
    employee: Optional[UserSummary] = None
    supplier: Optional[SupplierSummary] = None

    flight_details: Optional[FlightDetailResponse] = None
    transport_details: Optional[TransportDetailResponse] = None
    visa_details: Optional[VisaDetailResponse] = None
    passport_details: Optional[PassportDetailResponse] = None
    parcel_details: Optional[ParcelDetailResponse] = None

    class Config:
        from_attributes = True


class TicketSearchItem(BaseModel):
    id: int
    booking_id: str
    ticket_number: str
    passenger_name: str
    passenger_phone: str
    identity_number: Optional[str] = None
    type: BookingType
    company_name: str
    booking_date: datetime
    route: str
    travel_date: Optional[date] = None
    travel_time: Optional[time] = None
    employee_id: int
    employee_name: str
    status: BookingStatus
    selling_price: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    currency: str
    customer_id: int
    customer_balance: Optional[Decimal] = None
    notes: Optional[str] = None


class TicketSearchResponse(BaseModel):
    items: List[TicketSearchItem]
    total: int
    page: int
    limit: int
