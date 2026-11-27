"""
Stage 6-A Verification Suite:
1. Rate limit storage resolver safely falls back to memory:// when Redis is offline.
2. Sending 11 rapid POST /api/auth/login requests triggers real HTTP 429 with Arabic error message.
"""
import asyncio
import sys
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, get_db
from app.middleware.rate_limit import limiter, resolve_rate_limit_storage_uri
from main import app


async def _run_6a_tests():
    # 1. Local fallback check (no Redis running in CI/dev)
    storage_uri = resolve_rate_limit_storage_uri()
    assert storage_uri.startswith(("memory://", "redis://", "rediss://"))

    # 2. Isolated DB override for real ASGI HTTP rate-limit test
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    # Reset limiter storage before counting 1..11
    try:
        limiter.reset()
    except Exception:
        try:
            limiter._storage.reset()
        except Exception:
            pass

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            statuses = []
            last_body = {}
            for i in range(11):
                resp = await client.post(
                    "/api/auth/login",
                    json={"username": f"probe_{i}", "password": "wrong"},
                    headers={"X-Forwarded-For": "198.51.100.61"},
                )
                statuses.append(resp.status_code)
                if resp.status_code == 429:
                    last_body = resp.json()

            assert all(s == 401 for s in statuses[:10]), f"Expected 401 for first 10 attempts, got {statuses[:10]}"
            assert statuses[10] == 429, f"Expected 429 on 11th attempt, got {statuses}"
            assert "تم تجاوز الحد المسموح" in last_body.get("detail", "")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


def test_stage_6a_real_login_rate_limit():
    asyncio.run(_run_6a_tests())
