"""Prometheus metrics instrumentation for application monitoring."""

from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI


def setup_monitoring(app: FastAPI) -> None:
    """Configure and expose Prometheus metrics endpoint."""
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=False,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )
    
    # Instrument the app and expose /metrics endpoint
    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)
