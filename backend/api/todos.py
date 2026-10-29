from fastapi import APIRouter, Depends, Query, Response

from backend.api.deps import get_current_user, get_repo
from backend.domain import CurrentUser
from backend.repositories.base import Repository, TodoSort
from backend.schemas import Todo, TodoCreate, TodoUpdate

router = APIRouter(prefix="/api/todos", tags=["todos"])

UNASSIGNED = "unassigned"


@router.get("", response_model=list[Todo])
def list_todos(
    project: str = Query(..., description=f"프로젝트 ID 또는 '{UNASSIGNED}'(미분류)"),
    sort: TodoSort = "created",
    repo: Repository = Depends(get_repo),
    user: CurrentUser = Depends(get_current_user),
):
    return repo.list_todos(user, None if project == UNASSIGNED else project, sort)


@router.post("", response_model=Todo, status_code=201)
def create_todo(
    body: TodoCreate, repo: Repository = Depends(get_repo), user: CurrentUser = Depends(get_current_user)
):
    return repo.create_todo(user, body.title, body.project_id, body.due_date)


@router.patch("/{todo_id}", response_model=Todo)
def update_todo(
    todo_id: str,
    body: TodoUpdate,
    repo: Repository = Depends(get_repo),
    user: CurrentUser = Depends(get_current_user),
):
    # exclude_unset: 보내지 않은 필드는 그대로 두고, null 로 보낸 필드만 비운다.
    return repo.update_todo(user, todo_id, body.model_dump(exclude_unset=True))


@router.delete("/{todo_id}", status_code=204)
def delete_todo(todo_id: str, repo: Repository = Depends(get_repo), user: CurrentUser = Depends(get_current_user)):
    repo.delete_todo(user, todo_id)
    return Response(status_code=204)
