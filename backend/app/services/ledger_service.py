from decimal import Decimal
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.accounting import Account, JournalEntry, JournalEntryLine, EntityAccountType, AccountCurrency
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.core.config import to_office_time

async def get_ledger_statement(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    currency: Optional[str] = None
) -> Dict[str, Any]:
    
    entity_type_upper = entity_type.upper()
    if entity_type_upper not in ["CUSTOMER", "SUPPLIER"]:
        raise HTTPException(status_code=400, detail="نوع الكيان غير صالح")
        
    ent_enum = EntityAccountType.CUSTOMER if entity_type_upper == "CUSTOMER" else EntityAccountType.SUPPLIER
    
    if ent_enum == EntityAccountType.CUSTOMER:
        entity = (await db.execute(select(Customer).where(Customer.id == entity_id))).scalar_one_or_none()
    else:
        entity = (await db.execute(select(Supplier).where(Supplier.id == entity_id))).scalar_one_or_none()
        
    if not entity:
        raise HTTPException(status_code=404, detail="الكيان غير موجود")
        
    entity_dict = {
        "id": entity.id,
        "name": entity.name,
        "phone": getattr(entity, "phone_number", getattr(entity, "phone", ""))
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
    rows = result.all() # list of (JournalEntryLine, JournalEntry, AccountCurrency)
    
    target_currencies = [currency.upper()] if currency else ["YER", "SAR", "USD"]
    
    ledgers = {}
    for cur in target_currencies:
        ledgers[cur] = {
            "opening_balance": Decimal("0.00"),
            "total_debit": Decimal("0.00"),
            "total_credit": Decimal("0.00"),
            "closing_balance": Decimal("0.00"),
            "entries": []
        }
    
    for cur in target_currencies:
        cur_rows = [(l, je) for l, je, c in rows if c.name == cur]
        
        opening_balance = Decimal("0.00")
        period_entries = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        
        for line, je in cur_rows:
            je_date = to_office_time(je.date).date() if isinstance(je.date, datetime) else je.date
            
            is_before = False
            if from_date and je_date < from_date:
                is_before = True
                
            is_in_period = True
            if from_date and je_date < from_date:
                is_in_period = False
            if to_date and je_date > to_date:
                is_in_period = False
                
            debit = Decimal(str(line.debit))
            credit = Decimal(str(line.credit))
            
            net_movement = (debit - credit) if ent_enum == EntityAccountType.CUSTOMER else (credit - debit)
            
            if is_before:
                opening_balance += net_movement
            elif is_in_period:
                total_debit += debit
                total_credit += credit
                period_entries.append({
                    "date": je_date.isoformat() if isinstance(je_date, (datetime, date)) else str(je_date),
                    "reference_id": je.reference_id,
                    "description": je.description,
                    "debit": float(debit),
                    "credit": float(credit),
                    "balance": 0.0, # Will calculate below
                    "notes": None
                })
                
        # Calculate running balances
        running_bal = opening_balance
        for e in period_entries:
            movement = (Decimal(str(e["debit"])) - Decimal(str(e["credit"]))) if ent_enum == EntityAccountType.CUSTOMER else (Decimal(str(e["credit"])) - Decimal(str(e["debit"])))
            running_bal += movement
            e["balance"] = float(running_bal)
            
        ledgers[cur]["opening_balance"] = float(opening_balance)
        ledgers[cur]["total_debit"] = float(total_debit)
        ledgers[cur]["total_credit"] = float(total_credit)
        ledgers[cur]["closing_balance"] = float(running_bal)
        ledgers[cur]["entries"] = period_entries

    return {
        "entity_type": entity_type.lower(),
        "entity_id": entity_id,
        "entity": entity_dict,
        "period": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None
        },
        "ledgers": ledgers
    }
