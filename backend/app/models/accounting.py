from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AccountType(str, PyEnum):
    ASSET = "ASSET"          # أصول (الصناديق، المدينون/العملاء)
    LIABILITY = "LIABILITY"  # التزامات/خصوم (الدائنون/الموردون)
    EQUITY = "EQUITY"        # حقوق ملكية (الأرباح المبقاة، رأس المال الافتتاحي)
    REVENUE = "REVENUE"      # إيرادات (مبيعات الحجوزات، رسوم الإلغاء)
    EXPENSE = "EXPENSE"      # مصروفات (تكلفة المبيعات، المصروفات التشغيلية، فروقات التقريب)


class AccountCurrency(str, PyEnum):
    YER = "YER"
    SAR = "SAR"
    USD = "USD"


class EntityAccountType(str, PyEnum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    NONE = "NONE"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Unique constraint strictly on code alone as instructed
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    currency: Mapped[AccountCurrency] = mapped_column(Enum(AccountCurrency), nullable=False)
    entity_type: Mapped[EntityAccountType] = mapped_column(
        Enum(EntityAccountType), default=EntityAccountType.NONE, nullable=False
    )
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    lines: Mapped[List["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="account"
    )

    def __repr__(self) -> str:
        return f"<Account code={self.code} name={self.name} currency={self.currency}>"


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entry_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    reference_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # BOOKING, RECEIPT, PAYMENT, EXPENSE, OPENING, CANCEL
    reference_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)    # e.g., FL-0004, RC-0009
    currency: Mapped[AccountCurrency] = mapped_column(Enum(AccountCurrency), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("1.000000"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_posted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    lines: Mapped[List["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<JournalEntry {self.entry_number} ({self.reference_type}:{self.reference_id})>"


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    journal_entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    debit_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    credit_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    journal_entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["Account"] = relationship("Account", back_populates="lines")

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)",
            name="chk_line_debit_credit",
        ),
        Index("ix_account_lines", "account_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Line acc={self.account_id} debit={self.debit} credit={self.credit}>"
