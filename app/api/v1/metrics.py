from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from app.core.metrics import metrics_registry

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def get_prometheus_metrics():
    """Expose application operational metrics in Prometheus text exposition format."""
    body = metrics_registry.generate_prometheus_metrics()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/metrics/json")
async def get_json_metrics():
    """Expose application operational metrics snapshot in JSON format."""
    snapshot = metrics_registry.generate_json_metrics()
    return JSONResponse(content=snapshot)
