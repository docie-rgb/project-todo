"""RLS 실제 검증 스크립트 — 테스트 계정 A/B 의 "일반 사용자 권한"으로 실제 Supabase 를 호출한다.

실행 (프로젝트 폴더에서):
    .venv/Scripts/python -m scripts.rls_check

필요한 .env 값: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, RLS_TEST_A_EMAIL/PASSWORD, RLS_TEST_B_EMAIL/PASSWORD

검증 방식
  [DB 직접] 우리 백엔드를 거치지 않고 Supabase REST(/rest/v1)에 A·B 각자의 토큰으로 요청한다.
           → Python 코드의 필터가 아니라 DB 의 RLS·제약조건이 막는지 확인한다.
  [앱 API]  실행 중인 로컬 서버(http://127.0.0.1:8000, supabase 모드)에 같은 시나리오를 보낸다.
           서버가 없으면 이 부분은 건너뛴다.
관리자(secret/service_role) 키는 사용하지 않는다.

출력에는 토큰·비밀번호·이메일·user_id 를 표시하지 않는다.
검증용으로 만든 행은 마지막에 삭제한다. 결과는 docs/rls_check_result.md 에도 저장한다.
"""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from backend import config
from backend.supabase_auth import SupabaseAuth

# 앱 API 검증 대상 (배포 후에는 RLS_CHECK_API_BASE=https://<앱 주소> 로 바꿔 실행할 수 있다)
API_BASE = os.getenv("RLS_CHECK_API_BASE", "http://127.0.0.1:8000").rstrip("/")
RESULT_FILE = Path(__file__).resolve().parent.parent / "docs" / "rls_check_result.md"

results: list[tuple[str, str, bool, str]] = []  # (구분, 항목, 통과, 근거)


def check(group: str, name: str, ok: bool, evidence: str) -> None:
    results.append((group, name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {group} | {name} — {evidence}")


def env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        sys.exit(f".env 에 {name} 값이 없습니다. (값은 출력하지 않습니다)")
    return value


class Rest:
    """한 사용자의 토큰으로 Supabase REST 를 호출한다 (token=None 이면 비로그인)."""

    def __init__(self, token: str | None):
        self.headers = {"apikey": config.SUPABASE_PUBLISHABLE_KEY, "Prefer": "return=representation"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.http = httpx.Client(base_url=f"{config.SUPABASE_URL}/rest/v1", timeout=15.0)

    def call(self, method: str, table: str, params=None, json=None) -> tuple[int, object]:
        r = self.http.request(method, f"/{table}", params=params, json=json, headers=self.headers)
        try:
            body = r.json() if r.content else []
        except ValueError:
            body = None
        return r.status_code, body


def code_of(body) -> str | None:
    return body.get("code") if isinstance(body, dict) else None


def rows(body) -> int:
    return len(body) if isinstance(body, list) else -1


def main() -> int:
    if config.SUPABASE_PUBLISHABLE_KEY.startswith("sb_secret_"):
        sys.exit("SUPABASE_PUBLISHABLE_KEY 에 secret 키가 들어 있습니다. publishable 키로 바꾸세요.")
    if not config.SUPABASE_URL or not config.SUPABASE_PUBLISHABLE_KEY:
        sys.exit(".env 에 SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY 가 없습니다.")

    auth = SupabaseAuth(config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY)
    a_email, a_pw = env("RLS_TEST_A_EMAIL"), env("RLS_TEST_A_PASSWORD")
    b_email, b_pw = env("RLS_TEST_B_EMAIL"), env("RLS_TEST_B_PASSWORD")
    sa = auth.sign_in(a_email, a_pw)
    sb = auth.sign_in(b_email, b_pw)
    check("준비", "A·B 로그인 (일반 사용자 토큰 발급)", sa.user_id != sb.user_id, "서로 다른 사용자 2명")

    A, B, ANON = Rest(sa.access_token), Rest(sb.access_token), Rest(None)
    tag = f"RLS-check-{uuid.uuid4().hex[:6]}"
    b_todo_id = None
    a_project_id = None

    try:
        # ---------- 1. A 가 데이터 생성 ----------
        s, body = A.call("POST", "projects", json={"name": tag})
        a_project_id = body[0]["id"] if s == 201 else None
        check("DB 직접", "1. A 프로젝트 생성", s == 201, f"HTTP {s}")
        s1, t1 = A.call("POST", "todos", json={"title": f"{tag} 프로젝트 할 일", "project_id": a_project_id})
        s2, t2 = A.call("POST", "todos", json={"title": f"{tag} 미분류 할 일"})
        a_todo = t1[0]["id"] if s1 == 201 else None
        a_loose = t2[0]["id"] if s2 == 201 else None
        check("DB 직접", "1. A 할 일 생성 (프로젝트 + 미분류)", s1 == 201 and s2 == 201, f"HTTP {s1}, {s2}")
        check(
            "DB 직접",
            "1. user_id 자동 입력 (요청 본문에 user_id 없음)",
            t1[0].get("user_id") == sa.user_id if s1 == 201 and "user_id" in t1[0] else s1 == 201,
            "DB 기본값 auth.uid() 가 A 로 채움",
        )

        # ---------- 2. A 자신의 데이터 접근 ----------
        _, ap = A.call("GET", "projects", params={"select": "id", "id": f"eq.{a_project_id}"})
        _, at = A.call("GET", "todos", params={"select": "id", "id": f"in.({a_todo},{a_loose})"})
        check("DB 직접", "2. A 가 자기 프로젝트·할 일 조회", rows(ap) == 1 and rows(at) == 2, f"프로젝트 {rows(ap)}건, 할 일 {rows(at)}건")

        # ---------- 3. B 목록에 A 데이터 없음 ----------
        _, bp = B.call("GET", "projects", params={"select": "id"})
        _, bt = B.call("GET", "todos", params={"select": "id"})
        b_ids = {r["id"] for r in (bp or []) + (bt or [])} if isinstance(bp, list) and isinstance(bt, list) else set()
        leaked = b_ids & {a_project_id, a_todo, a_loose}
        check("DB 직접", "3. B 의 전체 목록에 A 데이터 없음", isinstance(bp, list) and not leaked, f"A 의 행 {len(leaked)}건 노출")

        # ---------- 4. B 가 A 의 할 일 직접 조회 ----------
        s, body = B.call("GET", "todos", params={"select": "id,title", "id": f"in.({a_todo},{a_loose})"})
        check("DB 직접", "4. B 가 A 의 할 일 ID 로 직접 조회 (미분류 포함)", s == 200 and rows(body) == 0, f"HTTP {s}, {rows(body)}건")

        # ---------- 5. B 가 A 의 할 일 수정 ----------
        s, body = B.call("PATCH", "todos", params={"id": f"eq.{a_todo}"}, json={"title": "B가 바꿈", "is_done": True})
        check("DB 직접", "5. B 가 A 의 할 일 수정", rows(body) == 0, f"HTTP {s}, 변경 {rows(body)}건")
        s, body = B.call("PATCH", "projects", params={"id": f"eq.{a_project_id}"}, json={"name": "B가 바꿈"})
        check("DB 직접", "5. B 가 A 의 프로젝트 이름 수정", rows(body) == 0, f"HTTP {s}, 변경 {rows(body)}건")

        # ---------- 6. B 가 A 의 할 일 삭제 ----------
        s, body = B.call("DELETE", "todos", params={"id": f"in.({a_todo},{a_loose})"})
        check("DB 직접", "6. B 가 A 의 할 일 삭제 (미분류 포함)", rows(body) == 0, f"HTTP {s}, 삭제 {rows(body)}건")
        s, body = B.call("DELETE", "projects", params={"id": f"eq.{a_project_id}"})
        check("DB 직접", "6. B 가 A 의 프로젝트 삭제", rows(body) == 0, f"HTTP {s}, 삭제 {rows(body)}건")

        # ---------- 7. B 가 자기 할 일을 A 의 프로젝트에 연결 ----------
        s, body = B.call("POST", "todos", json={"title": f"{tag} B 할 일", "project_id": a_project_id})
        check("DB 직접", "7. B 가 A 의 프로젝트로 할 일 생성", code_of(body) == "23503", f"HTTP {s}, code={code_of(body)} (복합 외래키)")
        s, body = B.call("POST", "todos", json={"title": f"{tag} B 할 일"})
        b_todo_id = body[0]["id"] if s == 201 else None
        s, body = B.call("PATCH", "todos", params={"id": f"eq.{b_todo_id}"}, json={"project_id": a_project_id})
        check("DB 직접", "7. B 가 자기 할 일을 A 의 프로젝트로 이동", code_of(body) == "23503", f"HTTP {s}, code={code_of(body)} (복합 외래키)")
        s, body = B.call("POST", "todos", json={"title": f"{tag} 위장", "user_id": sa.user_id})
        check("DB 직접", "7. B 가 user_id=A 로 행 생성", code_of(body) == "42501", f"HTTP {s}, code={code_of(body)} (RLS WITH CHECK)")
        s, body = B.call("PATCH", "todos", params={"id": f"eq.{b_todo_id}"}, json={"user_id": sa.user_id})
        check("DB 직접", "7. B 가 자기 할 일을 A 소유로 변경", code_of(body) == "42501", f"HTTP {s}, code={code_of(body)} (RLS WITH CHECK)")

        # ---------- 8. 원본 보존 ----------
        _, ap = A.call("GET", "projects", params={"select": "name", "id": f"eq.{a_project_id}"})
        _, at = A.call("GET", "todos", params={"select": "id,title,is_done,project_id", "id": f"in.({a_todo},{a_loose})", "order": "created_at"})
        intact = (
            rows(ap) == 1 and ap[0]["name"] == tag
            and rows(at) == 2
            and all(not t["is_done"] and "B가" not in t["title"] for t in at)
            and {t["id"]: t["project_id"] for t in at} == {a_todo: a_project_id, a_loose: None}
        )
        check("DB 직접", "8. 차단 이후 A 의 원본 데이터 그대로", intact, f"프로젝트 {rows(ap)}건, 할 일 {rows(at)}건, 제목·완료·소속 변화 없음={intact}")

        # ---------- 9. 비로그인 ----------
        s1, b1 = ANON.call("GET", "todos", params={"select": "id"})
        s2, b2 = ANON.call("GET", "projects", params={"select": "id"})
        s3, b3 = ANON.call("POST", "todos", json={"title": "anon"})
        anon_blocked = all(s >= 400 or rows(b) == 0 for s, b in ((s1, b1), (s2, b2))) and s3 >= 400
        check("DB 직접", "9. 비로그인(publishable 키만) 조회·생성", anon_blocked,
              f"GET todos {s1}/{code_of(b1)}, GET projects {s2}/{code_of(b2)}, POST {s3}/{code_of(b3)}")

        # ---------- 앱 API 경유 ----------
        run_api_checks(a_email, a_pw, b_email, b_pw, a_project_id, a_todo)

    finally:
        # ---------- 정리: 검증용 행 삭제 (각자 자기 행만 지울 수 있다) ----------
        if b_todo_id:
            B.call("DELETE", "todos", params={"id": f"eq.{b_todo_id}"})
        A.call("DELETE", "todos", params={"title": f"like.{tag}*"})
        if a_project_id:
            A.call("DELETE", "projects", params={"id": f"eq.{a_project_id}"})
        for s in (sa, sb):
            try:
                auth.sign_out(s.access_token)
            except Exception:
                pass

    write_result_file()
    failed = [r for r in results if not r[2]]
    print(f"\n총 {len(results)}개 중 통과 {len(results) - len(failed)}개, 실패 {len(failed)}개")
    print(f"결과 저장: {RESULT_FILE.relative_to(RESULT_FILE.parent.parent)}")
    return 1 if failed else 0


def run_api_checks(a_email, a_pw, b_email, b_pw, a_project_id, a_todo) -> None:
    try:
        health = httpx.get(f"{API_BASE}/api/health", timeout=3).json()
    except httpx.HTTPError:
        print("[SKIP] 앱 API | 로컬 서버가 실행 중이 아니어서 건너뜀")
        return
    if health.get("db_backend") != "supabase":
        print("[SKIP] 앱 API | 로컬 서버가 sqlite 모드라서 건너뜀 (.env 의 DB_BACKEND=supabase 후 서버 재시작)")
        return

    anon = httpx.Client(base_url=API_BASE, timeout=15)
    s = anon.get("/api/projects").status_code
    check("앱 API", "9. 비로그인으로 /api/projects", s == 401, f"HTTP {s}")

    b = httpx.Client(base_url=API_BASE, timeout=15)
    s = b.post("/api/auth/login", json={"email": b_email, "password": b_pw}).status_code
    check("앱 API", "B 로그인 (HttpOnly 쿠키)", s == 200, f"HTTP {s}")
    r = b.get("/api/projects").json()
    check("앱 API", "3. B 의 프로젝트 목록에 A 프로젝트 없음",
          all(p["id"] != a_project_id for p in r.get("projects", [])), f"{len(r.get('projects', []))}개 중 A 것 0개")
    r = b.get("/api/todos", params={"project": a_project_id})
    check("앱 API", "4. B 가 A 의 프로젝트 할 일 조회", r.status_code == 200 and r.json() == [], f"HTTP {r.status_code}, {len(r.json())}건")
    s = b.patch(f"/api/todos/{a_todo}", json={"title": "B가 바꿈"}).status_code
    check("앱 API", "5. B 가 A 의 할 일 수정", s == 404, f"HTTP {s}")
    s = b.delete(f"/api/todos/{a_todo}").status_code
    check("앱 API", "6. B 가 A 의 할 일 삭제", s == 404, f"HTTP {s}")
    s = b.post("/api/todos", json={"title": "B", "project_id": a_project_id}).status_code
    check("앱 API", "7. B 가 A 의 프로젝트로 할 일 생성", s == 422, f"HTTP {s}")
    s = b.post("/api/todos", json={"title": "B", "user_id": "anything"}).status_code
    check("앱 API", "7. B 가 user_id 를 직접 보냄", s == 422, f"HTTP {s} (입력 단계에서 거부)")
    b.post("/api/auth/logout")

    a = httpx.Client(base_url=API_BASE, timeout=15)
    a.post("/api/auth/login", json={"email": a_email, "password": a_pw})
    r = a.get("/api/todos", params={"project": a_project_id}).json()
    check("앱 API", "8. A 로 다시 조회 시 원본 그대로", len(r) == 1 and r[0]["id"] == a_todo and "B가" not in r[0]["title"],
          f"{len(r)}건")
    a.post("/api/auth/logout")


def write_result_file() -> None:
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# RLS 검증 결과 (scripts/rls_check.py 자동 생성)",
        "",
        f"- 실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 권한: 테스트 계정 A·B 의 일반 사용자 토큰 (관리자 키 사용 안 함)",
        "- 개인정보·토큰은 기록하지 않음",
        "",
        "| 구분 | 항목 | 결과 | 근거 |",
        "|---|---|---|---|",
    ]
    lines += [f"| {g} | {n} | {'✅ PASS' if ok else '❌ FAIL'} | {e} |" for g, n, ok, e in results]
    RESULT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
