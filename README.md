# Project Todo

여러 프로젝트의 할 일을 나눠 관리하는 웹 Todo 앱. 현재는 **길 A: 로컬 SQLite** 버전이다.

- 요구사항: [PRD.md](PRD.md)
- DB 설계: [DB_DESIGN.md](DB_DESIGN.md)
- 검증 기록: [TEST_LOG.md](TEST_LOG.md)

## 기능

- 프로젝트 생성·이름 수정·삭제 (삭제 시 소속 할 일은 미분류로 이동)
- 프로젝트 이름 중복 금지 (앞뒤 공백 제거, 영문 대소문자 무시)
- 할 일 등록·조회·수정·삭제, 완료 체크
- 미분류 할 일 (프로젝트 없이 등록, 프로젝트 배정 / 미분류로 변경)
- 마감일 (선택), 마감 지난 미완료 업무 빨간 표시, 마감일순 정렬
- 프로젝트별·미분류 전체/완료 개수 표시

## 구조

```
브라우저 (frontend/)  ──fetch /api/*──▶  FastAPI (backend/api)  ──▶  Repository  ──▶  todo.db
```

| 경로 | 역할 |
|---|---|
| `frontend/` | HTML·CSS·JS 화면. `api.js` 만 서버와 통신하며 DB를 모른다 |
| `backend/api/` | REST API 라우터, 의존성(저장소·현재 사용자) |
| `backend/domain.py` | DB와 무관한 업무 규칙(입력 정규화, 오류) |
| `backend/repositories/` | 저장소 인터페이스(`base.py`)와 SQLite 구현(`sqlite_repo.py`, SQL은 여기에만) |
| `backend/db/` | `schema.sql`, SQLite 연결·초기화 |
| `tests/` | pytest 테스트 |

`todo.db` 는 서버 첫 실행 시 자동 생성되며, `frontend/` 밖에 있어 브라우저에서 내려받을 수 없다.

## 실행 방법 (Windows)

준비물: Python 3.11 이상. 모든 패키지는 프로젝트 안의 `.venv` 에만 설치된다.

1) 가상환경 생성 (최초 1회)

```bash
python -m venv .venv
```

2) 패키지 설치 (최초 1회)

```bash
.venv/Scripts/python -m pip install -r requirements.txt -r requirements-dev.txt
```

3) (선택) 설정 파일 — 기본값으로 충분하면 생략 가능

```bash
cp .env.example .env
```

4) 서버 실행 후 브라우저에서 http://localhost:8000 접속 (종료: `Ctrl + C`)

```bash
.venv/Scripts/python -m uvicorn backend.main:app --port 8000
```

API 문서(Swagger UI): http://localhost:8000/docs

5) 테스트

```bash
.venv/Scripts/python -m pytest
```

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/projects` | 프로젝트 목록 + 개수, 미분류 개수 |
| POST | `/api/projects` | `{"name": "..."}` 생성 (중복 409) |
| PATCH | `/api/projects/{id}` | 이름 수정 |
| DELETE | `/api/projects/{id}` | 삭제 (할 일은 미분류로) |
| GET | `/api/todos?project={id}\|unassigned&sort=created\|due` | 할 일 목록 |
| POST | `/api/todos` | `{"title", "project_id"?, "due_date"?}` 생성 |
| PATCH | `/api/todos/{id}` | 보낸 필드만 수정 (`project_id`/`due_date` 에 `null` = 미분류/마감일 제거) |
| DELETE | `/api/todos/{id}` | 삭제 |

## todo.db 직접 확인하기

**DB Browser for SQLite** (무료, https://sqlitebrowser.org)

1. 설치 후 실행 → **Open Database** 클릭
2. 파일 선택 창 아래쪽의 **Read Only** 를 체크하고 `todo.db` 선택
   (서버 실행 중 쓰기 모드로 열면 잠금 충돌이 날 수 있다)
3. **Database Structure** 탭: `projects`, `todos` 테이블과 인덱스 확인
4. **Browse Data** 탭: Table 에서 `projects` / `todos` 를 골라 저장된 행 확인
5. **Execute SQL** 탭 예시:

```sql
SELECT p.name, t.title, t.is_done, t.due_date
FROM todos t LEFT JOIN projects p ON p.id = t.project_id
ORDER BY p.name, t.due_date;
```

앱에서 데이터를 바꾼 뒤에는 DB Browser 에서 `F5`(새로고침)로 다시 읽는다.

대안: VS Code 확장 **SQLite Viewer** 설치 후 `todo.db` 클릭.

## 보안·Git

- `.env`, `todo.db`, `.venv/` 는 `.gitignore` 로 제외된다.
- 클라이언트가 보낸 `user_id` 는 받지 않는다(422). Step 3에서는 서버가 Supabase 로그인 토큰으로 사용자를 확인한다.
