import os
import shutil
import time
from pathlib import Path

from app.core.config import settings
from app.core.security import resolve_job_dir


def delete_storage_item(item_id: str) -> bool:
    """Immediately wipe an uploaded/compressed job directory from ephemeral storage."""
    try:
        target = resolve_job_dir(item_id)
        if target.exists() and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            return True
        return False
    except Exception:
        return False


def purge_expired_files() -> int:
    """Remove ephemeral PDF storage directories older than FILE_RETENTION_MINUTES."""
    root = Path(settings.STORAGE_DIR)
    if not root.exists():
        return 0
    ttl_seconds = settings.FILE_RETENTION_MINUTES * 60
    now = time.time()
    removed = 0
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            mtime = child.stat().st_mtime
            if (now - mtime) > ttl_seconds:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


def count_stored_items() -> int:
    root = Path(settings.STORAGE_DIR)
    if not root.exists():
        return 0
    return sum(1 for c in root.iterdir() if c.is_dir())
