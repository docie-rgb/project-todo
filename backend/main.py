"""FastAPI 진입점: /api/* 는 JSON API, 그 외 경로는 frontend/ 정적 파일."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import config, domain
from backend.api import projects, todos
from backend.api.deps import get_repo


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_repo()  # 시작 시 DB 연결 확인 및 스키마 생성 (todo.db 가 없으면 만든다)
    yield


app = FastAPI(title="Project Todo API", lifespan=lifespan)

_STATUS = {
    domain.ValidationError: 400,
    domain.NotFound: 404,
    domain.DuplicateProjectName: 409,
    domain.InvalidProject: 422,
}


@app.exception_handler(domain.DomainError)
async def domain_error_handler(request: Request, exc: domain.DomainError):
    return JSONResponse(status_code=_STATUS.get(type(exc), 400), content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"status": "ok", "db_backend": config.DB_BACKEND}


app.include_router(projects.router)
app.include_router(todos.router)

# 반드시 API 라우터 등록 뒤에 마운트한다 (먼저 마운트하면 /api 요청을 가로챈다).
# frontend/ 만 공개하므로 todo.db·backend/ 코드는 브라우저에서 접근할 수 없다.
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
