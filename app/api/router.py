"""Aggregates every feature router. Add new routers here only."""

from fastapi import APIRouter

from app.api.routes import admin, auth, games, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(games.router)
