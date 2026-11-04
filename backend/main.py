from contextlib import asynccontextmanager
from decimal import Decimal
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from app.api.routes import (
    auth,
    bookings,
    customers,
    dashboard,
    finance,
    ocr,
    reports,
    settings as settings_route,
    suppliers,
)
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import get_password_hash
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import limiter
from app.models import ExchangeRate, Settings, User, UserRole
from app.services.counter_service import init_reference_counters


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if not present
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize default data in a session
    async with AsyncSessionLocal() as session:
        # 1. Initialize 8 Reference Counters
        await init_reference_counters(session)

        # 2. Initialize default Admin user if none exists
        res = await session.execute(select(User).where(User.username == "admin"))
        admin = res.scalar_one_or_none()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="مدير النظام الرئيسي",
                role=UserRole.ADMIN,
                email="admin@alamalnaql.com",
                phone_number="778699440",
                is_active=True,
            )
            session.add(admin)

        # 3. Initialize default Employee user for testing
        emp_res = await session.execute(select(User).where(User.username == "employee"))
        emp = emp_res.scalar_one_or_none()
        if not emp:
            emp = User(
                username="employee",
                password_hash=get_password_hash("employee123"),
                full_name="أحمد الموظف",
                role=UserRole.EMPLOYEE,
                email="employee@alamalnaql.com",
                phone_number="771609217",
                is_active=True,
            )
            session.add(emp)

        # 4. Initialize default Accountant user for testing
        acc_res = await session.execute(select(User).where(User.username == "accountant"))
        acc = acc_res.scalar_one_or_none()
        if not acc:
            acc = User(
                username="accountant",
                password_hash=get_password_hash("accountant123"),
                full_name="سالم المحاسب",
                role=UserRole.ACCOUNTANT,
                email="accountant@alamalnaql.com",
                phone_number="771292978",
                is_active=True,
            )
            session.add(acc)

        # 5. Initialize Office Settings with Tagline
        s_res = await session.execute(select(Settings).limit(1))
        office_s = s_res.scalar_one_or_none()
        if not office_s:
            office_s = Settings(
                office_name="عالم النقل",
                tagline="للسفريات والنقل البري والتخليص",
                address="صنعاء - الستين الجنوبي - جوار فندق أبراج النيل",
                phone_numbers="778699440 - 771609217 - 771292978 01601217",
                email="info@alamalnaql.com",
                website="www.alamalnaql.com",
                default_currency="YER",
                footer_text="عالم النقل للسفريات - ثقتكم رصيدنا الأعلى",
            )
            session.add(office_s)

        # 6. Initialize Exchange Rates
        ex_res = await session.execute(select(ExchangeRate).limit(1))
        if not ex_res.scalars().first():
            session.add_all([
                ExchangeRate(from_currency="USD", to_currency="YER", rate=Decimal("530.0000")),
                ExchangeRate(from_currency="SAR", to_currency="YER", rate=Decimal("140.0000")),
                ExchangeRate(from_currency="USD", to_currency="SAR", rate=Decimal("3.7500")),
            ])

        await session.commit()

    yield
    # Shutdown logic
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="منصة الحجوزات المتقدمة (ARP) لمكاتب السفر والسياحة",
    version="2.1.0",
    lifespan=lifespan,
)

# Slowapi state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:80",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF Middleware
app.add_middleware(CSRFMiddleware)

import logging
from datetime import datetime
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

api_logger = logging.getLogger("arp.http")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    api_logger.warning(f"[{ts}] HTTP {exc.status_code} on {request.method} {request.url.path} -> {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None) or None,
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    api_logger.warning(f"[{ts}] HTTP 422 Validation Error on {request.method} {request.url.path} -> {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": "2.1.0"}


# Mount Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(bookings.router, prefix=settings.API_V1_STR)
app.include_router(finance.router, prefix=settings.API_V1_STR)
app.include_router(customers.router, prefix=settings.API_V1_STR)
app.include_router(suppliers.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)
app.include_router(settings_route.router, prefix=settings.API_V1_STR)
app.include_router(ocr.router, prefix=settings.API_V1_STR)
