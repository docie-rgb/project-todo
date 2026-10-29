import sqlite3
import uuid

import pytest

from backend import domain


# ---------- projects ----------


def test_create_and_list_project(repo, user):
    p = repo.create_project(user, "  Work  ")
    assert p["name"] == "Work"  # 앞뒤 공백 제거
    assert len(p["id"]) == 36 and uuid.UUID(p["id"]).version == 4
    assert p["total_count"] == 0 and p["done_count"] == 0
    listed = repo.list_projects(user)
    assert [x["name"] for x in listed["projects"]] == ["Work"]
    assert listed["unassigned"] == {"total_count": 0, "done_count": 0}


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_empty_project_name_rejected(repo, user, name):
    with pytest.raises(domain.ValidationError):
        repo.create_project(user, name)


@pytest.mark.parametrize("dup", ["Work", "work", "WORK", "  work  "])
def test_duplicate_project_name_case_and_space_insensitive(repo, user, dup):
    repo.create_project(user, "Work")
    with pytest.raises(domain.DuplicateProjectName):
        repo.create_project(user, dup)


def test_korean_and_distinct_names_allowed(repo, user):
    repo.create_project(user, "업무")
    repo.create_project(user, "업무 2")
    repo.create_project(user, "Workshop")
    assert len(repo.list_projects(user)["projects"]) == 3


def test_rename_project(repo, user):
    p = repo.create_project(user, "Work")
    assert repo.rename_project(user, p["id"], " Office ")["name"] == "Office"
    # 자기 자신의 대소문자만 바꾸는 것은 허용
    assert repo.rename_project(user, p["id"], "OFFICE")["name"] == "OFFICE"


def test_rename_to_existing_name_rejected(repo, user):
    repo.create_project(user, "Work")
    p2 = repo.create_project(user, "Home")
    with pytest.raises(domain.DuplicateProjectName):
        repo.rename_project(user, p2["id"], "wORK")


def test_rename_or_delete_missing_project(repo, user):
    missing = str(uuid.uuid4())
    with pytest.raises(domain.NotFound):
        repo.rename_project(user, missing, "X")
    with pytest.raises(domain.NotFound):
        repo.delete_project(user, missing)


def test_delete_project_moves_todos_to_unassigned(repo, user):
    p = repo.create_project(user, "Work")
    t1 = repo.create_todo(user, "a", project_id=p["id"])
    repo.create_todo(user, "b", project_id=p["id"])
    repo.update_todo(user, t1["id"], {"is_done": True})

    repo.delete_project(user, p["id"])

    assert repo.list_projects(user)["projects"] == []
    unassigned = repo.list_todos(user, None)
    assert [t["title"] for t in unassigned] == ["a", "b"]  # 삭제되지 않고 남음
    assert all(t["project_id"] is None for t in unassigned)
    assert repo.list_projects(user)["unassigned"] == {"total_count": 2, "done_count": 1}


def test_project_counts(repo, user):
    p = repo.create_project(user, "Work")
    for title in ("a", "b", "c"):
        repo.create_todo(user, title, project_id=p["id"])
    first = repo.list_todos(user, p["id"])[0]
    repo.update_todo(user, first["id"], {"is_done": True})
    repo.create_todo(user, "loose")

    listed = repo.list_projects(user)
    assert (listed["projects"][0]["total_count"], listed["projects"][0]["done_count"]) == (3, 1)
    assert listed["unassigned"] == {"total_count": 1, "done_count": 0}


# ---------- todos ----------


def test_create_todo_defaults(repo, user):
    t = repo.create_todo(user, "  write PRD ")
    assert t["title"] == "write PRD"
    assert t["project_id"] is None  # 미분류
    assert t["is_done"] is False
    assert t["due_date"] is None
    assert uuid.UUID(t["id"]).version == 4


def test_todo_filtering_by_project_and_unassigned(repo, user):
    p1 = repo.create_project(user, "P1")
    p2 = repo.create_project(user, "P2")
    repo.create_todo(user, "in p1", project_id=p1["id"])
    repo.create_todo(user, "in p2", project_id=p2["id"])
    repo.create_todo(user, "loose")
    assert [t["title"] for t in repo.list_todos(user, p1["id"])] == ["in p1"]
    assert [t["title"] for t in repo.list_todos(user, p2["id"])] == ["in p2"]
    assert [t["title"] for t in repo.list_todos(user, None)] == ["loose"]


def test_create_todo_with_missing_project_rejected(repo, user):
    with pytest.raises(domain.InvalidProject):
        repo.create_todo(user, "x", project_id=str(uuid.uuid4()))


@pytest.mark.parametrize("title", ["", "  "])
def test_empty_title_rejected(repo, user, title):
    with pytest.raises(domain.ValidationError):
        repo.create_todo(user, title)


@pytest.mark.parametrize("bad", ["2026/11/05", "20261105", "2026-02-30", "tomorrow"])
def test_invalid_due_date_rejected(repo, user, bad):
    with pytest.raises(domain.ValidationError):
        repo.create_todo(user, "x", due_date=bad)


def test_update_todo_fields(repo, user):
    p = repo.create_project(user, "Work")
    t = repo.create_todo(user, "old")
    t = repo.update_todo(user, t["id"], {"title": "new", "due_date": "2026-11-05", "is_done": True})
    assert (t["title"], t["due_date"], t["is_done"]) == ("new", "2026-11-05", True)

    t = repo.update_todo(user, t["id"], {"project_id": p["id"]})  # 미분류 → 프로젝트 배정
    assert t["project_id"] == p["id"]
    t = repo.update_todo(user, t["id"], {"project_id": None, "due_date": None, "is_done": False})
    assert (t["project_id"], t["due_date"], t["is_done"]) == (None, None, False)  # 미분류로 변경, 마감일 제거


def test_update_todo_partial_keeps_other_fields(repo, user):
    t = repo.create_todo(user, "keep", due_date="2026-11-05")
    t = repo.update_todo(user, t["id"], {"is_done": True})
    assert (t["title"], t["due_date"]) == ("keep", "2026-11-05")


def test_update_todo_rejects_bad_input(repo, user):
    t = repo.create_todo(user, "x")
    with pytest.raises(domain.InvalidProject):
        repo.update_todo(user, t["id"], {"project_id": str(uuid.uuid4())})
    with pytest.raises(domain.ValidationError):
        repo.update_todo(user, t["id"], {"user_id": "someone"})  # 허용되지 않은 필드
    with pytest.raises(domain.ValidationError):
        repo.update_todo(user, t["id"], {"is_done": "yes"})
    with pytest.raises(domain.NotFound):
        repo.update_todo(user, str(uuid.uuid4()), {"title": "y"})


def test_delete_todo(repo, user):
    t = repo.create_todo(user, "x")
    repo.delete_todo(user, t["id"])
    assert repo.list_todos(user, None) == []
    with pytest.raises(domain.NotFound):
        repo.delete_todo(user, t["id"])


def test_sort_by_due_date_nulls_last(repo, user):
    repo.create_todo(user, "no date")
    repo.create_todo(user, "later", due_date="2026-12-01")
    repo.create_todo(user, "sooner", due_date="2026-11-01")
    assert [t["title"] for t in repo.list_todos(user, None, sort="due")] == ["sooner", "later", "no date"]
    assert [t["title"] for t in repo.list_todos(user, None, sort="created")] == ["no date", "later", "sooner"]


# ---------- 스키마 자체의 제약조건 (저장소 검증을 우회한 직접 INSERT) ----------


def _raw(repo):
    conn = sqlite3.connect(repo.db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_schema_rejects_untrimmed_or_empty_name(repo):
    conn = _raw(repo)
    for bad in (" Work", "Work ", ""):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (str(uuid.uuid4()), bad))


def test_schema_rejects_case_duplicate(repo):
    conn = _raw(repo)
    conn.execute("INSERT INTO projects (id, name) VALUES (?, 'Work')", (str(uuid.uuid4()),))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO projects (id, name) VALUES (?, 'wOrK')", (str(uuid.uuid4()),))


def test_schema_rejects_bad_id_and_is_done(repo):
    conn = _raw(repo)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO projects (id, name) VALUES ('short', 'X')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO todos (id, title, is_done) VALUES (?, 't', 2)", (str(uuid.uuid4()),))


def test_init_db_is_idempotent_and_keeps_data(repo, user):
    from backend.repositories.sqlite_repo import SqliteRepository

    repo.create_project(user, "Persist")
    reopened = SqliteRepository(repo.db_path)  # 서버 재시작과 같은 상황
    assert [p["name"] for p in reopened.list_projects(user)["projects"]] == ["Persist"]
