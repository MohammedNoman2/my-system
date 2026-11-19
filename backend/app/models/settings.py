from datetime import date
from typing import Optional
from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import TimestampMixin


class Settings(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    office_name: Mapped[str] = mapped_column(String(255), default="عالم النقل", nullable=False)
    tagline: Mapped[str] = mapped_column(String(255), default="للسفريات والنقل البري والتخليص", nullable=False)
    address: Mapped[str] = mapped_column(String(255), default="صنعاء - الستين الجنوبي - جوار فندق أبراج النيل", nullable=False)
    phone_numbers: Mapped[str] = mapped_column(Text, default="778699440 - 771609217 - 771292978 01601217", nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), default="info@alamalnaql.com", nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(100), default="www.alamalnaql.com", nullable=True)
    logo_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logo_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_currency: Mapped[str] = mapped_column(String(10), default="YER", nullable=False)
    footer_text: Mapped[str] = mapped_column(
        Text,
        default="عالم النقل للسفريات - ثقتكم رصيدنا الأعلى",
        nullable=False
    )
    accounting_lock_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
