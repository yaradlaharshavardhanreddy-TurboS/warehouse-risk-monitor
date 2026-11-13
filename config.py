"""Application configuration."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "warehouse-risk-monitor-development-key"
    )

    DATABASE_PATH = Path(
        os.getenv(
            "WAREHOUSE_DATABASE_PATH",
            str(PROJECT_ROOT / "data" / "warehouse_monitor.db")
        )
    )

    JSON_SORT_KEYS = False
    TESTING = False
