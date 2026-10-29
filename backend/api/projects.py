from fastapi import APIRouter, Depends, Response

from backend.api.deps import get_current_user, get_repo
from backend.domain import CurrentUser
from backend.repositories.base import Repository
from backend.schemas import Project, ProjectIn, ProjectList

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectList)
def list_projects(repo: Repository = Depends(get_repo), user: CurrentUser = Depends(get_current_user)):
    return repo.list_projects(user)


@router.post("", response_model=Project, status_code=201)
def create_project(
    body: ProjectIn, repo: Repository = Depends(get_repo), user: CurrentUser = Depends(get_current_user)
):
    return repo.create_project(user, body.name)


@router.patch("/{project_id}", response_model=Project)
def rename_project(
    project_id: str,
    body: ProjectIn,
    repo: Repository = Depends(get_repo),
    user: CurrentUser = Depends(get_current_user),
):
    return repo.rename_project(user, project_id, body.name)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str, repo: Repository = Depends(get_repo), user: CurrentUser = Depends(get_current_user)
):
    repo.delete_project(user, project_id)
    return Response(status_code=204)
