import pytest

from backend import config
from backend.api import deps
from backend.domain import LOCAL_USER
from backend.repositories.sqlite_repo import SqliteRepository

# 테스트 중 monkeypatch 로 바뀔 수 있으므로 원래 함수(캐시 포함)를 미리 잡아 둔다.
_CACHED = (deps.get_repo, deps.get_auth)


def _clear_caches():
    for fn in _CACHED:
        fn.cache_clear()


@pytest.fixture(autouse=True)
def isolate_from_env(monkeypatch):
    """로컬 .env 설정(DB_BACKEND=supabase 등)과 무관하게 테스트는 항상 sqlite 모드에서 시작한다.

    supabase 모드가 필요한 테스트는 자기 fixture 에서 다시 바꾼다. 실제 Supabase 에는 접속하지 않는다.
    """
    monkeypatch.setattr(config, "DB_BACKEND", "sqlite")
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
def repo(tmp_path):
    """테스트마다 임시 DB 파일을 쓴다 (실제 todo.db 는 건드리지 않음)."""
    return SqliteRepository(tmp_path / "test.db")


@pytest.fixture
def user():
    return LOCAL_USER
