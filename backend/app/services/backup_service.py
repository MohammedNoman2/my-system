import gzip
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

from app.core.config import BASE_DIR, OFFICE_TZ, settings

BACKUPS_DIR = BASE_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_sqlite_path(db_url: str) -> Path:
    prefix = "sqlite+aiosqlite:///"
    if db_url.startswith(prefix):
        raw_path = db_url[len(prefix):]
    elif db_url.startswith("sqlite:///"):
        raw_path = db_url[len("sqlite:///"):]
    else:
        return BASE_DIR / "arp.db"
    p = Path(raw_path)
    return p if p.is_absolute() else (BASE_DIR / p)


def _verify_sqlite_restore(backup_gz_path: Path) -> Dict[str, Any]:
    """يفك ضغط النسخة الاحتياطية إلى ملف مؤقت، ويتحقق من سلامتها عبر PRAGMA integrity_check وعدّ الجداول."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        restored_db = Path(tmp_dir) / "restored_verify.db"
        with gzip.open(backup_gz_path, "rb") as gz_in, open(restored_db, "wb") as out_f:
            shutil.copyfileobj(gz_in, out_f)

        conn = sqlite3.connect(str(restored_db))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            assert integrity == "ok", f"فشل فحص سلامة النسخة الاحتياطية: {integrity}"

            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            counts: Dict[str, int] = {}
            for tbl in ("bookings", "customers", "journal_entries"):
                if tbl in tables:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                    counts[tbl] = int(cur.fetchone()[0])
            return {"integrity": integrity, "tables_count": len(tables), "row_counts": counts}
        finally:
            conn.close()


def create_database_backup(
    db_url: str | None = None,
    backup_dir: Path | None = None,
    keep_last: int = 30,
) -> Dict[str, Any]:
    """
    ينشئ نسخة احتياطية مضغوطة ومتحقق من إمكانية استعادتها لقاعدة البيانات:
    - SQLite: يستخدم sqlite3.Connection.backup() الذري عبر الإنترنت ثم gzip ثم اختبار استعادة فعلي.
    - PostgreSQL: يستخدم pg_dump لإنتاج نسخة SQL مضغوطة مع التحقق من عدم خلوها.
    """
    target_url = db_url or settings.DATABASE_URL
    target_dir = backup_dir or BACKUPS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(OFFICE_TZ).strftime("%Y%m%d_%H%M%S")

    if "sqlite" in target_url.lower():
        src_db = _resolve_sqlite_path(target_url)
        if not src_db.exists():
            raise FileNotFoundError(f"ملف قاعدة البيانات غير موجود: {src_db}")

        backup_path = target_dir / f"arp_sqlite_backup_{ts}.db.gz"
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_copy = Path(tmp_dir) / "snapshot.db"
            src_conn = sqlite3.connect(str(src_db))
            dst_conn = sqlite3.connect(str(raw_copy))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

            with open(raw_copy, "rb") as f_in, gzip.open(backup_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        verify_info = _verify_sqlite_restore(backup_path)
        _prune_old_backups(target_dir, keep_last)
        return {
            "engine": "sqlite",
            "filename": backup_path.name,
            "path": str(backup_path),
            "size_bytes": backup_path.stat().st_size,
            "verified": True,
            "verification": verify_info,
            "created_at": datetime.now(OFFICE_TZ).isoformat(),
        }

    elif "postgresql" in target_url.lower():
        parsed = urlparse(target_url.replace("postgresql+asyncpg://", "postgresql://"))
        env = os.environ.copy()
        if parsed.password:
            env["PGPASSWORD"] = unquote(parsed.password)
        pg_dump_bin = shutil.which("pg_dump")
        if not pg_dump_bin:
            raise RuntimeError("أداة pg_dump غير متوفرة في هذه البيئة؛ شغّل النسخ الاحتياطي من حاوية PostgreSQL.")

        backup_path = target_dir / f"arp_pg_backup_{ts}.sql.gz"
        cmd = [
            pg_dump_bin,
            "-h", parsed.hostname or "postgres",
            "-p", str(parsed.port or 5432),
            "-U", parsed.username or "arp_user",
            "-d", (parsed.path or "/arp_db").lstrip("/"),
            "--no-owner",
            "--no-acl",
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, check=True)
        assert len(res.stdout) > 0, "pg_dump أرجع مخرجات فارغة!"
        with gzip.open(backup_path, "wb") as f_out:
            f_out.write(res.stdout)

        _prune_old_backups(target_dir, keep_last)
        return {
            "engine": "postgresql",
            "filename": backup_path.name,
            "path": str(backup_path),
            "size_bytes": backup_path.stat().st_size,
            "verified": True,
            "verification": {"sql_bytes": len(res.stdout)},
            "created_at": datetime.now(OFFICE_TZ).isoformat(),
        }

    raise ValueError(f"محرك قاعدة البيانات غير مدعوم للنسخ الاحتياطي: {target_url}")


def _prune_old_backups(backup_dir: Path, keep_last: int) -> None:
    files = sorted(
        [p for p in backup_dir.glob("arp_*_backup_*.gz") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old_f in files[keep_last:]:
        old_f.unlink(missing_ok=True)


def list_backups(backup_dir: Path | None = None) -> List[Dict[str, Any]]:
    target_dir = backup_dir or BACKUPS_DIR
    if not target_dir.exists():
        return []
    files = sorted(
        [p for p in target_dir.glob("arp_*_backup_*.gz") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=OFFICE_TZ).isoformat(),
        }
        for f in files
    ]
