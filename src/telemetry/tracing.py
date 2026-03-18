"""OpenTelemetry tracing setup for the RCA bot."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import structlog

from src.config import get_settings

logger = structlog.get_logger(__name__)


def setup_telemetry(app=None):
    """Initialize OpenTelemetry tracing."""
    settings = get_settings()

    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": "1.0.0",
        "deployment.environment": "development",
    })

    provider = TracerProvider(resource=resource)

    # Try OTLP exporter; fall back to console
    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=True,
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info("OTLP span exporter configured", endpoint=settings.otel_exporter_otlp_endpoint)
    except Exception as e:
        logger.warning("Failed to setup OTLP exporter, using console", error=str(e))
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    if app:
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumented with OpenTelemetry")
        except Exception as e:
            logger.warning("Failed to instrument FastAPI", error=str(e))

    return trace.get_tracer(settings.otel_service_name)


def get_tracer():
    """Get the application tracer."""
    settings = get_settings()
    return trace.get_tracer(settings.otel_service_name)