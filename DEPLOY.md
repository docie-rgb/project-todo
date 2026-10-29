# Render 배포 준비 (문서만, 실제 배포는 하지 않음)

FastAPI 백엔드와 화면(`frontend/`)을 Render Web Service 하나로 올리고, 데이터는 Supabase 를 쓰는 구성이다.

```
브라우저 ──HTTPS──▶ Render (FastAPI + frontend/) ──HTTPS──▶ Supabase (Auth + PostgreSQL/RLS)
```

## 1. GitHub 에 보관할 코드 범위

| 올림 | 올리지 않음 (`.gitignore`) |
|---|---|
| `backend/`, `frontend/`, `supabase/`, `scripts/`, `tests/` | `.env` (URL·키·테스트 계정 비밀번호) |
| `requirements.txt`, `requirements-dev.txt`, `.env.example` | `todo.db` (로컬 데이터) |
| `README.md`, `PRD.md`, `DB_DESIGN.md`, `TEST_LOG.md`, `DEPLOY.md`, `LEARNING_NOTES.md`, `docs/` | `.venv/`, `__pycache__/`, `.pytest_cache/` |

Push 전 확인:

```bash
git ls-files
```

```bash
git grep -nE "sb_secret_|service_role|eyJ[A-Za-z0-9_-]{20,}"
```

첫 명령 결과에 `.env`·`todo.db` 가 없고, 두 번째 명령 결과가 비어 있어야 한다.

## 2. 환경변수 (Render → 서비스 → Environment)

| 이름 | 값 | 비고 |
|---|---|---|
| `DB_BACKEND` | `supabase` | Render 디스크는 재배포·재시작 시 지워지므로 sqlite 모드로 운영하면 데이터가 사라진다 |
| `SUPABASE_URL` | `https://<프로젝트>.supabase.co` | |
| `SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_...` | **secret / service_role 키는 넣지 않는다** (RLS 우회) |
| `COOKIE_SECURE` | `true` | HTTPS 에서만 세션 쿠키 전송 |
| `ALLOWED_ORIGINS` | (비워 둠) | 앱과 같은 주소의 요청은 자동 허용. 다른 도메인을 붙일 때만 `https://도메인` 추가 |
| `PYTHON_VERSION` | `3.11.9` | 로컬과 같은 버전 |

`RLS_TEST_*` 테스트 계정 변수는 서버에 넣지 않는다 (검증 스크립트 전용).

## 3. 명령

빌드(패키지 설치):

```bash
pip install -r requirements.txt
```

시작:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

- `--host 0.0.0.0`: 외부 접속 허용 (로컬의 `127.0.0.1` 과 다름)
- `$PORT`: Render 가 지정하는 포트

## 4. Render 설정값

| 항목 | 값 |
|---|---|
| 서비스 종류 | Web Service |
| 연결 저장소 / 브랜치 | GitHub 저장소 / `main` |
| Root Directory | (비움, 저장소 루트) |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |
| Region | Singapore (한국에서 가장 가까움) |
| Health Check Path | `/api/health` |
| Auto-Deploy | On (main 에 push 하면 재배포) |

Free 인스턴스는 15분간 요청이 없으면 잠들고, 다음 첫 요청에 약 1분 걸릴 수 있다.

## 5. Supabase 연결 시 주의사항

- **데이터는 Supabase 에만 있다.** Render 서버를 재배포해도 데이터는 유지된다.
- **Free 프로젝트는 1주일간 사용이 없으면 일시 중지**된다. 대시보드에서 Restore 하면 데이터는 그대로다.
- 서버 시작 시 `SUPABASE_URL`/`SUPABASE_PUBLISHABLE_KEY` 가 없으면 즉시 오류로 멈춘다 (로그에서 확인).
- 이메일 로그인만 사용하므로 Authentication → URL Configuration 의 Site URL 은 필수가 아니다. 회원가입·비밀번호 재설정 메일 기능을 추가할 때 Render 주소로 설정한다.
- 테이블·정책을 바꿀 때는 `supabase/schema.sql` 을 고치고 SQL Editor 에서 변경분만 실행한 뒤 `supabase/verify.sql` 로 확인한다.
- 로컬 개발과 배포가 같은 Supabase 프로젝트를 쓰면 데이터도 공유된다. 분리하려면 프로젝트를 하나 더 만들어 Render 환경변수만 바꾼다.

## 6. 인증·보안 주의사항

- **RLS 가 최종 방어선**이다. 백엔드는 `user_id` 로 거르지 않고 사용자 토큰을 DB 에 그대로 전달한다. 정책을 바꾼 뒤에는 반드시 `rls_check.py` 를 다시 돌린다.
- **secret / service_role 키를 서버·코드·GitHub 어디에도 두지 않는다.** 실수로 노출되면 Supabase 대시보드에서 즉시 키를 재발급(rotate)한다.
- `COOKIE_SECURE=true` 로 세션 쿠키가 HTTPS 에서만 전송되게 한다 (Render 는 HTTPS 를 기본 제공).
- 세션 토큰은 HttpOnly 쿠키에만 있고 응답 본문·로그에 남기지 않는다. Render 로그에 토큰·비밀번호를 출력하는 코드를 추가하지 않는다.
- CSRF: SameSite 쿠키 + Origin 검사 + JSON 전용. Render 는 공개 주소를 `Host` 헤더로 전달하므로 같은 출처 검사가 그대로 동작한다.
- 테스트 계정 A·B 는 검증 후 삭제하거나 비밀번호를 바꾼다. 실제 사용자 계정을 테스트에 쓰지 않는다.
- 회원가입 화면이 없으므로 사용자는 Supabase 대시보드에서만 만들어진다. 대시보드에서 "Allow new users to sign up" 을 꺼 두면 외부에서 API 로 가입하는 것도 막을 수 있다.

## 7. 배포 후 정상 작동 확인

1. `https://<앱>.onrender.com/api/health` → `{"status":"ok","db_backend":"supabase"}`
2. 앱 주소 접속 → 로그인 화면 표시, 로그인 없이 `/api/projects` → 401
3. A 로 로그인 → 프로젝트·할 일 추가, 완료 체크, 삭제 → Supabase Table Editor 에 반영 확인
4. 브라우저 개발자도구 → Application → Cookies: `pt_access`·`pt_refresh` 에 **HttpOnly, Secure** 표시
5. 로그아웃 → B 로 로그인 → A 의 데이터가 보이지 않음
6. Render 대시보드에서 **Manual Deploy → Restart** 후 다시 로그인 → 데이터 유지
7. RLS 를 배포 주소로 다시 검증 (로컬 PC 에서, `.env` 의 테스트 계정 사용):

```bash
RLS_CHECK_API_BASE=https://<앱>.onrender.com .venv/Scripts/python -m scripts.rls_check
```

8. `TEST_LOG.md` 에 배포 URL 과 결과를 기록한다.
