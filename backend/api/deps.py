"""라우터가 주입받는 의존성: 저장소, 인증 클라이언트, 현재 사용자."""

from functools import lru_cache

from fastapi import Request

from backend import config, domain
from backend.api.cookies import ACCESS_COOKIE
from backend.domain import LOCAL_USER, CurrentUser
from backend.repositories.base import Repository
from backend.supabase_auth import SupabaseAuth


def auth_required() -> bool:
    return config.DB_BACKEND == "supabase"


@lru_cache
def get_repo() -> Repository:
    """DB_BACKEND 설정에 따라 저장소 구현을 고른다. 선택되지 않은 쪽은 만들지 않는다."""
    if config.DB_BACKEND == "sqlite":
        from backend.repositories.sqlite_repo import SqliteRepository

        return SqliteRepository(config.DB_PATH)
    if config.DB_BACKEND == "supabase":
        from backend.repositories.supabase_repo import SupabaseRepository

        return SupabaseRepository(config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY)
    raise RuntimeError(f"지원하지 않는 DB_BACKEND: {config.DB_BACKEND}")


@lru_cache
def get_auth() -> SupabaseAuth:
    return SupabaseAuth(config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY)


def get_current_user(request: Request) -> CurrentUser:
    """요청한 사용자를 결정한다.

    - sqlite 모드: 로그인이 없으므로 항상 단일 로컬 사용자.
    - supabase 모드: pt_access 쿠키의 토큰을 Supabase Auth 에 검증받는다.
      검증된 토큰만 저장소로 넘어가 DB 요청에 실리고, DB는 그 토큰으로 RLS 를 적용한다.
      클라이언트가 보낸 user_id 같은 값은 어디에서도 사용하지 않는다.
    """
    if not auth_required():
        return LOCAL_USER
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise domain.Unauthorized()
    return get_auth().get_user(token)
