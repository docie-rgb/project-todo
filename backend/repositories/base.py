"""저장소 인터페이스. API 계층은 이 인터페이스에만 의존한다.

반환값은 JSON으로 바로 응답할 수 있는 dict 이며, 자료형은 DB 종류와 무관하게 같다.
  project: {id, name, created_at, total_count, done_count}
  todo:    {id, project_id (None=미분류), title, is_done (bool), due_date (YYYY-MM-DD|None), created_at}
"""

from typing import Literal, Protocol

from backend.domain import CurrentUser

TodoSort = Literal["due", "created"]

# update_todo 에 넘길 수 있는 필드
TODO_UPDATABLE_FIELDS = frozenset({"title", "is_done", "due_date", "project_id"})


class Repository(Protocol):
    # projects
    def list_projects(self, user: CurrentUser) -> dict:
        """{"projects": [project, ...], "unassigned": {"total_count", "done_count"}}"""

    def create_project(self, user: CurrentUser, name: str) -> dict: ...

    def rename_project(self, user: CurrentUser, project_id: str, name: str) -> dict: ...

    def delete_project(self, user: CurrentUser, project_id: str) -> None:
        """소속 할 일은 삭제하지 않고 미분류(project_id=None)로 바뀐다."""

    # todos
    def list_todos(self, user: CurrentUser, project_id: str | None, sort: TodoSort = "created") -> list[dict]:
        """project_id=None 이면 미분류 할 일."""

    def create_todo(
        self, user: CurrentUser, title: str, project_id: str | None = None, due_date: str | None = None
    ) -> dict: ...

    def update_todo(self, user: CurrentUser, todo_id: str, changes: dict) -> dict:
        """changes 에 포함된 필드만 바꾼다 (TODO_UPDATABLE_FIELDS)."""

    def delete_todo(self, user: CurrentUser, todo_id: str) -> None: ...
