import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_repo
from backend.main import app


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_repo] = lambda: repo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _project(client, name="Work"):
    r = client.post("/api/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _todo(client, **body):
    r = client.post("/api/todos", json={"title": "task", **body})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_frontend(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/").status_code == 200
    # 백엔드 코드·DB 파일은 정적 경로로 노출되지 않는다
    assert client.get("/backend/config.py").status_code == 404
    assert client.get("/todo.db").status_code == 404


def test_project_crud(client):
    p = _project(client, " Work ")
    assert p["name"] == "Work"

    r = client.patch(f"/api/projects/{p['id']}", json={"name": "Office"})
    assert r.status_code == 200 and r.json()["name"] == "Office"

    listed = client.get("/api/projects").json()
    assert [x["name"] for x in listed["projects"]] == ["Office"]
    assert listed["unassigned"] == {"total_count": 0, "done_count": 0}

    assert client.delete(f"/api/projects/{p['id']}").status_code == 204
    assert client.get("/api/projects").json()["projects"] == []


def test_project_errors(client):
    _project(client, "Work")
    r = client.post("/api/projects", json={"name": " work "})
    assert r.status_code == 409 and "이미 같은 이름" in r.json()["detail"]
    assert client.post("/api/projects", json={"name": "  "}).status_code == 400
    assert client.post("/api/projects", json={"name": "X", "user_id": "u"}).status_code == 422
    missing = str(uuid.uuid4())
    assert client.patch(f"/api/projects/{missing}", json={"name": "Y"}).status_code == 404
    assert client.delete(f"/api/projects/{missing}").status_code == 404


def test_todo_crud_and_filters(client):
    p = _project(client)
    t = _todo(client, title="in project", project_id=p["id"], due_date="2026-11-05")
    loose = _todo(client, title="loose")

    assert [x["title"] for x in client.get(f"/api/todos?project={p['id']}").json()] == ["in project"]
    assert [x["title"] for x in client.get("/api/todos?project=unassigned").json()] == ["loose"]

    r = client.patch(f"/api/todos/{t['id']}", json={"title": "renamed", "is_done": True})
    body = r.json()
    assert (body["title"], body["is_done"], body["due_date"]) == ("renamed", True, "2026-11-05")

    # 미분류로 변경 + 마감일 제거 (null 전송)
    body = client.patch(f"/api/todos/{t['id']}", json={"project_id": None, "due_date": None}).json()
    assert (body["project_id"], body["due_date"], body["title"]) == (None, None, "renamed")

    # 미분류 → 프로젝트 배정
    assert client.patch(f"/api/todos/{loose['id']}", json={"project_id": p["id"]}).json()["project_id"] == p["id"]

    assert client.delete(f"/api/todos/{loose['id']}").status_code == 204
    assert client.delete(f"/api/todos/{loose['id']}").status_code == 404


def test_todo_errors(client):
    assert client.post("/api/todos", json={"title": " "}).status_code == 400
    assert client.post("/api/todos", json={"title": "x", "due_date": "2026-13-01"}).status_code == 400
    assert client.post("/api/todos", json={"title": "x", "project_id": str(uuid.uuid4())}).status_code == 422
    assert client.post("/api/todos", json={"title": "x", "user_id": "u"}).status_code == 422
    t = _todo(client)
    assert client.patch(f"/api/todos/{t['id']}", json={"is_done": "maybe"}).status_code == 422
    assert client.get("/api/todos").status_code == 422  # project 파라미터 필수
    assert client.get("/api/todos?project=unassigned&sort=bogus").status_code == 422


def test_delete_project_keeps_todos_as_unassigned(client):
    p = _project(client)
    _todo(client, title="survivor", project_id=p["id"])
    client.delete(f"/api/projects/{p['id']}")
    todos = client.get("/api/todos?project=unassigned").json()
    assert [(x["title"], x["project_id"]) for x in todos] == [("survivor", None)]
    assert client.get("/api/projects").json()["unassigned"]["total_count"] == 1


def test_sort_by_due(client):
    _todo(client, title="none")
    _todo(client, title="late", due_date="2026-12-01")
    _todo(client, title="soon", due_date="2026-11-01")
    titles = [x["title"] for x in client.get("/api/todos?project=unassigned&sort=due").json()]
    assert titles == ["soon", "late", "none"]
