from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.exchange_rate import ExchangeRate
from app.models.settings import Settings
from app.models.user import User
from app.schemas.settings import (
    ExchangeRateCreate,
    ExchangeRateResponse,
    ExchangeRateUpdate,
    PublicSettingsResponse,
    SettingsResponse,
    SettingsUpdate,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.utils.audit import log_audit_event
from fastapi import File, UploadFile
import base64
from pathlib import Path

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/public", response_model=PublicSettingsResponse)
async def get_public_settings(
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint for login page and unauthenticated branding display."""
    res = await db.execute(select(Settings).limit(1))
    s = res.scalar_one_or_none()
    if not s:
        s = Settings()
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return s


@router.get("/office", response_model=SettingsResponse)
async def get_office_settings(
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Settings).limit(1))
    s = res.scalar_one_or_none()
    if not s:
        s = Settings()
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return s


@router.put("/office", response_model=SettingsResponse)
async def update_office_settings(
    data: SettingsUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Settings).limit(1))
    s = res.scalar_one_or_none()
    if not s:
        s = Settings()
        db.add(s)

    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(s, k, v)

    await log_audit_event(
        db,
        "UPDATE",
        "settings",
        user=current_user,
        record_id=s.id,
        new_data=update_dict,
        request=request,
    )
    await db.commit()
    await db.refresh(s)
    return s


@router.post("/logo", response_model=SettingsResponse)
async def upload_logo(
    request: Request,
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and synchronize office logo. Supports multipart file upload OR JSON base64 data.
    """
    res = await db.execute(select(Settings).limit(1))
    s = res.scalar_one_or_none()
    if not s:
        s = Settings()
        db.add(s)

    # Check if multipart file uploaded
    if file:
        content = await file.read()
        mime_type = file.content_type or "image/png"
        b64_str = f"data:{mime_type};base64,{base64.b64encode(content).decode('utf-8')}"
        s.logo_data = b64_str
        
        # Also persist to static dir if available
        static_dir = Path(__file__).resolve().parent.parent.parent / "static" / "uploads"
        static_dir.mkdir(parents=True, exist_ok=True)
        ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "png"
        logo_path = static_dir / f"logo.{ext}"
        with open(logo_path, "wb") as f:
            f.write(content)
        s.logo_image_url = f"/static/uploads/logo.{ext}"
    else:
        # Check if JSON payload was sent with logo_data
        try:
            body = await request.json()
            if "logo_data" in body:
                s.logo_data = body["logo_data"]
            if "logo_image_url" in body:
                s.logo_image_url = body["logo_image_url"]
        except Exception:
            raise HTTPException(status_code=400, detail="يجب إرفاق ملف صورة أو إرسال logo_data")

    await log_audit_event(
        db,
        "UPDATE",
        "settings",
        user=current_user,
        record_id=s.id,
        new_data={"action": "upload_logo"},
        request=request,
    )
    await db.commit()
    await db.refresh(s)
    return s


# Exchange Rates
@router.get("/exchange-rates", response_model=List[ExchangeRateResponse])
async def list_exchange_rates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(ExchangeRate).order_by(ExchangeRate.from_currency))
    return res.scalars().all()


@router.post("/exchange-rates", response_model=ExchangeRateResponse)
async def upsert_exchange_rate(
    data: ExchangeRateCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ExchangeRate).where(
        ExchangeRate.from_currency == data.from_currency,
        ExchangeRate.to_currency == data.to_currency,
    )
    res = await db.execute(stmt)
    rate = res.scalar_one_or_none()

    if rate:
        rate.rate = data.rate
        rate.updated_by = current_user.id
    else:
        rate = ExchangeRate(
            from_currency=data.from_currency,
            to_currency=data.to_currency,
            rate=data.rate,
            updated_by=current_user.id,
        )
        db.add(rate)

    await log_audit_event(
        db,
        "UPDATE" if rate.id else "INSERT",
        "exchange_rates",
        user=current_user,
        record_id=rate.id,
        new_data={"pair": f"{data.from_currency}/{data.to_currency}", "rate": float(data.rate)},
        request=request,
    )
    await db.commit()
    await db.refresh(rate)
    return rate


# Users Management (Admin Only)
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(User).order_by(User.id))
    return res.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="اسم المستخدم مسجل مسبقاً")

    if data.email:
        existing_email = await db.execute(select(User).where(User.email == data.email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")

    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        full_name=data.full_name,
        role=data.role,
        email=data.email,
        phone_number=data.phone_number,
        is_active=data.is_active,
    )
    db.add(user)
    await db.flush()

    await log_audit_event(
        db,
        "INSERT",
        "users",
        user=current_user,
        record_id=user.id,
        new_data={"username": user.username, "role": user.role.value},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{id}", response_model=UserResponse)
async def update_user(
    id: int,
    data: UserUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    update_dict = data.model_dump(exclude_unset=True)
    if "password" in update_dict and update_dict["password"]:
        user.password_hash = get_password_hash(update_dict.pop("password"))

    for k, v in update_dict.items():
        setattr(user, k, v)

    await log_audit_event(
        db,
        "UPDATE",
        "users",
        user=current_user,
        record_id=user.id,
        new_data={"username": user.username, "updated_fields": list(update_dict.keys())},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/status")
async def toggle_user_status(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """تفعيل أو تعطيل حساب مستخدم — المدير فقط ولا يمكن تعطيل حسابه الخاص."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="لا يمكنك تعطيل حسابك الخاص")
    if user.role.value == "admin" and not user.is_active:
        # Allow reactivation of admin accounts but not self-disabling
        pass

    user.is_active = not user.is_active
    action_label = "تفعيل" if user.is_active else "تعطيل"
    await log_audit_event(
        db, "UPDATE", "users", user=current_user,
        record_id=user.id,
        new_data={"action": action_label, "is_active": user.is_active},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return {"message": f"تم {action_label} حساب {user.full_name} بنجاح", "is_active": user.is_active, "user_id": user.id}


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """إعادة تعيين كلمة مرور مستخدم — المدير فقط."""
    from pydantic import BaseModel

    class ResetPasswordBody(BaseModel):
        new_password: str

    body = await request.json()
    new_password = body.get("new_password", "")
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    user.password_hash = get_password_hash(new_password)
    await log_audit_event(
        db, "UPDATE", "users", user=current_user,
        record_id=user.id,
        new_data={"action": "reset_password", "username": user.username},
        request=request,
    )
    await db.commit()
    return {"message": f"تم إعادة تعيين كلمة مرور {user.full_name} بنجاح"}


# Audit Logs (Admin Only)
@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return logs
