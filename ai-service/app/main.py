from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import LoggingMiddleware, logger
from app.schemas.common import RootResponse, HealthResponse
from app.api.v1.router import api_v1_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.APP_DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Logging Middleware
app.add_middleware(LoggingMiddleware)

# Include API v1 Router
app.include_router(api_v1_router, prefix=settings.API_PREFIX)


@app.get("/", response_model=RootResponse, tags=["Root"])
async def root():
    """Root application endpoint."""
    return RootResponse(
        service=settings.APP_NAME,
        status="running",
        version=settings.APP_VERSION,
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    """System health check endpoint without authentication requirements."""
    return HealthResponse(
        status="ok",
        service="ai-service",
        version=settings.APP_VERSION,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.APP_DEBUG)
