from fastapi import APIRouter

from app.api.routes import health, login, qa

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(login.router, tags=["login"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])
