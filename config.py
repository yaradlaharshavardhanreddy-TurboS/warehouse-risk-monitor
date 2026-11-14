"""Application configuration."""

import os

from pathlib import Path
from app.database.database import DATABASE_PATH

PROJECT_ROOT = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "warehouse-risk-monitor-development-key"
    )

    DATABASE_PATH = DATABASE_PATH

    JSON_SORT_KEYS = False
    TESTING = False
