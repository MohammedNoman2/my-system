import asyncio
import base64
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from main import app
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.database import Base
from app.models.user import User, UserRole
from app.api.routes.settings import upload_logo
from app.api.routes.customers import list_customers
from app.api.routes.suppliers import list_suppliers


class _DummyClient:
    host = "127.0.0.1"


class _DummyRequest:
    client = _DummyClient()
    headers = {"user-agent": "stage4d-verifier"}

    def __init__(self, json_body=None):
        self._json_body = json_body

    async def json(self):
        if self._json_body is None:
            raise ValueError("No JSON body")
        return self._json_body


# Minimal valid 1x1 PNG bytes
VALID_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


async def run_stage_4d_verification():
    root_dir = Path(__file__).resolve().parent.parent.parent

    # 1. Verify docker-compose.yml & .gitignore hardening
    dc_text = (root_dir / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"5432:5432"' not in dc_text and '"6379:6379"' not in dc_text, (
        "Ports 5432 or 6379 are still exposed in docker-compose.yml!"
    )
    assert "${POSTGRES_PASSWORD" in dc_text and "${SECRET_KEY" in dc_text and "${CSRF_SECRET_KEY" in dc_text, (
        "Hardcoded secrets not replaced with env vars in docker-compose.yml!"
    )
    gi_text = (root_dir / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gi_text and "backend/static/uploads/" in gi_text, (
        ".env or backend/static/uploads/ missing from .gitignore!"
    )

    # 2. Verify hmac.compare_digest with .encode in csrf.py
    csrf_text = (root_dir / "backend/app/middleware/csrf.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in csrf_text and '.encode("utf-8"' in csrf_text, (
        "hmac.compare_digest with UTF-8 encode missing in csrf.py!"
    )

    # 3. Verify SettingsPage.tsx removed image/svg+xml
    sp_text = (root_dir / "frontend/src/pages/settings/SettingsPage.tsx").read_text(encoding="utf-8")
    assert "image/svg+xml" not in sp_text, "image/svg+xml must be removed from SettingsPage.tsx!"

    # 4. Verify upload_logo security checks on isolated in-memory DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    static_logo_path = root_dir / "backend/static/uploads/logo.png"
    pre_existed = static_logo_path.exists()
    prev_bytes = static_logo_path.read_bytes() if pre_existed else None

    try:
        async with Session() as db:
            admin = User(
                username="admin",
                password_hash="x",
                full_name="مدير النظام",
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)

            # 4-A: Reject fake PNG (script disguised as image/png)
            fake_file = UploadFile(
                file=io.BytesIO(b"<script>alert(1)</script>"),
                filename="evil.png",
                headers=Headers({"content-type": "image/png"}),
            )
            fake_rejected = False
            try:
                await upload_logo(request=_DummyRequest(), file=fake_file, current_user=admin, db=db)
            except HTTPException as exc:
                assert exc.status_code == 400
                fake_rejected = True
            assert fake_rejected, "Disguised non-image file must be rejected with 400!"

            # 4-B: Reject SVG upload
            svg_file = UploadFile(
                file=io.BytesIO(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
                filename="logo.svg",
                headers=Headers({"content-type": "image/svg+xml"}),
            )
            svg_rejected = False
            try:
                await upload_logo(request=_DummyRequest(), file=svg_file, current_user=admin, db=db)
            except HTTPException as exc:
                assert exc.status_code == 400
                svg_rejected = True
            assert svg_rejected, "SVG logo must be rejected with 400!"

            # 4-C: Reject oversized (> 2MB) file
            huge_bytes = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (2 * 1024 * 1024 + 100))
            huge_file = UploadFile(
                file=io.BytesIO(huge_bytes),
                filename="huge.png",
                headers=Headers({"content-type": "image/png"}),
            )
            huge_rejected = False
            try:
                await upload_logo(request=_DummyRequest(), file=huge_file, current_user=admin, db=db)
            except HTTPException as exc:
                assert exc.status_code == 400
                huge_rejected = True
            assert huge_rejected, "Oversized (>2MB) logo must be rejected with 400!"

            # 4-D: Accept valid PNG upload
            valid_file = UploadFile(
                file=io.BytesIO(VALID_PNG_BYTES),
                filename="brand.png",
                headers=Headers({"content-type": "image/png"}),
            )
            saved_settings = await upload_logo(
                request=_DummyRequest(), file=valid_file, current_user=admin, db=db
            )
            assert saved_settings.logo_data.startswith("data:image/png;base64,")
            assert saved_settings.logo_image_url == "/static/uploads/logo.png"

            # 5. Verify list_customers and list_suppliers support limit=1000 without error
            c_list = await list_customers(search=None, limit=1000, offset=0, current_user=admin, db=db)
            s_list = await list_suppliers(search=None, limit=1000, offset=0, current_user=admin, db=db)
            assert isinstance(c_list, list) and isinstance(s_list, list)
    finally:
        if pre_existed and prev_bytes is not None:
            static_logo_path.write_bytes(prev_bytes)
        elif static_logo_path.exists():
            static_logo_path.unlink()

    await engine.dispose()

    # 6. Verify frontend ErrorBoundary & dynamic exchange rates in ReceiptVoucherModal.tsx
    rv_text = (root_dir / "frontend/src/components/finance/ReceiptVoucherModal.tsx").read_text(encoding="utf-8")
    assert "/settings/exchange-rates" in rv_text and "limit=1000" in rv_text, (
        "Dynamic exchange rates or limit=1000 missing in ReceiptVoucherModal.tsx!"
    )
    assert (root_dir / "frontend/src/components/common/ErrorBoundary.tsx").exists(), (
        "ErrorBoundary.tsx missing!"
    )
    app_text = (root_dir / "frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "<ErrorBoundary>" in app_text, "ErrorBoundary not wrapping App.tsx!"

    # 7. Verify 0 files in the repository have UTF-8 BOM (\xef\xbb\xbf)
    exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json", ".md", ".yml"}
    bom_files = []
    for r, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "dist", "__pycache__"}]
        for fn in files:
            fp = Path(r) / fn
            if fp.suffix.lower() in exts and fp.read_bytes().startswith(b"\xef\xbb\xbf"):
                bom_files.append(str(fp.relative_to(root_dir)))
    assert not bom_files, f"UTF-8 BOM detected in files: {bom_files}"

    paths = list(app.openapi()["paths"].keys())
    print("TOTAL_ROUTES:", len(paths))
    print("UTF8_BOM_FILES_COUNT: 0")
    print("STAGE_4D_FUNCTIONAL_VERIFICATION: PASSED 100%")


if __name__ == "__main__":
    asyncio.run(run_stage_4d_verification())
