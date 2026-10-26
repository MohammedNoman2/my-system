from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_validator
from app.models.booking import BookingStatus, BookingType
from app.models.booking_details.flight import FlightTicketType
from app.models.booking_details.passport import PassportPriority, PassportType


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
    passenger_name: str
    passenger_phone: str
    passport_number: str
    birth_date: date
    birth_place: str
    passport_image_url: Optional[str] = None


class TransportDetailCreate(BaseModel):
    transport_company: str
    departure_station: str
    arrival_station: str
    travel_date: date
    travel_time: time
    # NO seat_number per specification
    passenger_name: str
    passenger_phone: str
    id_number: str
    birth_date: date
    birth_place: str
    id_image_url: Optional[str] = None


class VisaDetailCreate(BaseModel):
    visa_type: str
    # NO country, expected_issue_date, duration per specification
    application_date: date
    applicant_name: str
    applicant_phone: str
    passport_number: str
    birth_date: date
    birth_place: str
    passport_image_url: Optional[str] = None


class PassportDetailCreate(BaseModel):
    passport_type: PassportType = PassportType.NEW
    priority: PassportPriority = PassportPriority.NORMAL
    application_date: date
    expected_delivery_date: Optional[date] = None
    applicant_name: str
    applicant_phone: str
    id_number: str
    birth_date: date
    birth_place: str
    id_image_url: Optional[str] = None


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
    passenger_phone: str
    passport_number: str
    birth_date: date
    birth_place: str
    passport_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class TransportDetailResponse(BaseModel):
    transport_company: str
    departure_station: str
    arrival_station: str
    travel_date: date
    travel_time: time
    passenger_name: str
    passenger_phone: str
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
    application_date: date
    expected_delivery_date: Optional[date] = None
    applicant_name: str
    applicant_phone: str
    id_number: str
    birth_date: date
    birth_place: str
    id_image_url: Optional[str] = None

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
