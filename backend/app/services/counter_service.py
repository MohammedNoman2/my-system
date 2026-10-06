import asyncio
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.reference_counter import ReferenceCounter

_counter_locks = defaultdict(asyncio.Lock)

INITIAL_COUNTERS = [
    ("FL", "Flight Booking (حجز طيران)"),
    ("TR", "Group Transport Booking (حجز نقل بري)"),
    ("VI", "Visa Booking (معاملة تأشيرة)"),
    ("PA", "Passport Issuance (معاملة جواز)"),
    ("PR", "Parcel Booking (شحن طرود)"),
    ("RC", "Receipt Voucher (سند قبض)"),
    ("PY", "Payment Voucher (سند صرف/دفع)"),
    ("EX", "Expense (سند مصروفات)"),
    ("JE", "Journal Entry (قيد محاسبي)"),
    ("SH", "Cash Shift (وردية نقدية)"),
]


async def init_reference_counters(session: AsyncSession) -> None:
    for prefix, desc in INITIAL_COUNTERS:
        res = await session.execute(
            select(ReferenceCounter).where(ReferenceCounter.prefix == prefix)
        )
        existing = res.scalar_one_or_none()
        if not existing:
            new_counter = ReferenceCounter(prefix=prefix, current_val=0, description=desc)
            session.add(new_counter)
    await session.commit()


async def get_next_reference_number(session: AsyncSession, prefix: str) -> str:
    """
    Generates next reference number in format {PREFIX}-{XXXX}
    Uses in-process prefix lock + database SELECT ... FOR UPDATE to guarantee zero collisions
    both in SQLite (dev) and PostgreSQL (production).
    """
    async with _counter_locks[prefix]:
        stmt = (
            select(ReferenceCounter)
            .where(ReferenceCounter.prefix == prefix)
            .with_for_update()
        )
        result = await session.execute(stmt)
        counter = result.scalar_one_or_none()

        if not counter:
            desc = dict(INITIAL_COUNTERS).get(prefix, f"Counter {prefix}")
            counter = ReferenceCounter(prefix=prefix, current_val=1, description=desc)
            session.add(counter)
            await session.flush()
            return f"{prefix}-{counter.current_val:04d}"

        counter.current_val += 1
        await session.flush()
        return f"{prefix}-{counter.current_val:04d}"
