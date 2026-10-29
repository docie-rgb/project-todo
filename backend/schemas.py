"""API 요청/응답 모델. 입력에 정의되지 않은 필드(user_id 등)가 오면 422로 거부한다."""

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectIn(_Input):
    name: str


class TodoCreate(_Input):
    title: str
    project_id: str | None = None  # None = 미분류
    due_date: str | None = None  # YYYY-MM-DD


class TodoUpdate(_Input):
    """보낸 필드만 수정한다. project_id/due_date 에 null 을 보내면 미분류/마감일 제거."""

    title: str | None = None
    is_done: bool | None = None
    due_date: str | None = None
    project_id: str | None = None


class Project(BaseModel):
    id: str
    name: str
    created_at: str
    total_count: int
    done_count: int


class Counts(BaseModel):
    total_count: int
    done_count: int


class ProjectList(BaseModel):
    projects: list[Project]
    unassigned: Counts


class Todo(BaseModel):
    id: str
    project_id: str | None
    title: str
    is_done: bool
    due_date: str | None
    created_at: str
