from fastapi import APIRouter
from api.routes.health import router as health_router
from ingestion.routes import router as ingestion_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(ingestion_router, tags=["Ingestion"])
