from datetime import date, time
from typing import Optional
from sqlalchemy import Date, ForeignKey, Integer, String, Time
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
    passenger_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    id_number: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_place: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    id_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    booking = relationship("Booking", back_populates="transport_details")
