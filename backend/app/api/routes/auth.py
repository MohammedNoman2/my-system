from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    generate_password_reset_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.email_service import send_password_reset_email
from app.utils.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.username == login_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة",
        )

    # Check lockout
    now = datetime.now(timezone.utc)
    if user.locked_until:
        locked_until_utc = user.locked_until
        if locked_until_utc.tzinfo is None:
            locked_until_utc = locked_until_utc.replace(tzinfo=timezone.utc)
        if now < locked_until_utc:
            remaining_mins = int((locked_until_utc - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"تم قفل الحساب مؤقتاً بسبب تكرار المحاولات الفاشلة. يرجى المحاولة بعد {remaining_mins} دقيقة.",
            )

    # Verify password
    if not verify_password(login_data.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"تم قفل الحساب لمدة {settings.LOCKOUT_DURATION_MINUTES} دقيقة بسبب تجاوز الحد الأقصى للمحاولات الفاشلة (5 محاولات).",
            )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"اسم المستخدم أو كلمة المرور غير صحيحة. المحاولات المتبقية: {settings.MAX_FAILED_LOGIN_ATTEMPTS - user.failed_login_attempts}",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذا الحساب معطل حالياً، تواصل مع مسؤول النظام.",
        )

    # Successful login: reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = now

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    user.refresh_token = refresh_token
    await db.commit()

    csrf_token = generate_csrf_token()

    # Set HTTP-only cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )
    # Double-submit cookie for JS readability
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=False,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )

    await log_audit_event(db, "LOGIN", "users", user=user, record_id=user.id, request=request)
    await db.commit()

    return TokenResponse(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        csrf_token=csrf_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز التحديث مفقود",
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز التحديث غير صالح أو منتهي الصلاحية",
        )

    user_id = payload.get("sub")
    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.refresh_token != token or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="جلسة العمل غير صالحة، يرجى تسجيل الدخول من جديد",
        )

    new_access_token = create_access_token(user.id)
    csrf_token = generate_csrf_token()

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )

    return TokenResponse(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        csrf_token=csrf_token,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get("access_token")
    if token:
        payload = decode_token(token)
        if payload and payload.get("sub"):
            user_id = payload.get("sub")
            stmt = select(User).where(User.id == int(user_id))
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                user.refresh_token = None
                await log_audit_event(db, "LOGOUT", "users", user=user, record_id=user.id, request=request)
                await db.commit()

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"message": "تم تسجيل الخروج بنجاح"}


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user and user.is_active:
        token = generate_password_reset_token(user.email)
        await send_password_reset_email(user.email, token)

    return {
        "message": "إذا كان البريد الإلكتروني مسجلاً لدينا، فستصلك تعليمات استعادة كلمة المرور قريباً."
    }


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    email = verify_password_reset_token(data.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رابط إعادة تعيين كلمة المرور غير صالح أو انتهت صلاحيته (المدة المحددة ساعة واحدة)",
        )

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المستخدم غير موجود")

    user.password_hash = get_password_hash(data.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.refresh_token = None
    await db.commit()

    return {"message": "تم تغيير كلمة المرور بنجاح، يمكنك الآن تسجيل الدخول."}
