"""Test fixtures and configuration."""

import pytest
import os

# Set test environment variables
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///test.db")


@pytest.fixture
def sample_logs():
    """Sample log entries for testing."""
    return [
        {
            "timestamp": "2024-01-15T14:00:12Z",
            "level": "ERROR",
            "source": "payment-service",
            "message": "Failed to acquire database connection: pool exhausted",
        },
        {
            "timestamp": "2024-01-15T14:00:15Z",
            "level": "ERROR",
            "source": "payment-service",
            "message": "Transaction timeout after 30s waiting for DB connection",
        },
        {
            "timestamp": "2024-01-15T13:55:00Z",
            "level": "WARN",
            "source": "payment-service",
            "message": "Database connection pool utilization at 95%",
        },
        {
            "timestamp": "2024-01-15T13:50:00Z",
            "level": "INFO",
            "source": "deployment-pipeline",
            "message": "Deployed payment-service v2.3.1 with new batch processing feature",
        },
        {
            "timestamp": "2024-01-15T14:01:00Z",
            "level": "ERROR",
            "source": "api-gateway",
            "message": "Upstream payment-service returning 503",
        },
    ]


@pytest.fixture
def sample_raw_logs():
    """Sample raw log text."""
    return """2024-01-15T13:50:00Z INFO [deployment-pipeline] Deployed payment-service v2.3.1 with new batch processing feature
2024-01-15T13:55:00Z WARN [payment-service] Database connection pool utilization at 95%
2024-01-15T14:00:12Z ERROR [payment-service] Failed to acquire database connection: pool exhausted
2024-01-15T14:00:15Z ERROR [payment-service] Transaction timeout after 30s waiting for DB connection
2024-01-15T14:01:00Z ERROR [api-gateway] Upstream payment-service returning 503
2024-01-15T14:02:00Z ERROR [payment-service] java.sql.SQLException: Cannot get a connection, pool error Timeout waiting for idle object
2024-01-15T14:03:00Z WARN [order-service] Payment service calls failing, circuit breaker opened"""


@pytest.fixture
def sample_alerts():
    """Sample alert data."""
    return [
        {
            "alert_name": "PaymentServiceErrorRate",
            "source": "prometheus",
            "severity": "critical",
            "triggered_at": "2024-01-15T14:02:00Z",
            "description": "Error rate > 50% for payment-service",
            "labels": {"service": "payment-service", "env": "production"},
        },
        {
            "alert_name": "DatabaseConnectionPoolExhausted",
            "source": "prometheus",
            "severity": "warning",
            "triggered_at": "2024-01-15T13:58:00Z",
            "description": "Connection pool usage > 90%",
            "labels": {"service": "payment-service", "database": "payments-db"},
        },
        {
            "alertname": "HighLatency",
            "status": "firing",
            "startsAt": "2024-01-15T14:01:00Z",
            "endsAt": "2024-01-15T14:30:00Z",
            "labels": {"alertname": "HighLatency", "severity": "warning", "service": "api-gateway"},
            "annotations": {"summary": "P99 latency > 5s for api-gateway", "description": "API gateway experiencing high latency"},
        },
    ]


@pytest.fixture
def sample_timeline():
    """Sample incident timeline."""
    return [
        {"timestamp": "2024-01-15T13:50:00Z", "description": "payment-service v2.3.1 deployed to production", "type": "deployment"},
        {"timestamp": "2024-01-15T13:55:00Z", "description": "DB connection pool warnings start appearing", "type": "observation"},
        {"timestamp": "2024-01-15T13:58:00Z", "description": "DatabaseConnectionPoolExhausted alert fires", "type": "alert"},
        {"timestamp": "2024-01-15T14:00:00Z", "description": "First customer complaints about failed payments", "type": "observation"},
        {"timestamp": "2024-01-15T14:02:00Z", "description": "PaymentServiceErrorRate critical alert fires", "type": "alert"},
        {"timestamp": "2024-01-15T14:05:00Z", "description": "On-call SRE acknowledged and began investigation", "type": "action"},
        {"timestamp": "2024-01-15T14:15:00Z", "description": "Root cause identified: new batch processing feature holding DB connections", "type": "observation"},
        {"timestamp": "2024-01-15T14:20:00Z", "description": "Rolled back to payment-service v2.3.0", "type": "action"},
        {"timestamp": "2024-01-15T14:25:00Z", "description": "Service recovered, error rate back to normal", "type": "observation"},
    ]


@pytest.fixture
def sample_otel_logs():
    """Sample OpenTelemetry log records."""
    return [
        {
            "timeUnixNano": "1705327212000000000",
            "severityText": "ERROR",
            "body": {"stringValue": "Connection pool exhausted: max connections reached"},
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "payment-service"}},
                    {"key": "deployment.environment", "value": {"stringValue": "production"}},
                ]
            },
            "attributes": [
                {"key": "pool.size", "value": {"intValue": 50}},
                {"key": "pool.active", "value": {"intValue": 50}},
            ],
            "traceId": "abc123def456",
            "spanId": "span789",
        }
    ]


@pytest.fixture
def sample_otel_spans():
    """Sample OpenTelemetry span data."""
    return [
        {
            "name": "POST /api/payments",
            "startTimeUnixNano": "1705327212000000000",
            "endTimeUnixNano": "1705327242000000000",
            "status": {"code": 2, "message": "Connection pool timeout"},
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "payment-service"}},
                ]
            },
            "attributes": [
                {"key": "http.method", "value": {"stringValue": "POST"}},
                {"key": "http.status_code", "value": {"intValue": 503}},
            ],
            "traceId": "abc123def456",
            "spanId": "span789",
        }
    ]