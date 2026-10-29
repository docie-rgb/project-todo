"""환경변수(.env) 기반 설정. 비밀값은 코드에 두지 않는다."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

load_dotenv(PROJECT_ROOT / ".env")

DB_BACKEND = os.getenv("DB_BACKEND", "sqlite")


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


DB_PATH = _resolve(os.getenv("DB_PATH", "todo.db"))
