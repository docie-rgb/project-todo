"""SQLite 저장소 구현. SQL 문은 이 파일에만 있다.

로컬 모드는 단일 사용자이므로 user 인자는 받기만 하고 쿼리에 쓰지 않는다
(DB_DESIGN.md: 로컬 스키마에는 user_id 컬럼이 없다).
"""

import sqlite3
import uuid
from pathlib import Path

from backend import domain
from backend.db.sqlite import connect, init_db
from backend.domain import CurrentUser
from backend.repositories.base import TODO_UPDATABLE_FIELDS, TodoSort

_PROJECT_SELECT = """
SELECT p.id, p.name, p.created_at,
       COUNT(t.id)                 AS total_count,
       COALESCE(SUM(t.is_done), 0) AS done_count
FROM projects p
LEFT JOIN todos t ON t.project_id = p.id
"""

_TODO_ORDER = {
    # 마감일 없는 할 일은 뒤로
    "due": "due_date IS NULL, due_date, created_at, rowid",
    "created": "created_at, rowid",
}


def _todo(row: sqlite3.Row) -> dict:
    todo = dict(row)
    todo["is_done"] = bool(todo["is_done"])
    return todo


def _constraint(err: sqlite3.IntegrityError) -> str:
    return getattr(err, "sqlite_errorname", "")


class SqliteRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        init_db(db_path)

    # ---------- projects ----------

    def list_projects(self, user: CurrentUser) -> dict:
        with connect(self.db_path) as conn:
            projects = conn.execute(
                _PROJECT_SELECT + " GROUP BY p.id ORDER BY p.created_at, p.rowid"
            ).fetchall()
            unassigned = conn.execute(
                "SELECT COUNT(*) AS total_count, COALESCE(SUM(is_done), 0) AS done_count"
                " FROM todos WHERE project_id IS NULL"
            ).fetchone()
        return {"projects": [dict(r) for r in projects], "unassigned": dict(unassigned)}

    def _get_project(self, conn: sqlite3.Connection, project_id: str) -> dict:
        row = conn.execute(_PROJECT_SELECT + " WHERE p.id = ? GROUP BY p.id", (project_id,)).fetchone()
        if row is None:
            raise domain.NotFound("프로젝트를 찾을 수 없습니다.")
        return dict(row)

    def create_project(self, user: CurrentUser, name: str) -> dict:
        name = domain.clean_project_name(name)
        project_id = str(uuid.uuid4())
        try:
            with connect(self.db_path) as conn:
                conn.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (project_id, name))
                return self._get_project(conn, project_id)
        except sqlite3.IntegrityError as err:
            if _constraint(err) == "SQLITE_CONSTRAINT_UNIQUE":
                raise domain.DuplicateProjectName(name) from None
            raise

    def rename_project(self, user: CurrentUser, project_id: str, name: str) -> dict:
        name = domain.clean_project_name(name)
        try:
            with connect(self.db_path) as conn:
                cur = conn.execute("UPDATE projects SET name = ? WHERE id = ?", (name, project_id))
                if cur.rowcount == 0:
                    raise domain.NotFound("프로젝트를 찾을 수 없습니다.")
                return self._get_project(conn, project_id)
        except sqlite3.IntegrityError as err:
            if _constraint(err) == "SQLITE_CONSTRAINT_UNIQUE":
                raise domain.DuplicateProjectName(name) from None
            raise

    def delete_project(self, user: CurrentUser, project_id: str) -> None:
        # 소속 할 일의 project_id 는 FK의 ON DELETE SET NULL 이 NULL(미분류)로 바꾼다.
        with connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            if cur.rowcount == 0:
                raise domain.NotFound("프로젝트를 찾을 수 없습니다.")

    # ---------- todos ----------

    def list_todos(self, user: CurrentUser, project_id: str | None, sort: TodoSort = "created") -> list[dict]:
        order = _TODO_ORDER[sort]
        with connect(self.db_path) as conn:
            # "IS ?" 는 NULL 끼리도 일치하므로 미분류(None)와 프로젝트를 같은 쿼리로 조회한다.
            rows = conn.execute(
                "SELECT id, project_id, title, is_done, due_date, created_at"
                f" FROM todos WHERE project_id IS ? ORDER BY {order}",
                (project_id,),
            ).fetchall()
        return [_todo(r) for r in rows]

    def _get_todo(self, conn: sqlite3.Connection, todo_id: str) -> dict:
        row = conn.execute(
            "SELECT id, project_id, title, is_done, due_date, created_at FROM todos WHERE id = ?",
            (todo_id,),
        ).fetchone()
        if row is None:
            raise domain.NotFound("할 일을 찾을 수 없습니다.")
        return _todo(row)

    def create_todo(
        self, user: CurrentUser, title: str, project_id: str | None = None, due_date: str | None = None
    ) -> dict:
        title = domain.clean_title(title)
        due_date = domain.clean_due_date(due_date)
        todo_id = str(uuid.uuid4())
        try:
            with connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO todos (id, project_id, title, due_date) VALUES (?, ?, ?, ?)",
                    (todo_id, project_id, title, due_date),
                )
                return self._get_todo(conn, todo_id)
        except sqlite3.IntegrityError as err:
            if _constraint(err) == "SQLITE_CONSTRAINT_FOREIGNKEY":
                raise domain.InvalidProject() from None
            raise

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
            values["is_done"] = int(changes["is_done"])
        if "project_id" in changes:
            values["project_id"] = changes["project_id"]  # None = 미분류로 변경

        try:
            with connect(self.db_path) as conn:
                if values:
                    assignments = ", ".join(f"{col} = ?" for col in values)  # 컬럼명은 화이트리스트 키만
                    cur = conn.execute(
                        f"UPDATE todos SET {assignments} WHERE id = ?", (*values.values(), todo_id)
                    )
                    if cur.rowcount == 0:
                        raise domain.NotFound("할 일을 찾을 수 없습니다.")
                return self._get_todo(conn, todo_id)
        except sqlite3.IntegrityError as err:
            if _constraint(err) == "SQLITE_CONSTRAINT_FOREIGNKEY":
                raise domain.InvalidProject() from None
            raise

    def delete_todo(self, user: CurrentUser, todo_id: str) -> None:
        with connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            if cur.rowcount == 0:
                raise domain.NotFound("할 일을 찾을 수 없습니다.")
