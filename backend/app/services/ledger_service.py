import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import to_office_time
from app.models.accounting import (
    Account,
    AccountCurrency,
    EntityAccountType,
    JournalEntry,
    JournalEntryLine,
)
from app.models.customer import Customer
from app.models.financial import FinancialTransaction
from app.models.supplier import Supplier
from app.models.voucher_allocation import VoucherAllocation


def _q2(val: Any) -> Decimal:
    return Decimal(str(val or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _balance_label(bal: Decimal, ent_enum: EntityAccountType) -> str:
    if bal == Decimal("0.00"):
        return "متزن"
    if ent_enum == EntityAccountType.CUSTOMER:
        return "عليه (مدين)" if bal > Decimal("0.00") else "له (رصيد دائن)"
    return "له (مستحق للمورد)" if bal > Decimal("0.00") else "عليه (دفعة مقدمة)"


async def get_ledger_statement(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    currency: Optional[str] = None,
) -> Dict[str, Any]:
    entity_type_upper = entity_type.upper()
    if entity_type_upper not in ["CUSTOMER", "SUPPLIER"]:
        raise HTTPException(status_code=400, detail="نوع الكيان غير صالح")

    ent_enum = (
        EntityAccountType.CUSTOMER
        if entity_type_upper == "CUSTOMER"
        else EntityAccountType.SUPPLIER
    )

    if ent_enum == EntityAccountType.CUSTOMER:
        entity = (
            await db.execute(select(Customer).where(Customer.id == entity_id))
        ).scalar_one_or_none()
    else:
        entity = (
            await db.execute(select(Supplier).where(Supplier.id == entity_id))
        ).scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="الكيان غير موجود")

    entity_dict = {
        "id": entity.id,
        "name": entity.name,
        "phone": getattr(entity, "phone_number", getattr(entity, "phone", "")),
    }

    stmt = (
        select(JournalEntryLine, JournalEntry, Account.currency)
        .join(Account, Account.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(Account.entity_type == ent_enum)
        .where(Account.entity_id == entity_id)
    )

    if currency:
        stmt = stmt.where(Account.currency == AccountCurrency(currency.upper()))

    stmt = stmt.order_by(JournalEntry.date.asc(), JournalEntryLine.id.asc())

    result = await db.execute(stmt)
    rows = result.all()

    # Pre-fetch FinancialTransactions & VoucherAllocations for rich cross-currency descriptions (P7)
    rc_refs = {
        je.reference_id
        for _, je, _ in rows
        if je.reference_type in ("RECEIPT", "PAYMENT") and je.reference_id
    }
    tx_by_ref: Dict[str, FinancialTransaction] = {}
    if rc_refs:
        tx_stmt = (
            select(FinancialTransaction)
            .where(FinancialTransaction.transaction_id.in_(rc_refs))
            .options(
                selectinload(FinancialTransaction.allocations).selectinload(
                    VoucherAllocation.booking
                )
            )
        )
        tx_res = await db.execute(tx_stmt)
        for tx_obj in tx_res.scalars().all():
            tx_by_ref[tx_obj.transaction_id] = tx_obj

    target_currencies = [currency.upper()] if currency else ["YER", "SAR", "USD"]

    ledgers: Dict[str, Any] = {}
    for cur in target_currencies:
        ledgers[cur] = {
            "opening_balance": 0.0,
            "opening_balance_label": "متزن",
            "total_debit": 0.0,
            "total_credit": 0.0,
            "closing_balance": 0.0,
            "closing_balance_label": "متزن",
            "entries": [],
        }

    for cur in target_currencies:
        cur_rows = [(l, je) for l, je, c in rows if c.name == cur]

        opening_balance = Decimal("0.00")
        period_entries: List[Dict[str, Any]] = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        used_alloc_ids: set[int] = set()

        for line, je in cur_rows:
            je_date = (
                to_office_time(je.date).date()
                if isinstance(je.date, datetime)
                else je.date
            )

            is_before = bool(from_date and je_date < from_date)
            is_in_period = True
            if from_date and je_date < from_date:
                is_in_period = False
            if to_date and je_date > to_date:
                is_in_period = False

            debit = _q2(line.debit)
            credit = _q2(line.credit)

            net_movement = (
                (debit - credit)
                if ent_enum == EntityAccountType.CUSTOMER
                else (credit - debit)
            )

            if is_before:
                opening_balance = (opening_balance + net_movement).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            elif is_in_period:
                total_debit = (total_debit + debit).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_credit = (total_credit + credit).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                date_iso = (
                    je_date.isoformat()
                    if isinstance(je_date, (datetime, date))
                    else str(je_date)
                )

                # Handle Historical Backfill (BOOKING_BACKFILL) cleanly
                if je.reference_type == "BOOKING_BACKFILL":
                    if debit > Decimal("0.00"):
                        merged = False
                        for existing_e in period_entries:
                            if (
                                existing_e.get("_je_type") == "BOOKING"
                                and existing_e["reference_id"] == je.reference_id
                            ):
                                new_d = _q2(Decimal(str(existing_e["debit"])) + debit)
                                existing_e["debit"] = float(new_d)
                                if "إجمالي القيمة" not in existing_e["description"]:
                                    existing_e["description"] += f" (إجمالي القيمة: {new_d:,.2f} {cur})"
                                merged = True
                                break
                        if not merged:
                            period_entries.append(
                                {
                                    "date": date_iso,
                                    "reference_id": je.reference_id,
                                    "description": f"قيد حجز {je.reference_id} (إجمالي القيمة: {debit:,.2f} {cur})",
                                    "debit": float(debit),
                                    "credit": 0.0,
                                    "balance": 0.0,
                                    "balance_label": "متزن",
                                    "notes": None,
                                    "_je_type": "BOOKING",
                                }
                            )
                    elif credit > Decimal("0.00"):
                        m = re.search(r"\((RC-[0-9A-Za-z-]+)\)", je.description or "")
                        rc_ref = m.group(1) if m else je.reference_id
                        period_entries.append(
                            {
                                "date": date_iso,
                                "reference_id": rc_ref,
                                "description": f"سند قبض دفعة مقدمة ({rc_ref}) عند إصدار الحجز {je.reference_id}",
                                "debit": 0.0,
                                "credit": float(credit),
                                "balance": 0.0,
                                "balance_label": "متزن",
                                "notes": None,
                                "_je_type": "RECEIPT",
                            }
                        )
                    continue

                # Build rich description for RECEIPT lines using VoucherAllocation (P7)
                desc_text = je.description
                tx_obj = tx_by_ref.get(je.reference_id)
                if je.reference_type == "RECEIPT" and tx_obj and credit > Decimal("0.00"):
                    matched_alloc = None
                    for alloc in getattr(tx_obj, "allocations", []):
                        alloc_curr = (
                            alloc.target_currency.value
                            if hasattr(alloc.target_currency, "value")
                            else str(alloc.target_currency)
                        ).upper()
                        if (
                            alloc.id not in used_alloc_ids
                            and alloc_curr == cur
                            and _q2(alloc.allocated_in_booking_currency) == credit
                        ):
                            matched_alloc = alloc
                            used_alloc_ids.add(alloc.id)
                            break

                    if matched_alloc:
                        t_no = (
                            matched_alloc.booking.ticket_number
                            if getattr(matched_alloc, "booking", None)
                            else f"#{matched_alloc.booking_id}"
                        )
                        orig_curr = (tx_obj.currency or cur).upper()
                        orig_amt = _q2(matched_alloc.allocated_amount)
                        rate_val = Decimal(str(matched_alloc.exchange_rate))
                        if orig_curr != cur:
                            desc_text = (
                                f"سند قبض {tx_obj.transaction_id} — سداد حجز {t_no} "
                                f"(المبلغ الأصلي: {orig_amt:,.2f} {orig_curr} × سعر الصرف {float(rate_val):g} = {credit:,.2f} {cur})"
                            )
                        else:
                            desc_text = f"سند قبض {tx_obj.transaction_id} — سداد مخصص لحجز {t_no} ({credit:,.2f} {cur})"
                    elif getattr(tx_obj, "allocations", []):
                        allocs_in_curr = [
                            a for a in tx_obj.allocations
                            if (
                                a.id not in used_alloc_ids
                                and (a.target_currency.value if hasattr(a.target_currency, "value") else str(a.target_currency)).upper() == cur
                            )
                        ]
                        total_alloc_curr = _q2(
                            sum((Decimal(str(a.allocated_in_booking_currency)) for a in allocs_in_curr), Decimal("0.00"))
                        )
                        if allocs_in_curr and total_alloc_curr >= credit:
                            tickets_str = "، ".join(
                                (a.booking.ticket_number if getattr(a, "booking", None) else f"#{a.booking_id}")
                                for a in allocs_in_curr
                            )
                            desc_text = (
                                f"سند قبض {tx_obj.transaction_id} — سداد مخصص للحجوزات ({tickets_str}) "
                                f"({credit:,.2f} {cur})"
                            )
                        else:
                            desc_text = (
                                f"سند قبض {tx_obj.transaction_id} — فائض دفعة مقدمة "
                                f"(رصيد دائن متاح تحت الحساب: {credit:,.2f} {cur})"
                            )

                period_entries.append(
                    {
                        "date": date_iso,
                        "reference_id": je.reference_id,
                        "description": desc_text,
                        "debit": float(debit),
                        "credit": float(credit),
                        "balance": 0.0,
                        "balance_label": "متزن",
                        "notes": None,
                        "_je_type": je.reference_type,
                    }
                )

        # Calculate running balances with 2-decimal precision and clear direction labels
        running_bal = opening_balance
        for e in period_entries:
            e.pop("_je_type", None)
            d_dec = _q2(e["debit"])
            c_dec = _q2(e["credit"])
            movement = (
                (d_dec - c_dec)
                if ent_enum == EntityAccountType.CUSTOMER
                else (c_dec - d_dec)
            )
            running_bal = (running_bal + movement).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            e["balance"] = float(running_bal)
            e["balance_label"] = _balance_label(running_bal, ent_enum)

        ledgers[cur]["opening_balance"] = float(opening_balance)
        ledgers[cur]["opening_balance_label"] = _balance_label(opening_balance, ent_enum)
        ledgers[cur]["total_debit"] = float(total_debit)
        ledgers[cur]["total_credit"] = float(total_credit)
        ledgers[cur]["closing_balance"] = float(running_bal)
        ledgers[cur]["closing_balance_label"] = _balance_label(running_bal, ent_enum)
        ledgers[cur]["entries"] = period_entries

    return {
        "entity_type": entity_type.lower(),
        "entity_id": entity_id,
        "entity": entity_dict,
        "period": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
        },
        "ledgers": ledgers,
    }
