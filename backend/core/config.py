from typing import List, Union, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AeroSentinel"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api"

    DATABASE_URL: str = "postgresql+psycopg2://aerosentinel:aerosentinel@localhost:5432/aerosentinel"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "aerosentinel-secret-jwt-key-sih26073-moes-imd"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # Supabase Configuration
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None

    CORS_ORIGINS: Union[str, List[str]] = [
        "https://aero-sentinel-sandy.vercel.app",
        "https://aerosentinel.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        base_origins = [
            "https://aero-sentinel-sandy.vercel.app",
            "https://aerosentinel.vercel.app",
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
        parsed: List[str] = []
        if isinstance(v, str) and not v.startswith("["):
            for item in v.split(","):
                cleaned = item.strip().strip("'\"").rstrip("/")
                if cleaned and cleaned not in parsed:
                    parsed.append(cleaned)
        elif isinstance(v, list):
            for item in v:
                cleaned = str(item).strip().strip("'\"").rstrip("/")
                if cleaned and cleaned not in parsed:
                    parsed.append(cleaned)

        # Merge mandatory base origins if not already present
        for b in base_origins:
            if b not in parsed:
                parsed.append(b)
        return parsed

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
