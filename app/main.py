from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import LoggingMiddleware, logger
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.exceptions import (
    http_exception_handler,
    validation_exception_handler,
    permission_exception_handler,
    unhandled_exception_handler,
)
from app.schemas.common import RootResponse, HealthResponse, ReadinessResponse
from app.api.v1.health import readiness_check
from app.api.v1.router import api_v1_router
import app.tools  # Register all MCP LMS and RAG tools

app = FastAPI(
    title=f"{settings.APP_NAME} API Gateway",
    description=(
        "Multi-tenant Shared AI Service API Gateway serving OWL LMS, HR Corner, Cineku, "
        "and future enterprise applications. Provides unified agent chat completion, "
        "multimodal RAG engine, knowledge management, and personalized recommendations."
    ),
    version=settings.APP_VERSION,
    debug=settings.APP_DEBUG,
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json",
)

# Global Exception Handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(PermissionError, permission_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# CORS Configuration
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Logging Middleware (Request ID & Latency Tracing)
app.add_middleware(LoggingMiddleware)

# Include API v1 Router
app.include_router(api_v1_router, prefix=settings.API_PREFIX)

# Mount Static Custom Documentation Frontend
import os
from fastapi.staticfiles import StaticFiles
docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
if os.path.exists(docs_dir):
    app.mount("/documentation", StaticFiles(directory=docs_dir, html=True), name="documentation")



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
    """Fast Liveness health check endpoint."""
    return HealthResponse(
        status="ok",
        service="ai-service",
        version=settings.APP_VERSION,
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["Health"])
async def ready():
    """Readiness probe checking dependency status."""
    from app.services.llm_service import get_llm_service
    return await readiness_check(llm_service=get_llm_service())


@app.get("/metrics", tags=["Metrics"])
async def root_metrics():
    """Expose Prometheus text metrics endpoint at root level."""
    from app.core.metrics import metrics_registry
    from fastapi import Response
    body = metrics_registry.generate_prometheus_metrics()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/metrics/json", tags=["Metrics"])
async def root_metrics_json():
    """Expose JSON snapshot metrics endpoint at root level."""
    from app.core.metrics import metrics_registry
    from fastapi.responses import JSONResponse
    return JSONResponse(content=metrics_registry.generate_json_metrics())



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.APP_DEBUG)
