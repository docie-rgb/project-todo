"""SupabaseRepository 단위 테스트 — 실제 Supabase 없이 HTTP 요청/응답을 가짜(MockTransport)로 대신한다.

이 테스트가 증명하는 것:
  - DB에 보내는 요청의 모양 (헤더에 publishable 키와 사용자 토큰, 본문에 user_id 없음, 필터·정렬 파라미터)
  - DB 응답(오류 코드, 0건)을 도메인 오류로 바꾸는 규칙
이 테스트가 증명하지 못하는 것:
  - RLS 정책이 실제로 남의 행을 막는지 → 실제 Supabase + 계정 A/B 로 B4에서 검증한다.
"""

import json
import uuid

import httpx
import pytest

from backend import domain
from backend.domain import CurrentUser
from backend.repositories.supabase_repo import SupabaseRepository

KEY = "sb_publishable_test"
TOKEN = "user-access-token-for-test"
USER = CurrentUser(id=str(uuid.uuid4()), email="a@example.com", access_token=TOKEN)
PID = str(uuid.uuid4())
TID = str(uuid.uuid4())


class FakePostgrest:
    """요청을 기록하고, 미리 정한 응답을 순서대로 돌려준다."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return httpx.Response(status, json=body)


def make_repo(*responses):
    fake = FakePostgrest(*responses)
    return SupabaseRepository("https://example.supabase.co", KEY, transport=httpx.MockTransport(fake)), fake


def body_of(request: httpx.Request) -> dict:
    return json.loads(request.content) if request.content else {}


# ---------- 요청 모양 ----------


def test_requests_carry_publishable_key_and_user_token():
    repo, fake = make_repo((200, []), (200, []))
    repo.list_projects(USER)
    for req in fake.requests:
        assert req.headers["apikey"] == KEY
        assert req.headers["authorization"] == f"Bearer {TOKEN}"  # RLS가 이 사용자로 적용되는 근거
        assert req.url.path.startswith("/rest/v1/")


def test_create_never_sends_user_id():
    row = {"id": PID, "name": "Work", "created_at": "2026-10-29T00:00:00+00:00", "todos": []}
    todo = {"id": TID, "project_id": None, "title": "t", "is_done": False, "due_date": None, "created_at": "x"}
    repo, fake = make_repo((201, [row]), (201, [todo]))
    repo.create_project(USER, "  Work ")
    repo.create_todo(USER, "t")
    assert body_of(fake.requests[0]) == {"name": "Work"}  # trim 후 이름만
    assert "user_id" not in body_of(fake.requests[1])  # user_id 는 DB 기본값 auth.uid() 가 채운다
    assert all(r.headers["prefer"] == "return=representation" for r in fake.requests)


def test_no_token_means_no_request():
    repo, fake = make_repo()
    with pytest.raises(domain.Unauthorized):
        repo.list_projects(CurrentUser(id=None))
    assert fake.requests == []


def test_user_repr_hides_token():
    assert TOKEN not in repr(USER)


# ---------- 조회 ----------


def test_list_projects_counts_from_embedded_todos():
    projects = [
        {"id": PID, "name": "Work", "created_at": "c", "todos": [{"is_done": True}, {"is_done": False}]},
    ]
    repo, fake = make_repo((200, projects), (200, [{"is_done": False}]))
    result = repo.list_projects(USER)
    assert result["projects"][0] | {} == {
        "id": PID, "name": "Work", "created_at": "c", "total_count": 2, "done_count": 1,
    }
    assert result["unassigned"] == {"total_count": 1, "done_count": 0}
    assert fake.requests[1].url.params["project_id"] == "is.null"  # 미분류 = project_id IS NULL


def test_list_todos_filters_and_sort():
    repo, fake = make_repo((200, []), (200, []))
    repo.list_todos(USER, PID, sort="due")
    repo.list_todos(USER, None)
    first, second = (r.url.params for r in fake.requests)
    assert first["project_id"] == f"eq.{PID}"
    assert first["order"] == "due_date.asc.nullslast,created_at.asc,id.asc"
    assert second["project_id"] == "is.null"
    assert second["order"] == "created_at.asc,id.asc"


def test_list_todos_with_non_uuid_project_returns_empty_without_request():
    repo, fake = make_repo()
    assert repo.list_todos(USER, "not-a-uuid") == []
    assert fake.requests == []


# ---------- 수정 ----------


def test_update_todo_sends_only_changed_fields():
    todo = {"id": TID, "project_id": None, "title": "t", "is_done": True, "due_date": None, "created_at": "x"}
    repo, fake = make_repo((200, [todo]))
    repo.update_todo(USER, TID, {"is_done": True, "project_id": None})
    req = fake.requests[0]
    assert req.method == "PATCH"
    assert req.url.params["id"] == f"eq.{TID}"
    assert body_of(req) == {"is_done": True, "project_id": None}  # null = 미분류로 변경


# ---------- DB 응답 → 도메인 오류 ----------


def test_zero_rows_on_update_or_delete_is_not_found():
    # RLS 로 보이지 않는 남의 행을 수정/삭제하면 DB는 오류 없이 0건([])을 돌려준다.
    repo, _ = make_repo((200, []), (200, []), (200, []))
    with pytest.raises(domain.NotFound):
        repo.update_todo(USER, TID, {"title": "hack"})
    with pytest.raises(domain.NotFound):
        repo.delete_todo(USER, TID)
    with pytest.raises(domain.NotFound):
        repo.rename_project(USER, PID, "x")


def test_unique_violation_is_duplicate_name():
    repo, _ = make_repo((409, {"code": "23505", "message": "duplicate key value"}))
    with pytest.raises(domain.DuplicateProjectName):
        repo.create_project(USER, "work")


def test_foreign_key_violation_is_invalid_project():
    # 남의 프로젝트 / 없는 프로젝트에 연결 → 복합 외래키 위반
    repo, _ = make_repo((409, {"code": "23503"}), (409, {"code": "23503"}))
    with pytest.raises(domain.InvalidProject):
        repo.create_todo(USER, "t", project_id=PID)
    with pytest.raises(domain.InvalidProject):
        repo.update_todo(USER, TID, {"project_id": PID})


def test_rls_violation_is_permission_denied():
    repo, _ = make_repo((403, {"code": "42501", "message": "new row violates row-level security policy"}))
    with pytest.raises(domain.PermissionDenied):
        repo.create_todo(USER, "t")


def test_expired_token_is_unauthorized():
    repo, _ = make_repo((401, {"code": "PGRST303", "message": "JWT expired"}))
    with pytest.raises(domain.Unauthorized):
        repo.list_todos(USER, None)


def test_unexpected_error_hides_internal_message():
    repo, _ = make_repo((500, {"code": "XX000", "message": "internal SQL detail"}))
    with pytest.raises(domain.StorageUnavailable) as exc:
        repo.list_todos(USER, None)
    assert "SQL" not in str(exc.value)


def test_network_error_is_storage_unavailable():
    def boom(request):
        raise httpx.ConnectError("offline")

    repo = SupabaseRepository("https://example.supabase.co", KEY, transport=httpx.MockTransport(boom))
    with pytest.raises(domain.StorageUnavailable):
        repo.list_todos(USER, None)


def test_invalid_ids_rejected_without_request():
    repo, fake = make_repo()
    with pytest.raises(domain.NotFound):
        repo.delete_todo(USER, "x")
    with pytest.raises(domain.NotFound):
        repo.delete_project(USER, "x")
    with pytest.raises(domain.InvalidProject):
        repo.create_todo(USER, "t", project_id="x")
    assert fake.requests == []


def test_same_validation_rules_as_sqlite():
    repo, fake = make_repo()
    with pytest.raises(domain.ValidationError):
        repo.create_project(USER, "   ")
    with pytest.raises(domain.ValidationError):
        repo.create_todo(USER, "t", due_date="2026-02-30")
    with pytest.raises(domain.ValidationError):
        repo.update_todo(USER, TID, {"user_id": "someone"})
    assert fake.requests == []


def test_missing_config_fails_fast():
    with pytest.raises(RuntimeError):
        SupabaseRepository("", "")
