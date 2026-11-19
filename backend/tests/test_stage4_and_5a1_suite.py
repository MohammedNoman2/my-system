import asyncio
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings
from app.core.database import Base
from app.services.backup_service import create_database_backup, list_backups
from tests.verify_stage_4a import run_functional_tests
from tests.verify_stage_4b import run_stage_4b_verification
from tests.verify_stage_4c import run_stage_4c_verification
from tests.verify_stage_4d import run_stage_4d_verification


def test_stage_4a_suite():
    asyncio.run(run_functional_tests())


def test_stage_4b_suite():
    asyncio.run(run_stage_4b_verification())


def test_stage_4c_suite():
    asyncio.run(run_stage_4c_verification())


def test_stage_4d_suite():
    asyncio.run(run_stage_4d_verification())


def test_5a1_production_secret_guard():
    # Development mode allows default dev keys
    dev_cfg = Settings(ENVIRONMENT="development")
    assert dev_cfg.ENVIRONMENT == "development"

    # Production mode MUST reject default weak secrets (passed explicitly so local .env does not mask them)
    with pytest.raises(ValueError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="arp-secret-key-production-super-secure-change-in-env-2026",
            CSRF_SECRET_KEY="csrf-secret-key-arp-double-submit-2026",
            PASSWORD_RESET_SECRET="password-reset-itsdangerous-secret-2026",
        )

    # Production mode accepts strong rotated secrets
    prod_cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="prod-super-strong-rotated-secret-key-2026-xyz",
        CSRF_SECRET_KEY="prod-super-strong-rotated-csrf-key-2026-xyz",
        PASSWORD_RESET_SECRET="prod-super-strong-rotated-reset-key-2026-xyz",
    )
    assert prod_cfg.ENVIRONMENT == "production"


def test_5a1_alembic_upgrade_on_temp_sqlite_copy():
    """يتحقق من تشغيل ترحيلات Alembic على نسخة مؤقتة معزولة دون لمس backend/arp.db الأصلي."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_db = Path(tmp_dir) / "temp_alembic_test.db"
        real_db = BACKEND_DIR / "arp.db"
        alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{temp_db.as_posix()}")

        if real_db.exists():
            shutil.copy2(real_db, temp_db)
        else:
            # In CI (no arp.db), simulate an existing DB created via Base.metadata.create_all
            sync_engine = create_engine(f"sqlite:///{temp_db.as_posix()}")
            Base.metadata.create_all(sync_engine)
            sync_engine.dispose()

        conn = sqlite3.connect(str(temp_db))
        has_alembic = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        conn.close()
        if not has_alembic:
            command.stamp(alembic_cfg, "655210f0992f")
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(str(temp_db))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()}
        ver = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        conn.close()
        assert "credit_applied" in cols
        assert ver in ("b7c8d9e0f1a2", "c9d0e1f2a3b4")


def test_5a1_backup_and_restore_integrity():
    """يختبر إنشاء نسخة احتياطية مضغوطة واستعادتها والتحقق من سلامتها عبر PRAGMA integrity_check."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sample_db = Path(tmp_dir) / "sample.db"
        backup_dir = Path(tmp_dir) / "backups"
        conn = sqlite3.connect(str(sample_db))
        conn.execute("CREATE TABLE bookings (id INTEGER PRIMARY KEY, ticket_number TEXT)")
        conn.execute("INSERT INTO bookings (ticket_number) VALUES ('FL-0001')")
        conn.commit()
        conn.close()

        info = create_database_backup(
            db_url=f"sqlite+aiosqlite:///{sample_db.as_posix()}",
            backup_dir=backup_dir,
        )
        assert info["verified"] is True
        assert info["verification"]["integrity"] == "ok"
        assert info["verification"]["row_counts"]["bookings"] == 1
        assert len(list_backups(backup_dir)) == 1
