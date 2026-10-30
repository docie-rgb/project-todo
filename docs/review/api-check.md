# API 직접 확인 (로컬 SQLite 모드)

리뷰어가 2026-10-30 로컬에서 서버를 띄우고 요청을 보낸 결과.

## 1. 입력 검사

| 요청 | HTTP | 응답 | 비고 |
|---|---|---|---|
| 제목 5000자 (화면은 maxlength=200) | 201 | - | **저장된 제목 길이 5000자** |
| (확인용 행 삭제) | 204 | | |
| 공백뿐인 제목 | 400 | `{"detail":"할 일 제목을 입력하세요."}` |  |
| 없는 날짜 2026-02-30 | 400 | `{"detail":"존재하지 않는 날짜입니다."}` |  |
| user_id 필드 포함 | 422 | `{"detail":[{"type":"extra_forbidden","loc":["body","user_id"],"msg":"Extra input…` | 정의되지 않은 필드 거부 |
| 없는 ID `abc` 수정 | 404 | `{"detail":"할 일을 찾을 수 없습니다."}` |  |

## 2. CSRF 방어

| 요청 | HTTP | 응답 | 비고 |
|---|---|---|---|
| 다른 출처 Origin: https://evil.example | 403 | `{"detail":"허용되지 않은 출처의 요청입니다."}` |  |
| HTML 폼 형식(urlencoded) | 415 | `{"detail":"JSON 형식의 요청만 허용됩니다."}` |  |

## 3. 정적 경로로 내부 파일 노출

| 요청 | HTTP | 응답 | 비고 |
|---|---|---|---|
| GET /todo.db | 404 | - |  |
| GET /.env | 404 | - |  |
| GET /backend/config.py | 404 | - |  |
| GET /requirements.txt | 404 | - |  |

## 4. 응답 헤더 (보안 헤더 유무)

- `server`: uvicorn
- `x-content-type-options`: (없음)
- `x-frame-options`: (없음)
- `content-security-policy`: (없음)
