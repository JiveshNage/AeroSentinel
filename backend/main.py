from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from api.router import api_router
from storage.db import check_db_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Ensures default stations and RBAC data are automatically seeded on startup
    if the database station registry is empty.
    """
    try:
        from storage.db import SessionLocal
        from storage.models import Station
        from storage.seed import seed_database

        with SessionLocal() as db:
            station_count = db.query(Station).count()
            if station_count == 0:
                print("[AeroSentinel] Station registry is empty. Auto-seeding initial stations and RBAC data...")
                seed_database(db)
                print("[AeroSentinel] Database auto-seed completed successfully.")
    except Exception as e:
        print(f"[AeroSentinel] Startup database check/seed notice: {e}")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AeroSentinel — AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations (AWS) sensor data (SIH26073)",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Production-safe CORS middleware
cors_list = (
    settings.CORS_ORIGINS
    if isinstance(settings.CORS_ORIGINS, list)
    else [o.strip().strip("'\"").rstrip("/") for o in str(settings.CORS_ORIGINS).split(",") if o.strip()]
)

# Ensure required production and local development origins are always present
required_origins = [
    "https://aero-sentinel-sandy.vercel.app",
    "https://aerosentinel.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
for origin in required_origins:
    if origin not in cors_list:
        cors_list.append(origin)

# Wildcards cannot be used with allow_credentials=True under CORS specifications
cors_list = [o for o in cors_list if o != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_list,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
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
