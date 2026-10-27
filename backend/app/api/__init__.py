from fastapi import APIRouter

from app.api import evidence, health, reports, samples

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(reports.router)
api_router.include_router(evidence.router)
api_router.include_router(samples.router)
