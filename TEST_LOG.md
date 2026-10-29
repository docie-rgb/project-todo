# 검증 기록 (TEST_LOG)

## 1. 길 A — 로컬 SQLite

| 항목 | 값 |
|---|---|
| 검증일 | 2026-10-29 |
| 환경 | Windows 10 Pro, Python 3.11.9, SQLite 3.45.1, FastAPI 0.115.6, uvicorn 0.34.0 |
| 실행 주소 | http://localhost:8000 |
| DB 파일 | `todo.db` (프로젝트 루트, Git 제외) |
| 기준 커밋 | `444cdda` (Step 3-4: frontend UI) |

### 1-1. 자동 테스트

```
.venv/Scripts/python -m pytest
39 passed
```

- `tests/test_repository.py` (32개): 이름 trim·중복(대소문자/공백 무시)·빈 이름 거부, 프로젝트 삭제 시 할 일 미분류 이동,
  없는 프로젝트 연결 거부, 마감일 형식 검증, 마감일순 정렬(NULL 뒤), 스키마 CHECK/UNIQUE 직접 검증, 재오픈 후 데이터 유지
- `tests/test_api.py` (7개): 프로젝트·할 일 CRUD, 오류 코드(400/404/409/422), `user_id` 등 허용되지 않은 필드 거부,
  백엔드 코드·DB 파일이 정적 경로로 노출되지 않음

테스트는 임시 DB 파일을 사용하며 실제 `todo.db` 에는 영향을 주지 않는다.

### 1-2. 기능 검증 (브라우저)

| # | 확인 항목 | 결과 | 확인 방법 / 증거 |
|---|---|---|---|
| 1 | 브라우저에서 localhost 로 접속 | ✅ | `http://127.0.0.1:8000` 접속, `/api/health` = `{"status":"ok"}` |
| 2 | 프로젝트와 할 일 추가 | ✅ | 프로젝트 "기말 과제" 생성 후 할 일 3건 등록 — `01-before-restart.jpg` |
| 3 | 저장한 할 일이 목록에 표시 | ✅ | 등록 즉시 목록·개수(0/3) 갱신 — `01-before-restart.jpg` |
| 4 | 할 일 제목·마감일 수정 | ✅ | "API 구현" → "API 구현 및 테스트", 마감 2026-11-05 → 2026-11-01 — `07-edit-mode.jpg` |
| 5 | 완료 상태 변경 | ✅ | 체크 시 취소선·"완료" 배지, 개수 1/3, 마감 지남 강조 해제 — `01-before-restart.jpg` |
| 6 | 할 일 삭제 | ✅ | 확인 창 후 삭제, 미분류 개수 1/4 → 1/3 |
| 7 | 미분류 할 일 관리 | ✅ | 미분류에 직접 등록, 프로젝트 할 일을 미분류로 이동, 프로젝트 삭제 시 소속 2건 미분류 이동 — `04-unassigned-todos.jpg`, `06-project-deleted-todos-unassigned.jpg` |
| 8 | 브라우저 새로고침 후 유지 | ✅ | 새로고침 전후 화면 동일 — `02-after-refresh.jpg` |
| 9 | 서버 완전 종료·재시작 후 유지 | ✅ | 아래 1-3 절차, 재시작 전후 API 응답 완전 일치 — `03-after-server-restart.jpg` |
| 10 | `todo.db` 에 실제 저장 | ✅ | 아래 1-4, 읽기 전용으로 직접 조회 |

추가 확인:

| 확인 항목 | 결과 | 증거 |
|---|---|---|
| 프로젝트 이름 중복 거부 (`" STRING "` ↔ 기존 `string`) | ✅ HTTP 409, 화면 알림 | `05-duplicate-name-rejected.jpg` |
| 프로젝트 이름 수정 | ✅ "웹개발 과제" → "웹개발" | — |
| 마감 지난 미완료 업무 시각 구분 | ✅ 빨간 배경 + "(N일 지남)" | `01-before-restart.jpg` |
| 마감일순 정렬 | ✅ 마감일 빠른 순, 마감일 없음은 맨 뒤 | 자동 테스트 + 화면 |
| 좁은 화면(375px) 레이아웃 | ✅ 세로 배치, 가로 스크롤 없음 | — |
| Swagger UI(`/docs`)에서 중복 이름 409 | ✅ 사용자 직접 확인 | — |

### 1-3. 서버 완전 종료 후 재시작 절차

| 시각 | 동작 | 결과 |
|---|---|---|
| 18:25 | 재시작 전 전체 데이터 스냅숏 저장 (`/api/projects`, 미분류·프로젝트별 `/api/todos`) | 프로젝트 2, 미분류 할 일 4, 프로젝트 할 일 3 |
| 18:26:12 | uvicorn 프로세스 종료 | `/api/health` 연결 거부, 8000 포트 LISTEN 없음 |
| 18:26:26 | 서버 재시작 | `/api/health` 정상 |
| 18:26 | 같은 API를 다시 조회해 스냅숏과 비교 | **완전 일치 (True)** |
| 18:26 | 브라우저 새로 접속 | 재시작 전 화면과 동일 (`03-after-server-restart.jpg`) |

### 1-4. `todo.db` 직접 조회 결과 (읽기 전용)

```
tables/indexes: projects, todos, ix_todos_project_id, ux_projects_name_ci
-- projects
('bfc8207d-…', 'string',    '2026-10-29T09:08:40.199Z')
('90315b8c-…', '기말 과제', '2026-10-29T09:25:30.581Z')
-- todos (id 앞 8자리, project_id 앞 8자리, title, is_done, due_date)
('b434e9f7', NULL,       'ERD 작성',            1, '2026-10-20')
('6afd208a', NULL,       'API 구현 및 테스트',  0, '2026-11-01')
('edd0153e', NULL,       'README 정리',         0, None)
('59a217ad', NULL,       '감자',                0, '2026-10-14')
('6bfc872a', '90315b8c', 'PRD 제출',            0, '2026-10-27')
('1a35df81', '90315b8c', '로컬 저장 테스트',    1, '2026-11-05')
('e2b87519', '90315b8c', 'Supabase 전환 준비',  0, None)
foreign_key_check: [] | integrity_check: ok
```

- ID는 모두 UUID v4 문자열, 미분류 할 일은 `project_id = NULL`, 완료 여부는 0/1 로 저장됨 (DB_DESIGN §2 와 일치).

### 1-5. 발견된 문제

| 문제 | 원인 | 조치 |
|---|---|---|
| 검증 스크립트 출력에서 한글 깨짐 | Windows 콘솔 인코딩(cp949) 표시 문제, 서버 응답은 정상 UTF-8 | 출력 시 `PYTHONIOENCODING=utf-8` 사용 |
| 테스트 시 `DeprecationWarning` 1건 | 외부 라이브러리(starlette TestClient) 내부 경고 | 동작 영향 없음, 조치 불필요 |

### 1-6. 스크린샷

`docs/screenshots/`

| 파일 | 내용 |
|---|---|
| `01-before-restart.jpg` | 프로젝트·할 일 등록, 완료·마감 지남 표시 |
| `02-after-refresh.jpg` | 새로고침 후 |
| `03-after-server-restart.jpg` | 서버 완전 종료·재시작 후 |
| `04-unassigned-todos.jpg` | 미분류 할 일 목록 |
| `05-duplicate-name-rejected.jpg` | 프로젝트 이름 중복 거부 알림 |
| `06-project-deleted-todos-unassigned.jpg` | 프로젝트 삭제 후 할 일이 미분류로 이동 |
| `07-edit-mode.jpg` | 할 일 수정 모드 |

`02-after-refresh.jpg` 와 `03-after-server-restart.jpg` 는 화면이 같아 파일 내용도 동일하다. 화면만으로는 재시작 여부를 구분할 수 없으므로, 재시작 사실과 데이터 유지는 1-3 의 절차(프로세스 종료·포트 확인·재시작 전후 API 응답 완전 일치)로 입증한다.

## 2. 길 B — Supabase

| 항목 | 값 |
|---|---|
| 검증일 | 2026-10-29 |
| 구성 | 화면·백엔드는 로컬(FastAPI, http://localhost:8000), 데이터는 Supabase(PostgreSQL, Free 플랜) |
| DB 접근 | Supabase REST(`/rest/v1`) + publishable 키 + **로그인 사용자의 액세스 토큰** → DB에서 RLS 적용. secret/service_role 키 미사용 |
| 인증 | Supabase Auth 이메일·비밀번호, 토큰은 HttpOnly 쿠키(`pt_access` Path=/api Lax, `pt_refresh` Path=/api/auth Strict) |
| 테스트 계정 | 대시보드에서 만든 A·B (Auto Confirm, 테스트 전용 주소) — 개인정보는 기록하지 않음 |

### 2-1. SQLite → Supabase 전환 기록

| 단계 | 내용 | 커밋 |
|---|---|---|
| B1 | `supabase/schema.sql`: 테이블 2개(UUID PK, 양쪽 `user_id default auth.uid()`, `project_id` NULL 허용), `(user_id, lower(name))` 유니크, 복합 FK `(project_id, user_id) → projects(id, user_id) ON DELETE SET NULL (project_id)`, 권한 REVOKE/GRANT, RLS 정책 8개 | `1d017a1` |
| B2 | `SupabaseRepository`: 기존 Repository 인터페이스 그대로 구현, `DB_BACKEND` 로 SQLite/Supabase 선택 | `1d017a1` |
| B3 | 로그인·로그아웃·토큰 갱신 API, HttpOnly 쿠키, Origin 검사·JSON 전용(CSRF 방어), 로그인 화면 | `0e1db9b` |
| B4·B5 | RLS 실제 검증, 클라우드 영속성 검증 (`scripts/rls_check.py`, `scripts/cloud_persistence.py`) | (이번 커밋) |

- 기존 API 경로 8개와 화면 기능은 그대로이고 `/api/auth/*` 3+1개만 추가되었다.
- SQLite 모드(`DB_BACKEND=sqlite`)는 로그인 없이 기존대로 동작하며 `todo.db` 는 변경되지 않았다 (프로젝트 2, 할 일 7 유지).

### 2-2. Supabase 테이블 생성·연결 확인

| 확인 | 결과 | 의미 |
|---|---|---|
| `.env` 변수 8개 설정 여부 (값 비공개) | ✅ 모두 설정, 키 종류 = publishable | secret 키가 아님 |
| 서버 `/api/health` | `{"db_backend":"supabase"}` | Supabase 모드로 실행 |
| 비로그인 REST `GET /projects`, `GET /todos` | `401`, `42501 permission denied for table …` | 테이블이 존재(schema.sql 실행됨)하고 anon 권한이 회수됨 |
| 이메일 로그인 공급자 | 활성화 | — |
| 앱으로 생성한 행이 DB에 저장 | ✅ (2-5 참조) | — |

### 2-3. RLS 활성화 및 정책

`supabase/schema.sql` 로 적용 (SQL Editor 에서 사용자가 직접 실행).

| 테이블 | RLS | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|---|
| projects | 활성화 | USING `user_id = auth.uid()` | WITH CHECK `user_id = auth.uid()` | USING + WITH CHECK 동일 조건 | USING 동일 조건 |
| todos | 활성화 | 〃 | 〃 | 〃 | 〃 |

- 모든 정책은 `to authenticated` 만 대상, `anon` 은 테이블 권한(GRANT) 자체가 없음.
- 다른 사용자의 프로젝트 연결은 정책이 아니라 **복합 외래키**가 차단.
- 정책·권한 상세는 `supabase/verify.sql` 로 SQL Editor 에서 조회 가능 (스크린샷 대상).

### 2-4. A/B 계정 접근 권한 테스트 — `scripts/rls_check.py`

2026-10-29 21:27 실행, **26개 중 26개 통과**. 전체 표: [`docs/rls_check_result.md`](docs/rls_check_result.md)

- **DB 직접**: 우리 백엔드를 거치지 않고 Supabase REST 에 A·B 각자의 일반 사용자 토큰으로 요청 → Python 필터가 아닌 DB 의 RLS·제약조건이 막는지 확인.
- **앱 API**: 같은 시나리오를 로컬 서버(supabase 모드)에 쿠키 로그인으로 요청.

| # | 시나리오 | DB 직접 결과 | 앱 API 결과 |
|---|---|---|---|
| 1 | A 가 프로젝트·할 일(프로젝트 소속 + 미분류) 생성 | 201, `user_id` 가 DB 기본값으로 A 가 됨 | — |
| 2 | A 가 자기 데이터 조회 | 프로젝트 1, 할 일 2 | — |
| 3 | B 의 목록에 A 데이터 | 0건 노출 | 0건 |
| 4 | B 가 A 의 할 일 ID 로 직접 조회 (미분류 포함) | 200, 0건 | 200, 0건 |
| 5 | B 가 A 의 할 일·프로젝트 수정 | 200, 변경 0건 | 404 |
| 6 | B 가 A 의 할 일·프로젝트 삭제 | 200, 삭제 0건 | 404 |
| 7 | B 가 A 의 프로젝트로 할 일 생성 / 자기 할 일을 이동 | 409, `23503` (복합 FK) | 422 |
| 7 | B 가 `user_id = A` 로 생성 / 자기 할 일을 A 소유로 변경 | 403, `42501` (RLS WITH CHECK) | `user_id` 입력 자체 422 |
| 8 | 차단 이후 A 의 원본 | 제목·완료·소속 변화 없음 | 원본 그대로 |
| 9 | 비로그인 조회·생성 | 401, `42501` | 401 |

- 거부 방식이 "오류"가 아니라 "0건"인 경우(4~6)는 RLS USING 이 남의 행을 보이지 않게 하기 때문이며, 8번에서 실제 데이터가 바뀌지 않았음을 다시 조회해 확인했다.
- 검증용 행은 스크립트가 삭제했고, 이후 A·B 각각 남은 검증 행 0건을 확인했다.

### 2-5. 클라우드 데이터 영속성 — `scripts/cloud_persistence.py`

결과 파일: [`docs/cloud_persistence_result.md`](docs/cloud_persistence_result.md)

| 시각 | 동작 | 결과 |
|---|---|---|
| 21:28:04 | 앱 API 로 A 로그인 → 프로젝트 `B5 영속성 확인` + 할 일 4건 생성 → 1건 완료, 1건 삭제 | 201 / 200 / 204 |
| 21:28 | 앱을 거치지 않고 Supabase REST 로 직접 조회 | 완료 `is_done=true` 반영, 삭제 행 없음, 미분류 `project_id=NULL` |
| 21:28 | 스냅숏 저장 | 프로젝트 1, 할 일 3 |
| 21:28:21 | 로컬 FastAPI 서버 완전 종료 | `/api/health` 연결 거부, 8000 포트 LISTEN 없음 |
| 21:28:32 | 서버 재시작 | supabase 모드 정상 |
| 21:28:36 | **재로그인**(새 세션) 후 조회해 스냅숏과 비교 | **완전 일치** |

- 이 데이터(`B5 영속성 확인`)는 Table Editor 확인용으로 A 계정에 남겨 두었다.

### 2-6. SQLite 회귀 테스트

```
.venv/Scripts/python -m pytest
71 passed
```

- 기존 SQLite 테스트 39개 + Supabase 저장소 18개(HTTP 가짜 응답) + 인증·쿠키·CSRF 14개(가짜 인증 서버).
- 자동 테스트는 실제 Supabase 에 접속하지 않는다. 실제 RLS 는 2-4 에서 검증.

### 2-7. 발견된 문제와 해결

| 문제 | 원인 | 해결 |
|---|---|---|
| 서버가 계속 sqlite 모드로 시작 | `.env` 파일이 없었음 | `.env.example` 기반으로 `.env` 생성(비밀값은 사용자가 입력) |
| 테스트 계정 A·B 로그인 실패 `invalid_credentials` | 계정이 비밀번호 없이 생성된 것으로 추정 (Supabase 는 계정 없음·비밀번호 오류를 같은 코드로 응답) | 대시보드 **Create new user + Auto Confirm** 으로 재생성 후 로그인 성공 |
| `.env` 생성 후 테스트 7개 실패 | 테스트가 로컬 `.env` 의 `DB_BACKEND=supabase` 를 읽음 | `tests/conftest.py` 에서 테스트는 항상 sqlite 모드로 시작하도록 격리 |

### 2-8. Supabase 모드 작동 화면 (브라우저)

2026-10-29 21:44~21:48. 사용자가 앱 안 브라우저에서 직접 로그인(계정 B, 테스트용 주소)했고, 이후 조작·캡처는 AI가 수행했다. 서버 종료(21:47:56)·재시작(21:48:18) 외의 시각은 분 단위 근사치다.

| 시각 | 동작 | 결과 | 화면 |
|---|---|---|---|
| 21:44 | 계정 B 로그인 직후 | 프로젝트 0개, 할 일 0건 — 계정 A 의 `B5 영속성 확인` 이 보이지 않음 | `11-supabase-b-cannot-see-a.jpg` |
| 21:45 | 프로젝트 `클라우드 과제` + 할 일 3건 등록 | 목록·개수(0/3) 표시 | `12-supabase-saved.jpg` |
| 21:46 | `완료 체크 확인` 완료 처리 | 취소선·"완료" 배지, 개수 1/3 | `13-supabase-completed.jpg` |
| 21:47 | `삭제 확인용 할 일` 삭제 | 개수 1/2 | `14-supabase-deleted.jpg` |
| 21:47 | 앱을 거치지 않고 Supabase REST 를 B 의 토큰으로 직접 조회 | `완료 체크 확인` is_done=true, `삭제 확인용 할 일` 0행 | — |
| 21:47:56 | 로컬 FastAPI 서버 종료 | `/api/health` 연결 거부, 8000 포트 LISTEN 없음. 브라우저 새로고침 시 데이터 없음 | `15-supabase-server-stopped.jpg` |
| 21:48:18 | 서버 재시작 후 브라우저 새로고침 | 완료·삭제 상태 그대로 2건 표시 | `16-supabase-after-restart.jpg` |

- 재시작 후에는 브라우저에 남아 있던 세션 쿠키로 접속했으며 **재로그인은 하지 않았다.** 새 세션(재로그인) 후 데이터 유지는 2-5 에서 별도로 확인했다.
- 할 일 등록 중 응답 지연으로 자동 조작의 등록 요청이 한 번 더 처리되어 같은 제목의 할 일이 1건 중복 생성되었고, 캡처 전에 삭제했다.

## 3. Render 배포 준비

[`DEPLOY.md`](DEPLOY.md) 참조 (실제 배포는 진행하지 않음).
