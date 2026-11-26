from datetime import date
import enum
from typing import Optional
from sqlalchemy import Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class PassportType(str, enum.Enum):
    NEW = "new"
    RENEWAL = "renewal"
    LOST = "lost"
    DAMAGED = "damaged"


class PassportPriority(str, enum.Enum):
    NORMAL = "normal"
    URGENT = "urgent"


class PassportBookingDetail(Base):
    __tablename__ = "passport_booking_details"

    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    passport_type: Mapped[PassportType] = mapped_column(
        Enum(PassportType, values_callable=lambda obj: [e.value for e in obj]),
        default=PassportType.NEW,
        nullable=False,
    )
    priority: Mapped[PassportPriority] = mapped_column(
        Enum(PassportPriority, values_callable=lambda obj: [e.value for e in obj]),
        default=PassportPriority.NORMAL,
        nullable=False,
    )
    issuing_office: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    applicant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    applicant_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    id_number: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_place: Mapped[str] = mapped_column(String(100), nullable=False)
    id_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    booking = relationship("Booking", back_populates="passport_details")
