"""라우터가 주입받는 의존성: 저장소와 현재 사용자."""

from functools import lru_cache

from backend import config
from backend.domain import LOCAL_USER, CurrentUser
from backend.repositories.base import Repository


@lru_cache
def get_repo() -> Repository:
    """DB_BACKEND 설정에 따라 저장소 구현을 고른다. Step 3에서 supabase 분기를 추가한다."""
    if config.DB_BACKEND == "sqlite":
        from backend.repositories.sqlite_repo import SqliteRepository

        return SqliteRepository(config.DB_PATH)
    raise RuntimeError(f"지원하지 않는 DB_BACKEND: {config.DB_BACKEND}")


def get_current_user() -> CurrentUser:
    """로컬 모드는 로그인이 없으므로 항상 단일 로컬 사용자.

    Step 3에서는 Authorization 헤더의 Supabase JWT를 검증해 사용자 ID를 돌려주도록 바꾼다.
    """
    return LOCAL_USER
