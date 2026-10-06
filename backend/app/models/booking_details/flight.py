from datetime import date, time
import enum
from typing import Optional
from decimal import Decimal
from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class FlightTicketType(str, enum.Enum):
    ONEWAY = "oneway"
    ROUNDTRIP = "roundtrip"


class FlightBookingDetail(Base):
    __tablename__ = "flight_booking_details"

    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    airline_company: Mapped[str] = mapped_column(String(100), nullable=False)
    flight_number: Mapped[str] = mapped_column(String(20), nullable=False)
    departure_airport: Mapped[str] = mapped_column(String(100), nullable=False)
    arrival_airport: Mapped[str] = mapped_column(String(100), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    departure_time: Mapped[time] = mapped_column(Time, nullable=False)
    return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    return_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    ticket_type: Mapped[FlightTicketType] = mapped_column(
        Enum(FlightTicketType, values_callable=lambda obj: [e.value for e in obj]),
        default=FlightTicketType.ONEWAY,
        nullable=False,
    )
    allowed_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    passenger_name: Mapped[str] = mapped_column(String(100), nullable=False)
    passenger_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    passport_number: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_place: Mapped[str] = mapped_column(String(100), nullable=False)
    passport_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    booking = relationship("Booking", back_populates="flight_details")
