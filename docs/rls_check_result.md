# RLS 검증 결과 (scripts/rls_check.py 자동 생성)

- 실행 시각: 2026-10-29 21:27:01
- 권한: 테스트 계정 A·B 의 일반 사용자 토큰 (관리자 키 사용 안 함)
- 개인정보·토큰은 기록하지 않음

| 구분 | 항목 | 결과 | 근거 |
|---|---|---|---|
| 준비 | A·B 로그인 (일반 사용자 토큰 발급) | ✅ PASS | 서로 다른 사용자 2명 |
| DB 직접 | 1. A 프로젝트 생성 | ✅ PASS | HTTP 201 |
| DB 직접 | 1. A 할 일 생성 (프로젝트 + 미분류) | ✅ PASS | HTTP 201, 201 |
| DB 직접 | 1. user_id 자동 입력 (요청 본문에 user_id 없음) | ✅ PASS | DB 기본값 auth.uid() 가 A 로 채움 |
| DB 직접 | 2. A 가 자기 프로젝트·할 일 조회 | ✅ PASS | 프로젝트 1건, 할 일 2건 |
| DB 직접 | 3. B 의 전체 목록에 A 데이터 없음 | ✅ PASS | A 의 행 0건 노출 |
| DB 직접 | 4. B 가 A 의 할 일 ID 로 직접 조회 (미분류 포함) | ✅ PASS | HTTP 200, 0건 |
| DB 직접 | 5. B 가 A 의 할 일 수정 | ✅ PASS | HTTP 200, 변경 0건 |
| DB 직접 | 5. B 가 A 의 프로젝트 이름 수정 | ✅ PASS | HTTP 200, 변경 0건 |
| DB 직접 | 6. B 가 A 의 할 일 삭제 (미분류 포함) | ✅ PASS | HTTP 200, 삭제 0건 |
| DB 직접 | 6. B 가 A 의 프로젝트 삭제 | ✅ PASS | HTTP 200, 삭제 0건 |
| DB 직접 | 7. B 가 A 의 프로젝트로 할 일 생성 | ✅ PASS | HTTP 409, code=23503 (복합 외래키) |
| DB 직접 | 7. B 가 자기 할 일을 A 의 프로젝트로 이동 | ✅ PASS | HTTP 409, code=23503 (복합 외래키) |
| DB 직접 | 7. B 가 user_id=A 로 행 생성 | ✅ PASS | HTTP 403, code=42501 (RLS WITH CHECK) |
| DB 직접 | 7. B 가 자기 할 일을 A 소유로 변경 | ✅ PASS | HTTP 403, code=42501 (RLS WITH CHECK) |
| DB 직접 | 8. 차단 이후 A 의 원본 데이터 그대로 | ✅ PASS | 프로젝트 1건, 할 일 2건, 제목·완료·소속 변화 없음=True |
| DB 직접 | 9. 비로그인(publishable 키만) 조회·생성 | ✅ PASS | GET todos 401/42501, GET projects 401/42501, POST 401/42501 |
| 앱 API | 9. 비로그인으로 /api/projects | ✅ PASS | HTTP 401 |
| 앱 API | B 로그인 (HttpOnly 쿠키) | ✅ PASS | HTTP 200 |
| 앱 API | 3. B 의 프로젝트 목록에 A 프로젝트 없음 | ✅ PASS | 0개 중 A 것 0개 |
| 앱 API | 4. B 가 A 의 프로젝트 할 일 조회 | ✅ PASS | HTTP 200, 0건 |
| 앱 API | 5. B 가 A 의 할 일 수정 | ✅ PASS | HTTP 404 |
| 앱 API | 6. B 가 A 의 할 일 삭제 | ✅ PASS | HTTP 404 |
| 앱 API | 7. B 가 A 의 프로젝트로 할 일 생성 | ✅ PASS | HTTP 422 |
| 앱 API | 7. B 가 user_id 를 직접 보냄 | ✅ PASS | HTTP 422 (입력 단계에서 거부) |
| 앱 API | 8. A 로 다시 조회 시 원본 그대로 | ✅ PASS | 1건 |
