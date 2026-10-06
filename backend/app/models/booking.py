from datetime import datetime
from decimal import Decimal
import enum
from typing import Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class BookingType(str, enum.Enum):
    FLIGHT = "flight"
    TRANSPORT = "transport"
    VISA = "visa"
    PASSPORT = "passport"
    PARCEL = "parcel"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    type: Mapped[BookingType] = mapped_column(
        Enum(BookingType, values_callable=lambda obj: [e.value for e in obj]),
        index=True,
        nullable=False,
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True, nullable=False
    )
    booking_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="YER", nullable=False)

    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=BookingStatus.PENDING,
        nullable=False,
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="bookings")
    employee = relationship("User", back_populates="bookings", foreign_keys=[employee_id])
    supplier = relationship("Supplier", back_populates="bookings")

    flight_details = relationship("FlightBookingDetail", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    transport_details = relationship("TransportBookingDetail", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    visa_details = relationship("VisaBookingDetail", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    passport_details = relationship("PassportBookingDetail", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    parcel_details = relationship("ParcelBookingDetail", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    financial_transactions = relationship("FinancialTransaction", back_populates="booking")
    voucher_allocations = relationship("VoucherAllocation", back_populates="booking")
