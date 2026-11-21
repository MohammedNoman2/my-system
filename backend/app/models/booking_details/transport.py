from datetime import date, datetime, time, timezone
from typing import Optional
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class TransportBookingDetail(Base):
    __tablename__ = "transport_booking_details"

    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    transport_company: Mapped[str] = mapped_column(String(100), nullable=False)
    departure_station: Mapped[str] = mapped_column(String(100), nullable=False)
    arrival_station: Mapped[str] = mapped_column(String(100), nullable=False)
    travel_date: Mapped[date] = mapped_column(Date, nullable=False)
    travel_time: Mapped[time] = mapped_column(Time, nullable=False)
    # NOTE: seat_number is deliberately removed per specification!
    passenger_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    passenger_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    id_type: Mapped[str] = mapped_column(String(30), default="national_id", nullable=False)
    id_number: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_place: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    id_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    booking = relationship("Booking", back_populates="transport_details")


class TransportInfant(Base):
    __tablename__ = "transport_infants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    id_type: Mapped[str] = mapped_column(String(30), default="birth_certificate", nullable=False)
    id_number: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    booking = relationship("Booking", back_populates="transport_infants")
