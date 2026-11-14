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
from app.services.accounting_service import (
    create_entity_accounts,
    get_customer_all_credit_balances,
    get_customers_credit_balances_map,
)

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
    customers = res.scalars().all()
    credit_map = await get_customers_credit_balances_map(db, [c.id for c in customers])
    items: List[CustomerSearchItem] = []
    for c in customers:
        item = CustomerSearchItem.model_validate(c)
        item.credit_balances = credit_map.get(c.id, {"YER": 0.0, "SAR": 0.0, "USD": 0.0})
        items.append(item)
    return items


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


def _normalize_phone(phone: str) -> str:
    import re
    digits = re.sub(r"\D", "", (phone or "").strip())
    if digits.startswith("00967") and len(digits) == 14:
        digits = digits[5:]
    elif digits.startswith("967") and len(digits) == 12:
        digits = digits[3:]
    return digits


def _normalize_name(name: str) -> str:
    import re
    return re.sub(r"\s+", " ", (name or "").strip())


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    norm_phone = _normalize_phone(data.phone_number)
    norm_name = _normalize_name(data.name)
    if len(norm_phone) < 9 or len(norm_phone) > 15:
        raise HTTPException(status_code=400, detail="رقم الهاتف غير صالح؛ يجب أن يتكون من 9 أرقام على الأقل")

    existing = await db.execute(
        select(Customer).where(Customer.phone_number == norm_phone, Customer.name == norm_name)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="يوجد عميل مسجل مسبقاً بنفس الاسم ورقم الهاتف")

    payload = data.model_dump()
    payload["name"] = norm_name
    payload["phone_number"] = norm_phone
    for nullable_key in ("email", "passport_number", "id_number"):
        if payload.get(nullable_key) is not None and not str(payload[nullable_key]).strip():
            payload[nullable_key] = None

    customer = Customer(**payload)
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
    resp = CustomerResponse.model_validate(customer)
    resp.credit_balances = await get_customer_all_credit_balances(db, customer.id)
    return resp


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
    if "name" in update_dict and update_dict["name"]:
        update_dict["name"] = _normalize_name(update_dict["name"])
    if "phone_number" in update_dict and update_dict["phone_number"]:
        norm_p = _normalize_phone(update_dict["phone_number"])
        if len(norm_p) < 9 or len(norm_p) > 15:
            raise HTTPException(status_code=400, detail="رقم الهاتف غير صالح؛ يجب أن يتكون من 9 أرقام على الأقل")
        update_dict["phone_number"] = norm_p
    for nullable_key in ("email", "passport_number", "id_number"):
        if nullable_key in update_dict and update_dict[nullable_key] is not None and not str(update_dict[nullable_key]).strip():
            update_dict[nullable_key] = None

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
