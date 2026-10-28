"""Configuration and environment settings for Loyalty Ledger Intelligence Platform."""
from pathlib import Path
import os
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
REPORTS_DIR = BASE_DIR / "reports"
DOCS_DIR = BASE_DIR / "docs"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "starter").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "full").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "ground_truth").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "manifests").mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
(EXPORTS_DIR / "csv").mkdir(parents=True, exist_ok=True)
(EXPORTS_DIR / "json").mkdir(parents=True, exist_ok=True)
(EXPORTS_DIR / "sql").mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/loyalty_ledger.db")
DEFAULT_SEED = int(os.getenv("DEFAULT_SEED", "20261022"))
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "UTC")
SIMULATION_START = os.getenv("SIMULATION_START_DATE", "2026-01-01T00:00:00Z")
SIMULATION_END = os.getenv("SIMULATION_END_DATE", "2026-10-22T23:59:59Z")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
