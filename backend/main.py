from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from api.router import api_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AeroSentinel — AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations (AWS) sensor data (SIH26073)",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

from storage.db import check_db_connection

# Production-safe CORS middleware
cors_list = (
    settings.CORS_ORIGINS
    if isinstance(settings.CORS_ORIGINS, list)
    else [o.strip() for o in str(settings.CORS_ORIGINS).split(",") if o.strip()]
)
if "*" in cors_list or not cors_list:
    cors_list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def root_health():
    """Production health check endpoint verifying database connectivity."""
    db_ok, _ = check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

from ingestion.routes import router as ingestion_router

# Include API router under API_V1_STR (default /api)
app.include_router(api_router, prefix=settings.API_V1_STR)
# Also include direct /ingest route matching architecture.md gateway spec
app.include_router(ingestion_router)


from pathlib import Path
from fastapi.responses import FileResponse

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

@app.api_route("/api/docs/download/manual", methods=["GET", "HEAD"], tags=["Documentation"])
async def download_user_manual():
    pdf_path = DOCS_DIR / "AeroSentinel_User_Manual.pdf"
    if not pdf_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User manual PDF not found")
    return FileResponse(
        path=str(pdf_path),
        filename="AeroSentinel_User_Manual.pdf",
        media_type="application/pdf",
    )

@app.api_route("/api/docs/download/spec", methods=["GET", "HEAD"], tags=["Documentation"])
async def download_technical_spec():
    pdf_path = DOCS_DIR / "AeroSentinel_Technical_Product_Spec.pdf"
    if not pdf_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Technical specification PDF not found")
    return FileResponse(
        path=str(pdf_path),
        filename="AeroSentinel_Technical_Product_Spec.pdf",
        media_type="application/pdf",
    )

@app.get("/", tags=["Root"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
        "user_manual_pdf": "/api/docs/download/manual",
        "technical_spec_pdf": "/api/docs/download/spec",
    }
