"""Periodic cleanup for temporary upload/output session folders.

This complements the in-app cleanup and removes nested session directories
that are older than the configured retention period.
"""

import os
import shutil
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
RETENTION_SECONDS = int(os.environ.get("FILE_RETENTION_SECONDS", "1800"))
CHECK_INTERVAL_SECONDS = int(os.environ.get("CLEANUP_CHECK_SECONDS", "600"))


def remove_old_entries(root_dir: str) -> None:
    if not os.path.isdir(root_dir):
        return

    now = time.time()
    for name in os.listdir(root_dir):
        path = os.path.join(root_dir, name)
        try:
            age = now - os.path.getmtime(path)
            if age <= RETENTION_SECONDS:
                continue

            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                os.remove(path)
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f"Cleanup warning for {path}: {exc}", flush=True)


def main() -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    while True:
        remove_old_entries(UPLOAD_DIR)
        remove_old_entries(OUTPUT_DIR)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
