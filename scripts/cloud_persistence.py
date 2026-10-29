"""클라우드(Supabase) 데이터 영속성 검증 — 앱 API(로컬 서버, supabase 모드)를 테스트 계정 A 로 사용한다.

실행 (프로젝트 폴더에서, 서버가 supabase 모드로 실행 중일 때):
    .venv/Scripts/python -m scripts.cloud_persistence before   # 데이터 생성·완료·삭제 + 스냅숏 저장
    (서버 완전 종료 → 재시작)
    .venv/Scripts/python -m scripts.cloud_persistence after    # 재로그인 후 스냅숏과 비교

- 완료·삭제가 실제 DB 에 반영됐는지는 앱을 거치지 않고 Supabase REST 를 A 의 토큰으로 직접 조회해 확인한다.
- 만든 데이터는 Table Editor 에서 확인할 수 있도록 남겨 둔다 (프로젝트 "B5 영속성 확인").
- 출력·결과 파일에 비밀번호·토큰·이메일·user_id 를 남기지 않는다.
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import httpx

from backend import config
from backend.supabase_auth import SupabaseAuth

API = "http://127.0.0.1:8000"
PROJECT = "B5 영속성 확인"
SNAPSHOT = Path(tempfile.gettempdir()) / "project_todo_b5_snapshot.json"
RESULT_FILE = Path(__file__).resolve().parent.parent / "docs" / "cloud_persistence_result.md"


def creds():
    return os.getenv("RLS_TEST_A_EMAIL", "").strip(), os.getenv("RLS_TEST_A_PASSWORD", "")


def app_login() -> httpx.Client:
    health = httpx.get(f"{API}/api/health", timeout=5).json()
    if health.get("db_backend") != "supabase":
        sys.exit("로컬 서버가 supabase 모드가 아닙니다.")
    client = httpx.Client(base_url=API, timeout=20)
    email, pw = creds()
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        sys.exit(f"앱 로그인 실패 (HTTP {r.status_code})")
    return client


def snapshot(client: httpx.Client) -> dict:
    projects = client.get("/api/projects").json()
    data = {"projects": projects, "todos": {}}
    for p in projects["projects"]:
        data["todos"][p["id"]] = client.get("/api/todos", params={"project": p["id"], "sort": "created"}).json()
    data["todos"]["unassigned"] = client.get("/api/todos", params={"project": "unassigned", "sort": "created"}).json()
    return data


def db_rows(todo_ids: list[str]) -> dict:
    """앱을 거치지 않고 Supabase REST 를 A 의 토큰으로 직접 조회."""
    auth = SupabaseAuth(config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY)
    session = auth.sign_in(*creds())
    try:
        r = httpx.get(
            f"{config.SUPABASE_URL}/rest/v1/todos",
            params={"select": "id,title,is_done,project_id", "id": f"in.({','.join(todo_ids)})"},
            headers={"apikey": config.SUPABASE_PUBLISHABLE_KEY, "Authorization": f"Bearer {session.access_token}"},
            timeout=15,
        )
        return {row["id"]: row for row in r.json()}
    finally:
        auth.sign_out(session.access_token)


def write_result(lines: list[str], mode: str) -> None:
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = [] if mode == "a" and RESULT_FILE.exists() else ["# 클라우드 영속성 검증 결과 (scripts/cloud_persistence.py 자동 생성)", ""]
    with RESULT_FILE.open(mode, encoding="utf-8") as f:
        f.write("\n".join(header + lines) + "\n")


def before() -> int:
    c = app_login()
    lines = [f"## before — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "", "| 단계 | 결과 |", "|---|---|"]

    r = c.post("/api/projects", json={"name": PROJECT})
    if r.status_code == 409:  # 재실행 시 기존 프로젝트 사용
        project = next(p for p in c.get("/api/projects").json()["projects"] if p["name"] == PROJECT)
    else:
        project = r.json()
    lines.append(f"| 프로젝트 생성 `{PROJECT}` | HTTP {r.status_code} |")

    created = {}
    for title, pid, due in (
        ("완료 처리할 할 일", project["id"], "2026-11-05"),
        ("삭제할 할 일", project["id"], None),
        ("유지될 할 일", project["id"], "2026-10-20"),
        ("미분류 할 일", None, None),
    ):
        r = c.post("/api/todos", json={"title": title, "project_id": pid, "due_date": due})
        created[title] = r.json()["id"]
        lines.append(f"| 할 일 생성 `{title}` | HTTP {r.status_code} |")

    r = c.patch(f"/api/todos/{created['완료 처리할 할 일']}", json={"is_done": True})
    lines.append(f"| 완료 처리 | HTTP {r.status_code}, is_done={r.json().get('is_done')} |")
    r = c.delete(f"/api/todos/{created['삭제할 할 일']}")
    lines.append(f"| 삭제 | HTTP {r.status_code} |")

    db = db_rows(list(created.values()))
    done_ok = db.get(created["완료 처리할 할 일"], {}).get("is_done") is True
    delete_ok = created["삭제할 할 일"] not in db
    unassigned_ok = db.get(created["미분류 할 일"], {}).get("project_id") is None
    lines.append(f"| Supabase DB 직접 조회: 완료 반영 | {'✅' if done_ok else '❌'} is_done=true |")
    lines.append(f"| Supabase DB 직접 조회: 삭제 반영 | {'✅' if delete_ok else '❌'} 행 없음 |")
    lines.append(f"| Supabase DB 직접 조회: 미분류 저장 | {'✅' if unassigned_ok else '❌'} project_id=NULL |")

    snap = snapshot(c)
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    total = sum(len(v) for v in snap["todos"].values())
    lines.append(f"| 스냅숏 저장 | 프로젝트 {len(snap['projects']['projects'])}개, 할 일 {total}건 |")
    c.post("/api/auth/logout")

    write_result(lines + [""], "w")
    print("\n".join(lines))
    return 0 if done_ok and delete_ok and unassigned_ok else 1


def after() -> int:
    if not SNAPSHOT.exists():
        sys.exit("before 단계의 스냅숏이 없습니다.")
    c = app_login()  # 새 로그인 = 새 세션
    now = snapshot(c)
    c.post("/api/auth/logout")
    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    same = json.dumps(now, ensure_ascii=False, sort_keys=True) == json.dumps(saved, ensure_ascii=False, sort_keys=True)
    total = sum(len(v) for v in now["todos"].values())
    lines = [
        f"## after (서버 재시작 + 재로그인) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 단계 | 결과 |",
        "|---|---|",
        "| 재로그인 | ✅ |",
        f"| 조회 | 프로젝트 {len(now['projects']['projects'])}개, 할 일 {total}건 |",
        f"| 재시작 전 스냅숏과 비교 | {'✅ 완전 일치' if same else '❌ 불일치'} |",
        "",
    ]
    write_result(lines, "a")
    print("\n".join(lines))
    SNAPSHOT.unlink(missing_ok=True)
    return 0 if same else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("before", "after"):
        sys.exit("사용법: python -m scripts.cloud_persistence before|after")
    sys.exit(before() if sys.argv[1] == "before" else after())
