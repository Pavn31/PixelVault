import shutil
import time
from pathlib import Path

from celery import shared_task
from django.conf import settings


@shared_task(ignore_result=True)
def cleanup_temporary_files() -> int:
    root = Path(settings.BASE_DIR) / "temporary"
    if not root.exists():
        return 0
    cutoff = time.time() - settings.PIXELVAULT_TEMP_RETENTION_SECONDS
    removed = 0
    for item in root.iterdir():
        try:
            if item.stat().st_mtime >= cutoff:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1
        except FileNotFoundError:
            continue
    return removed
