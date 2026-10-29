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

## 2. 길 B — Supabase

(Step 3에서 진행 예정: 클라우드 CRUD·영속성, RLS 조회/추가/수정/삭제별 검증)
