"""DB 종류와 무관한 업무 규칙: 현재 사용자, 입력 정규화, 도메인 오류.

SQLite·PostgreSQL 저장소가 모두 이 규칙을 공유하므로, 저장소를 바꿔도 동작이 같다.
"""

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class CurrentUser:
    """요청한 사용자. 로컬 모드는 로그인이 없으므로 id=None(단일 사용자).

    Supabase 모드에서는 백엔드가 검증한 로그인 정보를 담는다.
    access_token 은 DB 요청에 그대로 실어 보내 RLS 가 이 사용자로 적용되게 한다.
    (repr=False: 로그나 오류 메시지에 토큰이 찍히지 않게 한다)
    클라이언트가 보낸 user_id 는 절대 사용하지 않는다.
    """

    id: str | None
    email: str | None = None
    access_token: str | None = field(default=None, repr=False)


LOCAL_USER = CurrentUser(id=None)


class DomainError(Exception):
    """API 계층이 HTTP 상태코드로 바꿔 응답하는 오류의 기반 클래스."""


class ValidationError(DomainError):
    pass


class NotFound(DomainError):
    pass


class DuplicateProjectName(DomainError):
    def __init__(self, name: str):
        super().__init__(f"이미 같은 이름의 프로젝트가 있습니다: {name}")


class InvalidProject(DomainError):
    def __init__(self):
        super().__init__("존재하지 않는 프로젝트입니다.")


class Unauthorized(DomainError):
    def __init__(self, message: str = "로그인이 필요합니다."):
        super().__init__(message)


class PermissionDenied(DomainError):
    def __init__(self, message: str = "권한이 없습니다."):
        super().__init__(message)


class StorageUnavailable(DomainError):
    def __init__(self, message: str = "데이터 저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요."):
        super().__init__(message)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_project_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValidationError("프로젝트 이름을 입력하세요.")
    return cleaned


def clean_title(title: str) -> str:
    cleaned = (title or "").strip()
    if not cleaned:
        raise ValidationError("할 일 제목을 입력하세요.")
    return cleaned


def clean_due_date(value: str | None) -> str | None:
    """마감일은 선택사항. 빈 값은 NULL, 그 외에는 실제 존재하는 YYYY-MM-DD 날짜만 허용."""
    if value is None or value == "":
        return None
    if not _DATE_RE.match(value):
        raise ValidationError("마감일은 YYYY-MM-DD 형식이어야 합니다.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValidationError("존재하지 않는 날짜입니다.") from None
    return value
