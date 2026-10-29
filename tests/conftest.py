import pytest

from backend.domain import LOCAL_USER
from backend.repositories.sqlite_repo import SqliteRepository


@pytest.fixture
def repo(tmp_path):
    """테스트마다 임시 DB 파일을 쓴다 (실제 todo.db 는 건드리지 않음)."""
    return SqliteRepository(tmp_path / "test.db")


@pytest.fixture
def user():
    return LOCAL_USER
