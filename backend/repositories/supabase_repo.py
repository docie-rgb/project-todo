"""Supabase(PostgreSQL) 저장소 구현. SQLite 저장소와 같은 인터페이스(base.Repository)를 따른다.

DB 접근 방식: Supabase Data API(PostgREST, /rest/v1) 를 HTTP로 호출한다.
  - apikey 헤더        : publishable 키 (어느 프로젝트에 요청하는지 식별)
  - Authorization 헤더 : 로그인한 사용자의 액세스 토큰
DB는 토큰으로 요청자를 알아내 auth.uid() 를 정하고 RLS 정책을 적용한다.

따라서 이 파일은 user_id 로 행을 걸러내지 않으며 user_id 를 보내지도 않는다.
  - 조회 범위 제한  → RLS 정책 (supabase/schema.sql)
  - user_id 채우기   → 컬럼 기본값 auth.uid()
  - 남의 프로젝트 연결 차단 → 복합 외래키
RLS 를 우회하는 secret/service_role 키는 사용하지 않는다.
"""

import uuid

import httpx

from backend import domain
from backend.domain import CurrentUser
from backend.repositories.base import TODO_UPDATABLE_FIELDS, TodoSort

_PROJECT_COLUMNS = "id,name,created_at,todos(is_done)"  # todos(...) = 외래키로 연결된 할 일을 함께 가져옴
_TODO_COLUMNS = "id,project_id,title,is_done,due_date,created_at"

_TODO_ORDER = {
    "due": "due_date.asc.nullslast,created_at.asc,id.asc",  # 마감일 없는 할 일은 뒤로
    "created": "created_at.asc,id.asc",
}

# PostgreSQL 오류 코드
_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"
_RLS_OR_PRIVILEGE_VIOLATION = "42501"


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _project(row: dict) -> dict:
    """임베드된 todos 목록으로 전체/완료 개수를 계산한다."""
    todos = row.get("todos") or []
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "total_count": len(todos),
        "done_count": sum(1 for t in todos if t["is_done"]),
    }


def _counts(rows: list[dict]) -> dict:
    return {"total_count": len(rows), "done_count": sum(1 for r in rows if r["is_done"])}


class SupabaseRepository:
    def __init__(self, url: str, publishable_key: str, transport: httpx.BaseTransport | None = None):
        if not url or not publishable_key:
            raise RuntimeError("supabase 모드에는 SUPABASE_URL 과 SUPABASE_PUBLISHABLE_KEY 가 필요합니다 (.env).")
        self._key = publishable_key
        # 연결 재사용용 클라이언트. 사용자 토큰은 클라이언트에 저장하지 않고 요청마다 헤더로 넣는다
        # (여러 사용자의 요청이 같은 클라이언트를 공유해도 세션이 섞이지 않게).
        self._http = httpx.Client(base_url=f"{url}/rest/v1", timeout=10.0, transport=transport)

    # ---------- HTTP 공통 ----------

    def _request(
        self,
        user: CurrentUser,
        method: str,
        table: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        on_fk_violation: domain.DomainError | None = None,
    ) -> list[dict]:
        if not user.access_token:
            raise domain.Unauthorized()
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {user.access_token}",
        }
        if method in ("POST", "PATCH", "DELETE"):
            headers["Prefer"] = "return=representation"  # 변경된 행을 응답으로 돌려받는다 (0건이면 [])
        try:
            res = self._http.request(method, f"/{table}", params=params, json=json, headers=headers)
        except httpx.HTTPError:
            raise domain.StorageUnavailable() from None

        if res.is_success:
            return res.json() if res.content else []

        body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
        code = body.get("code") if isinstance(body, dict) else None
        if res.status_code == 401:
            raise domain.Unauthorized("로그인이 만료되었습니다. 다시 로그인하세요.")
        if code == _UNIQUE_VIOLATION:
            raise domain.DuplicateProjectName((json or {}).get("name", ""))
        if code == _FOREIGN_KEY_VIOLATION and on_fk_violation is not None:
            raise on_fk_violation
        if code == _RLS_OR_PRIVILEGE_VIOLATION or res.status_code == 403:
            raise domain.PermissionDenied()
        # 그 밖의 오류는 내부 정보(SQL 등)를 사용자에게 노출하지 않는다.
        raise domain.StorageUnavailable(f"데이터 저장소 오류 (HTTP {res.status_code})")

    # ---------- projects ----------

    def list_projects(self, user: CurrentUser) -> dict:
        projects = self._request(
            user, "GET", "projects", params={"select": _PROJECT_COLUMNS, "order": "created_at.asc,id.asc"}
        )
        unassigned = self._request(
            user, "GET", "todos", params={"select": "is_done", "project_id": "is.null"}
        )
        return {"projects": [_project(p) for p in projects], "unassigned": _counts(unassigned)}

    def create_project(self, user: CurrentUser, name: str) -> dict:
        name = domain.clean_project_name(name)
        rows = self._request(
            user, "POST", "projects", params={"select": _PROJECT_COLUMNS}, json={"name": name}
        )
        return _project(rows[0])

    def rename_project(self, user: CurrentUser, project_id: str, name: str) -> dict:
        name = domain.clean_project_name(name)
        if not _is_uuid(project_id):
            raise domain.NotFound("프로젝트를 찾을 수 없습니다.")
        rows = self._request(
            user,
            "PATCH",
            "projects",
            params={"id": f"eq.{project_id}", "select": _PROJECT_COLUMNS},
            json={"name": name},
        )
        if not rows:  # 없는 프로젝트이거나 RLS 때문에 보이지 않는(남의) 프로젝트
            raise domain.NotFound("프로젝트를 찾을 수 없습니다.")
        return _project(rows[0])

    def delete_project(self, user: CurrentUser, project_id: str) -> None:
        # 소속 할 일은 외래키의 ON DELETE SET NULL (project_id) 가 미분류로 바꾼다.
        if not _is_uuid(project_id):
            raise domain.NotFound("프로젝트를 찾을 수 없습니다.")
        rows = self._request(user, "DELETE", "projects", params={"id": f"eq.{project_id}", "select": "id"})
        if not rows:
            raise domain.NotFound("프로젝트를 찾을 수 없습니다.")

    # ---------- todos ----------

    def list_todos(self, user: CurrentUser, project_id: str | None, sort: TodoSort = "created") -> list[dict]:
        if project_id is None:
            project_filter = "is.null"
        elif _is_uuid(project_id):
            project_filter = f"eq.{project_id}"
        else:
            return []  # SQLite 와 같게: 없는 프로젝트의 할 일은 0건
        return self._request(
            user,
            "GET",
            "todos",
            params={"select": _TODO_COLUMNS, "project_id": project_filter, "order": _TODO_ORDER[sort]},
        )

    def create_todo(
        self, user: CurrentUser, title: str, project_id: str | None = None, due_date: str | None = None
    ) -> dict:
        title = domain.clean_title(title)
        due_date = domain.clean_due_date(due_date)
        if project_id is not None and not _is_uuid(project_id):
            raise domain.InvalidProject()
        rows = self._request(
            user,
            "POST",
            "todos",
            params={"select": _TODO_COLUMNS},
            json={"title": title, "project_id": project_id, "due_date": due_date},  # user_id 는 보내지 않는다
            on_fk_violation=domain.InvalidProject(),
        )
        return rows[0]

    def update_todo(self, user: CurrentUser, todo_id: str, changes: dict) -> dict:
        unknown = set(changes) - TODO_UPDATABLE_FIELDS
        if unknown:
            raise domain.ValidationError(f"수정할 수 없는 필드: {', '.join(sorted(unknown))}")

        values = {}
        if "title" in changes:
            values["title"] = domain.clean_title(changes["title"])
        if "due_date" in changes:
            values["due_date"] = domain.clean_due_date(changes["due_date"])
        if "is_done" in changes:
            if not isinstance(changes["is_done"], bool):
                raise domain.ValidationError("완료 여부는 true/false 여야 합니다.")
            values["is_done"] = changes["is_done"]
        if "project_id" in changes:
            if changes["project_id"] is not None and not _is_uuid(changes["project_id"]):
                raise domain.InvalidProject()
            values["project_id"] = changes["project_id"]

        if not _is_uuid(todo_id):
            raise domain.NotFound("할 일을 찾을 수 없습니다.")
        params = {"id": f"eq.{todo_id}", "select": _TODO_COLUMNS}
        if values:
            rows = self._request(
                user, "PATCH", "todos", params=params, json=values, on_fk_violation=domain.InvalidProject()
            )
        else:
            rows = self._request(user, "GET", "todos", params=params)
        if not rows:  # 없는 할 일이거나 RLS 때문에 보이지 않는(남의) 할 일
            raise domain.NotFound("할 일을 찾을 수 없습니다.")
        return rows[0]

    def delete_todo(self, user: CurrentUser, todo_id: str) -> None:
        if not _is_uuid(todo_id):
            raise domain.NotFound("할 일을 찾을 수 없습니다.")
        rows = self._request(user, "DELETE", "todos", params={"id": f"eq.{todo_id}", "select": "id"})
        if not rows:
            raise domain.NotFound("할 일을 찾을 수 없습니다.")
