from fastapi import APIRouter

from app.api.routes import auth, companies, health, qa, watchlist

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(companies.router, tags=["companies"])
api_router.include_router(watchlist.router, tags=["watchlist"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])
