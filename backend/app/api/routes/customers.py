from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerResponse,
    CustomerSearchItem,
    CustomerUpdate,
)
from app.utils.audit import log_audit_event
from app.services.accounting_service import create_entity_accounts

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/search", response_model=List[CustomerSearchItem])
async def search_customers(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Smart search for customer autocomplete (debounced on client).
    Searches by name, phone, passport, or id_number.
    """
    term = f"%{q.strip()}%"
    stmt = (
        select(Customer)
        .where(
            or_(
                Customer.name.ilike(term),
                Customer.phone_number.ilike(term),
                Customer.passport_number.ilike(term),
                Customer.id_number.ilike(term),
            )
        )
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/", response_model=List[CustomerResponse])
async def list_customers(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Customer).order_by(desc(Customer.created_at))
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(term),
                Customer.phone_number.ilike(term),
                Customer.passport_number.ilike(term),
                Customer.id_number.ilike(term),
            )
        )
    stmt = stmt.offset(offset).limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check phone unique
    existing = await db.execute(
        select(Customer).where(Customer.phone_number == data.phone_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً لعميل آخر")

    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.flush()

    await create_entity_accounts(db, "customer", customer.id, customer.name)

    await log_audit_event(
        db,
        "INSERT",
        "customers",
        user=current_user,
        record_id=customer.id,
        new_data={"name": customer.name, "phone": customer.phone_number},
        request=request,
    )
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/{id}", response_model=CustomerResponse)
async def get_customer(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, id)
    if not customer:
        raise HTTPException(status_code=404, detail="العميل غير موجود")
    return customer


@router.put("/{id}", response_model=CustomerResponse)
async def update_customer(
    id: int,
    data: CustomerUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, id)
    if not customer:
        raise HTTPException(status_code=404, detail="العميل غير موجود")

    update_dict = data.model_dump(exclude_unset=True)
    if "phone_number" in update_dict and update_dict["phone_number"] != customer.phone_number:
        chk = await db.execute(
            select(Customer).where(Customer.phone_number == update_dict["phone_number"])
        )
        if chk.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً لعميل آخر")

    for k, v in update_dict.items():
        setattr(customer, k, v)

    await log_audit_event(
        db,
        "UPDATE",
        "customers",
        user=current_user,
        record_id=customer.id,
        new_data=update_dict,
        request=request,
    )
    await db.commit()
    await db.refresh(customer)
    return customer
