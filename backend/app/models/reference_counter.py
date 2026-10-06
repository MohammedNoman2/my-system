from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ReferenceCounter(Base):
    __tablename__ = "reference_counters"

    prefix: Mapped[str] = mapped_column(String(10), primary_key=True)
    current_val: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str] = mapped_column(String(100), nullable=False)
