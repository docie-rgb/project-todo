"""FastAPI 진입점: /api/* 는 JSON API, 그 외 경로는 frontend/ 정적 파일."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import config

app = FastAPI(title="Project Todo API")


@app.get("/api/health")
def health():
    return {"status": "ok", "db_backend": config.DB_BACKEND}


# 반드시 API 라우터 등록 뒤에 마운트한다 (먼저 마운트하면 /api 요청을 가로챈다).
# frontend/ 만 공개하므로 todo.db·backend/ 코드는 브라우저에서 접근할 수 없다.
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
