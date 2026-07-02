import json
import os
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def log_cron_status(job_name: str, status: str, error: str = None):
    """
    Log the status of a cron job to a shared JSON file.
    Works seamlessly whether run inside Docker or on the host.
    """
    # 1. Detect logs directory
    possible_paths = [
        Path("/app/logs"),
        Path(__file__).parent.parent.parent / "logs",
        Path(__file__).parent.parent / "logs",
    ]
    logs_dir = None
    for p in possible_paths:
        if p.exists() and p.is_dir():
            logs_dir = p
            break

    if not logs_dir:
        # Fallback to local logs directory relative to this file
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

    status_file = logs_dir / "cron_status.json"

    # 2. Read existing statuses
    data = {}
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    # 3. Update status
    data[job_name] = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "error": error,
    }

    # 4. Write back atomically
    try:
        # Write to temporary file first, then rename to ensure atomicity
        temp_file = status_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file.replace(status_file)
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to write cron status for {job_name}: {e}")


@contextmanager
def monitor_cron_job(job_name: str):
    """
    Context manager to wrap cron script execution and monitor status.
    Catches exceptions, logs tracebacks, and updates status accordingly.
    """
    try:
        # Register job start (optional, but good for tracking hung tasks)
        log_cron_status(job_name, "running")
        yield
        # Register job success
        log_cron_status(job_name, "success")
    except Exception as exc:
        # Log failure traceback
        tb = traceback.format_exc()
        log_cron_status(job_name, "failed", error=tb)
        # Re-raise to preserve exit codes
        raise exc
