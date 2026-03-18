"""FastAPI application setup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from src.db.database import init_db
from src.telemetry.tracing import setup_telemetry
from src.api.routes import router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("Starting Incident RCA Bot")

    # Initialize database tables
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database initialization skipped", error=str(e))

    # Setup telemetry
    try:
        setup_telemetry(app)
        logger.info("Telemetry initialized")
    except Exception as e:
        logger.warning("Telemetry setup skipped", error=str(e))

    yield

    logger.info("Shutting down Incident RCA Bot")


app = FastAPI(
    title="Incident RCA Bot",
    description=(
        "AI-powered Root Cause Analysis for production incidents. "
        "Analyzes logs, alerts, and timelines to produce root cause analysis, "
        "impact reports, prevention plans, and postmortem summaries."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "incident-rca-bot"}