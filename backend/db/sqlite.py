"""SQLite 연결과 스키마 초기화. SQLite를 직접 다루는 코드는 이 파일과 sqlite_repo.py 뿐이다."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


@contextmanager
def connect(db_path: Path):
    """요청 단위 연결. 정상 종료 시 커밋, 예외 시 롤백하고 항상 닫는다."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # SQLite는 연결마다 켜야 FK(ON DELETE SET NULL 포함)가 동작한다.
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """todo.db 가 없으면 만들고, 테이블·인덱스가 없으면 생성한다 (기존 데이터는 유지)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
