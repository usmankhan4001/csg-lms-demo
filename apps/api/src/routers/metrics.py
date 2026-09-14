from fastapi import APIRouter, Response
from src.core.metrics import metrics_registry

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics():
    """Prometheus metrics scrape endpoint."""
    output = metrics_registry.generate_prometheus_output()
    return Response(content=output, media_type="text/plain; version=0.0.4; charset=utf-8")
