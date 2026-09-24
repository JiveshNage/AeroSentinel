from fastapi import APIRouter
from api.routes.health import router as health_router
from ingestion.routes import router as ingestion_router
from alerts.routes import router as alerts_router, feedback_router
from api.routes.stations import router as stations_router
from retrain.routes import router as retrain_router
from maintenance.routes import router as maintenance_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(ingestion_router, tags=["Ingestion"])
api_router.include_router(alerts_router)
api_router.include_router(feedback_router)
api_router.include_router(stations_router)
api_router.include_router(retrain_router)
api_router.include_router(maintenance_router)
