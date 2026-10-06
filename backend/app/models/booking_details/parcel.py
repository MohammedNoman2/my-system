from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ParcelBookingDetail(Base):
    __tablename__ = "parcel_booking_details"

    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    sender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(100), nullable=False)
    receiver_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_destination: Mapped[str] = mapped_column(String(100), nullable=False)
    # NOTE: parcel_type is free text per specification
    parcel_type: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # NOTE: quantity is deliberately removed per specification!
    content_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    shipping_date: Mapped[date] = mapped_column(Date, nullable=False)

    booking = relationship("Booking", back_populates="parcel_details")
