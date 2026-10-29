"""로그인·세션 쿠키·CSRF 방어 테스트 — 실제 Supabase 대신 가짜 인증 서버(FakeAuth)를 쓴다.

이 테스트가 증명하는 것:
  - supabase 모드에서 로그인 없이는 데이터 API 가 401
  - 로그인 시 토큰은 HttpOnly 쿠키로만 전달되고 응답 본문에 없음
  - 검증된 토큰이 저장소(→ DB 요청)까지 전달됨
  - 갱신·로그아웃 시 쿠키 교체·삭제, 다른 출처·비 JSON 요청 거부
  - sqlite 모드는 로그인 없이 기존대로 동작
이 테스트가 증명하지 못하는 것:
  - 실제 Supabase 가 비밀번호·토큰을 올바르게 검증하는지, RLS 가 남의 행을 막는지 → B4 실제 검증
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, domain
from backend.api import auth as auth_api
from backend.api import deps
from backend import main
from backend.supabase_auth import Session

GOOD = {"email": "a@example.com", "password": "correct-password"}


class FakeAuth:
    def __init__(self):
        self.valid_access = set()
        self.valid_refresh = set()
        self.signed_out = []
        self.counter = 0

    def _new_session(self):
        self.counter += 1
        access, refresh = f"access-{self.counter}", f"refresh-{self.counter}"
        self.valid_access.add(access)
        self.valid_refresh.add(refresh)
        return Session(user_id="user-a", email=GOOD["email"], access_token=access, refresh_token=refresh, expires_in=3600)

    def sign_in(self, email, password):
        if (email, password) != (GOOD["email"], GOOD["password"]):
            raise domain.Unauthorized("이메일 또는 비밀번호가 올바르지 않습니다.")
        return self._new_session()

    def refresh(self, refresh_token):
        if refresh_token not in self.valid_refresh:
            raise domain.Unauthorized("로그인이 만료되었습니다. 다시 로그인하세요.")
        self.valid_refresh.discard(refresh_token)  # rotation: 한 번 쓰면 무효
        return self._new_session()

    def get_user(self, access_token):
        if access_token not in self.valid_access:
            raise domain.Unauthorized("로그인이 만료되었습니다. 다시 로그인하세요.")
        return domain.CurrentUser(id="user-a", email=GOOD["email"], access_token=access_token)

    def sign_out(self, access_token):
        self.signed_out.append(access_token)
        self.valid_access.discard(access_token)


class RecordingRepo:
    """SQLite 저장소에 위임하면서, 저장소가 받은 사용자 정보를 기록한다."""

    def __init__(self, inner):
        self.inner = inner
        self.users = []

    def __getattr__(self, name):
        method = getattr(self.inner, name)

        def wrapper(user, *args, **kwargs):
            self.users.append(user)
            return method(user, *args, **kwargs)

        return wrapper


@pytest.fixture
def fake_auth():
    return FakeAuth()


@pytest.fixture
def supa_client(monkeypatch, repo, fake_auth):
    """supabase 모드 앱. 저장소는 임시 SQLite, 인증은 FakeAuth."""
    recording = RecordingRepo(repo)
    monkeypatch.setattr(config, "DB_BACKEND", "supabase")
    for module in (deps, auth_api, main):
        monkeypatch.setattr(module, "get_auth", lambda: fake_auth)
    monkeypatch.setattr(main, "get_repo", lambda: recording)
    main.app.dependency_overrides[deps.get_repo] = lambda: recording
    with TestClient(main.app) as c:
        c.recording = recording
        yield c
    main.app.dependency_overrides.clear()


def _login(client):
    r = client.post("/api/auth/login", json=GOOD)
    assert r.status_code == 200, r.text
    return r


def _set_cookie_headers(response):
    return [v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"]


# ---------- 로그인 전 ----------


def test_me_reports_login_required(supa_client):
    assert supa_client.get("/api/auth/me").json() == {"auth_required": True, "user": None}


def test_data_api_requires_login(supa_client):
    assert supa_client.get("/api/projects").status_code == 401
    assert supa_client.post("/api/todos", json={"title": "x"}).status_code == 401
    assert supa_client.recording.users == []  # 저장소(DB)까지 가지도 않음


def test_wrong_password_is_generic_401(supa_client):
    r = supa_client.post("/api/auth/login", json={**GOOD, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "이메일 또는 비밀번호가 올바르지 않습니다."
    assert _set_cookie_headers(r) == []


def test_forged_token_cookie_rejected(supa_client):
    supa_client.cookies.set("pt_access", "forged-token", path="/api")
    assert supa_client.get("/api/projects").status_code == 401


# ---------- 로그인 ----------


def test_login_sets_httponly_cookies_and_hides_tokens(supa_client):
    r = _login(supa_client)
    assert r.json() == {"user": {"email": GOOD["email"]}}
    assert "access-" not in r.text and "refresh-" not in r.text  # 본문에 토큰 없음

    cookies = _set_cookie_headers(r)
    access = next(c for c in cookies if c.startswith("pt_access="))
    refresh = next(c for c in cookies if c.startswith("pt_refresh="))
    assert "HttpOnly" in access and "Path=/api" in access and "SameSite=lax" in access
    assert "HttpOnly" in refresh and "Path=/api/auth" in refresh and "SameSite=strict" in refresh


def test_verified_token_reaches_repository(supa_client):
    _login(supa_client)
    assert supa_client.post("/api/projects", json={"name": "Work"}).status_code == 201
    user = supa_client.recording.users[-1]
    assert user.id == "user-a"
    assert user.access_token == "access-1"  # 이 토큰이 DB 요청 헤더에 실려 RLS 가 적용된다
    assert supa_client.get("/api/auth/me").json()["user"] == {"email": GOOD["email"]}


def test_client_supplied_user_id_is_rejected(supa_client):
    _login(supa_client)
    assert supa_client.post("/api/todos", json={"title": "x", "user_id": "someone-else"}).status_code == 422


# ---------- 갱신 ----------


def test_refresh_rotates_tokens(supa_client, fake_auth):
    _login(supa_client)
    fake_auth.valid_access.clear()  # 액세스 토큰 만료 상황
    assert supa_client.get("/api/projects").status_code == 401

    r = supa_client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert "refresh-1" not in fake_auth.valid_refresh  # 사용한 리프레시 토큰은 무효
    assert supa_client.get("/api/projects").status_code == 200


def test_me_silently_refreshes_expired_access(supa_client, fake_auth):
    _login(supa_client)
    fake_auth.valid_access.clear()
    assert supa_client.get("/api/auth/me").json()["user"] == {"email": GOOD["email"]}
    assert supa_client.get("/api/projects").status_code == 200


def test_failed_refresh_clears_cookies(supa_client, fake_auth):
    _login(supa_client)
    fake_auth.valid_refresh.clear()
    r = supa_client.post("/api/auth/refresh")
    assert r.status_code == 401
    assert any(c.startswith("pt_refresh=") and "Max-Age=0" in c for c in _set_cookie_headers(r))


# ---------- 로그아웃 ----------


def test_logout_revokes_and_clears(supa_client, fake_auth):
    _login(supa_client)
    r = supa_client.post("/api/auth/logout")
    assert r.status_code == 204
    assert fake_auth.signed_out == ["access-1"]
    assert all("Max-Age=0" in c for c in _set_cookie_headers(r))
    assert supa_client.get("/api/projects").status_code == 401


# ---------- CSRF 방어 ----------


def test_cross_origin_write_blocked(supa_client):
    _login(supa_client)
    r = supa_client.post("/api/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = supa_client.post("/api/auth/login", json=GOOD, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403  # 로그인 CSRF 도 차단
    ok = supa_client.post("/api/projects", json={"name": "y"}, headers={"Origin": "http://testserver"})
    assert ok.status_code == 201


def test_non_json_write_blocked(supa_client):
    _login(supa_client)
    r = supa_client.post(
        "/api/projects", content="name=x", headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert r.status_code == 415


# ---------- sqlite 모드는 그대로 ----------


def test_sqlite_mode_needs_no_login(repo):
    main.app.dependency_overrides[deps.get_repo] = lambda: repo
    try:
        with TestClient(main.app) as c:
            assert c.get("/api/auth/me").json() == {"auth_required": False, "user": None}
            assert c.get("/api/projects").status_code == 200
            assert c.post("/api/auth/login", json=GOOD).status_code == 400
    finally:
        main.app.dependency_overrides.clear()
