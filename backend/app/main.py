from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.main import api_router
from app.auth.errors import AuthError
from app.core.config import settings
from app.core.errors import DomainError


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or str(uuid4())
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    @application.exception_handler(AuthError)
    async def auth_error_handler(
        request: Request,
        error: AuthError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "request_id": request_id},
            headers={"x-request-id": request_id},
        )

    @application.exception_handler(DomainError)
    async def domain_error_handler(
        request: Request,
        error: DomainError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        content: dict[str, Any] = {
            "code": error.code,
            "request_id": request_id,
        }
        if error.details is not None:
            content["details"] = error.details
        return JSONResponse(
            status_code=error.status_code,
            content=content,
            headers={"x-request-id": request_id},
        )

    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/")
    async def root() -> dict[str, Any]:
        return {"name": settings.PROJECT_NAME, "status": "ok"}

    return application
