from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.security import generate_csrf_token

EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if cookie already exists; if not, prepare to issue one
        cookie_csrf = request.cookies.get("csrf_token")

        normalized_path = request.url.path.rstrip("/")
        exempt_normalized = {p.rstrip("/") for p in EXEMPT_PATHS}

        if request.method not in SAFE_METHODS and normalized_path not in exempt_normalized:
            header_csrf = request.headers.get("X-CSRF-Token")
            if not header_csrf or not cookie_csrf or header_csrf != cookie_csrf:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "فشل التحقق من أمان CSRF (رمز الحماية غير متطابق أو مفقود)"},
                )

        response = await call_next(request)

        # If client does not have csrf_token cookie, set it (unless response already set it)
        has_csrf_in_response = any(
            b"csrf_token=" in header_val
            for header_name, header_val in response.raw_headers
            if header_name.lower() == b"set-cookie"
        )
        if not cookie_csrf and not has_csrf_in_response:
            new_csrf = generate_csrf_token()
            response.set_cookie(
                key="csrf_token",
                value=new_csrf,
                httponly=False,  # Accessible to JavaScript for double-submit header
                samesite="lax",
                secure=False,    # Allow in local development / HTTP
                path="/",
            )

        return response
