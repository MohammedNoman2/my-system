from datetime import date
from typing import Optional
from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class VisaBookingDetail(Base):
    __tablename__ = "visa_booking_details"

    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    visa_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # NOTE: country, expected_issue_date, duration are deliberately removed per specification!
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    applicant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    applicant_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    passport_number: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_place: Mapped[str] = mapped_column(String(100), nullable=False)
    passport_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    booking = relationship("Booking", back_populates="visa_details")
