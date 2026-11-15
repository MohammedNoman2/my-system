from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_accountant_or_admin
from app.core.database import get_db
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.supplier import (
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.utils.audit import log_audit_event
from app.services.accounting_service import create_entity_accounts

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("/", response_model=List[SupplierResponse])
async def list_suppliers(
    search: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Supplier).order_by(desc(Supplier.created_at))
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Supplier.name.ilike(term),
                Supplier.phone_number.ilike(term),
                Supplier.contact_person.ilike(term),
                Supplier.service_type.ilike(term),
            )
        )
    stmt = stmt.offset(offset).limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    request: Request,
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    await db.flush()

    await create_entity_accounts(db, "supplier", supplier.id, supplier.name)

    await log_audit_event(
        db,
        "INSERT",
        "suppliers",
        user=current_user,
        record_id=supplier.id,
        new_data={"name": supplier.name, "phone": supplier.phone_number},
        request=request,
    )
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get("/{id}", response_model=SupplierResponse)
async def get_supplier(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="المورد غير موجود")
    return supplier


@router.put("/{id}", response_model=SupplierResponse)
async def update_supplier(
    id: int,
    data: SupplierUpdate,
    request: Request,
    current_user: User = Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="المورد غير موجود")

    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(supplier, k, v)

    await log_audit_event(
        db,
        "UPDATE",
        "suppliers",
        user=current_user,
        record_id=supplier.id,
        new_data=update_dict,
        request=request,
    )
    await db.commit()
    await db.refresh(supplier)
    return supplier
