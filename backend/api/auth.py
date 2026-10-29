"""로그인·로그아웃·토큰 갱신·로그인 상태 확인 API. 응답 본문에는 토큰을 절대 넣지 않는다."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from backend import domain
from backend.api.cookies import ACCESS_COOKIE, REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from backend.api.deps import auth_required, get_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: str


def _require_supabase_mode() -> None:
    if not auth_required():
        raise domain.ValidationError("로컬(sqlite) 모드에서는 로그인이 필요하지 않습니다.")


@router.get("/me")
def me(request: Request, response: Response):
    """화면이 처음 열릴 때 호출: 로그인이 필요한 모드인지, 지금 누구로 로그인되어 있는지.

    액세스 토큰이 만료됐어도 리프레시 쿠키(이 경로에 전송됨)가 유효하면 조용히 갱신한다.
    """
    if not auth_required():
        return {"auth_required": False, "user": None}
    auth = get_auth()
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        try:
            user = auth.get_user(token)
            return {"auth_required": True, "user": {"email": user.email}}
        except domain.Unauthorized:
            pass
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        try:
            session = auth.refresh(refresh_token)
            set_session_cookies(response, session)
            return {"auth_required": True, "user": {"email": session.email}}
        except domain.Unauthorized:
            clear_session_cookies(response)
    return {"auth_required": True, "user": None}


@router.post("/login")
def login(body: LoginIn, response: Response):
    _require_supabase_mode()
    session = get_auth().sign_in(body.email.strip(), body.password)
    set_session_cookies(response, session)
    return {"user": {"email": session.email}}


@router.post("/refresh")
def refresh(request: Request, response: Response):
    """액세스 토큰 만료(401) 시 화면이 호출한다. 리프레시 토큰을 새 토큰 한 쌍으로 교환한다."""
    _require_supabase_mode()
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise domain.Unauthorized()
    try:
        session = get_auth().refresh(refresh_token)
    except domain.Unauthorized:
        # 쿠키를 지운 응답을 직접 돌려준다 (예외로 끝내면 쿠키 삭제가 적용되지 않는다).
        expired = JSONResponse(status_code=401, content={"detail": "로그인이 만료되었습니다. 다시 로그인하세요."})
        clear_session_cookies(expired)
        return expired
    set_session_cookies(response, session)
    return {"user": {"email": session.email}}


@router.post("/logout", status_code=204)
def logout(request: Request):
    """Supabase 세션을 끝내고(리프레시 토큰 무효화) 쿠키를 지운다. Supabase 호출이 실패해도 쿠키는 지운다."""
    _require_supabase_mode()
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        try:
            get_auth().sign_out(token)
        except domain.DomainError:
            pass
    response = Response(status_code=204)
    clear_session_cookies(response)
    return response
