#!/usr/bin/env python3
"""
Integration test script to verify the full RCA pipeline.
Run this after starting services: docker-compose up -d

Usage:
    python scripts/test_integration.py

Requires a running API server and valid OPENAI_API_KEY.
"""

import httpx
import json
import asyncio
import sys


API_BASE = "http://localhost:8000/api/v1"

SAMPLE_INCIDENT = {
    "title": "Payment Service Outage - Database Connection Pool Exhaustion",
    "description": (
        "At 14:00 UTC, the payment service started returning 503 errors. "
        "Investigation revealed the database connection pool was exhausted "
        "following a deployment of v2.3.1 with a new batch processing feature."
    ),
    "severity": "critical",
    "timeline": [
        {
            "timestamp": "2024-01-15T13:50:00Z",
            "description": "payment-service v2.3.1 deployed to production with new batch processing feature",
            "type": "deployment",
        },
        {
            "timestamp": "2024-01-15T13:55:00Z",
            "description": "Database connection pool warnings begin appearing in logs",
            "type": "observation",
        },
        {
            "timestamp": "2024-01-15T13:58:00Z",
            "description": "DatabaseConnectionPoolExhausted alert fires in Prometheus",
            "type": "alert",
        },
        {
            "timestamp": "2024-01-15T14:00:00Z",
            "description": "First customer complaints about failed payments",
            "type": "observation",
        },
        {
            "timestamp": "2024-01-15T14:02:00Z",
            "description": "PaymentServiceErrorRate critical alert fires",
            "type": "alert",
        },
        {
            "timestamp": "2024-01-15T14:05:00Z",
            "description": "On-call SRE acknowledged and began investigation",
            "type": "action",
        },
        {
            "timestamp": "2024-01-15T14:10:00Z",
            "description": "Identified high DB connection count, suspecting pool exhaustion",
            "type": "observation",
        },
        {
            "timestamp": "2024-01-15T14:15:00Z",
            "description": "Confirmed: new batch processing feature not releasing DB connections properly",
            "type": "observation",
        },
        {
            "timestamp": "2024-01-15T14:20:00Z",
            "description": "Rolled back to payment-service v2.3.0",
            "type": "action",
        },
        {
            "timestamp": "2024-01-15T14:25:00Z",
            "description": "Service recovered, error rate back to baseline",
            "type": "observation",
        },
    ],
    "logs": [
        {
            "timestamp": "2024-01-15T13:50:02Z",
            "level": "INFO",
            "source": "deployment-pipeline",
            "message": "Deployed payment-service v2.3.1 (sha: abc123) to production cluster",
        },
        {
            "timestamp": "2024-01-15T13:52:00Z",
            "level": "INFO",
            "source": "payment-service",
            "message": "Batch processing job started: processing 50000 pending reconciliation records",
        },
        {
            "timestamp": "2024-01-15T13:53:00Z",
            "level": "INFO",
            "source": "payment-service",
            "message": "Active DB connections: 35/50",
        },
        {
            "timestamp": "2024-01-15T13:55:00Z",
            "level": "WARN",
            "source": "payment-service",
            "message": "Database connection pool utilization at 95% (48/50 connections active)",
        },
        {
            "timestamp": "2024-01-15T13:57:00Z",
            "level": "WARN",
            "source": "payment-service",
            "message": "Slow query detected: batch_reconciliation query taking 45s (threshold: 10s)",
        },
        {
            "timestamp": "2024-01-15T13:58:30Z",
            "level": "ERROR",
            "source": "payment-service",
            "message": "Connection pool exhausted: all 50 connections in use, 23 threads waiting",
        },
        {
            "timestamp": "2024-01-15T14:00:12Z",
            "level": "ERROR",
            "source": "payment-service",
            "message": "Failed to acquire database connection: pool exhausted after 30s timeout",
        },
        {
            "timestamp": "2024-01-15T14:00:15Z",
            "level": "ERROR",
            "source": "payment-service",
            "message": "Transaction failed: java.sql.SQLException: Cannot get a connection, pool error Timeout waiting for idle object",
        },
        {
            "timestamp": "2024-01-15T14:00:30Z",
            "level": "ERROR",
            "source": "payment-service",
            "message": "Health check failed: database connectivity check timed out",
        },
        {
            "timestamp": "2024-01-15T14:01:00Z",
            "level": "ERROR",
            "source": "api-gateway",
            "message": "Upstream service payment-service returning HTTP 503 Service Unavailable",
        },
        {
            "timestamp": "2024-01-15T14:01:30Z",
            "level": "WARN",
            "source": "order-service",
            "message": "Circuit breaker OPENED for payment-service: 10 consecutive failures",
        },
        {
            "timestamp": "2024-01-15T14:02:00Z",
            "level": "ERROR",
            "source": "notification-service",
            "message": "Failed to send payment confirmation emails: payment-service unavailable",
        },
        {
            "timestamp": "2024-01-15T14:20:05Z",
            "level": "INFO",
            "source": "deployment-pipeline",
            "message": "Rollback initiated: reverting payment-service to v2.3.0",
        },
        {
            "timestamp": "2024-01-15T14:22:00Z",
            "level": "INFO",
            "source": "payment-service",
            "message": "payment-service v2.3.0 pods healthy, DB connections normalizing",
        },
        {
            "timestamp": "2024-01-15T14:25:00Z",
            "level": "INFO",
            "source": "payment-service",
            "message": "Active DB connections: 12/50 - pool recovered",
        },
    ],
    "alerts": [
        {
            "alert_name": "DatabaseConnectionPoolExhausted",
            "source": "prometheus",
            "severity": "warning",
            "triggered_at": "2024-01-15T13:58:00Z",
            "description": "Database connection pool usage > 90% for payment-service for 3+ minutes",
            "labels": {"service": "payment-service", "database": "payments-db", "pool_size": "50"},
        },
        {
            "alert_name": "PaymentServiceErrorRate",
            "source": "prometheus",
            "severity": "critical",
            "triggered_at": "2024-01-15T14:02:00Z",
            "description": "Error rate exceeds 50% threshold for payment-service (current: 87%)",
            "labels": {"service": "payment-service", "env": "production"},
        },
        {
            "alert_name": "UpstreamServiceUnavailable",
            "source": "prometheus",
            "severity": "critical",
            "triggered_at": "2024-01-15T14:01:00Z",
            "description": "api-gateway unable to reach payment-service: 100% 503 responses",
            "labels": {"upstream": "payment-service", "proxy": "api-gateway"},
        },
        {
            "alert_name": "CircuitBreakerOpen",
            "source": "prometheus",
            "severity": "warning",
            "triggered_at": "2024-01-15T14:01:30Z",
            "resolved_at": "2024-01-15T14:26:00Z",
            "description": "Circuit breaker opened for payment-service in order-service",
            "labels": {"caller": "order-service", "callee": "payment-service"},
        },
    ],
    "monitoring_data": (
        "CPU usage: payment-service pods at 45% (normal)\n"
        "Memory usage: payment-service pods at 72% (slightly elevated)\n"
        "Database CPU: 85% (elevated, normally 30%)\n"
        "Database active connections: 50/50 (max, normally 15-20)\n"
        "Database slow queries: 47 queries > 10s (normally 0-2)\n"
        "Network: No anomalies detected\n"
        "Disk I/O: Database server disk I/O at 90% (elevated)\n"
    ),
    "run_agent": True,
}


async def run_integration_test():
    """Run the full integration test."""
    print("=" * 80)
    print("INCIDENT RCA BOT - INTEGRATION TEST")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Health check
        print("\n[1] Health Check...")
        try:
            resp = await client.get("http://localhost:8000/health")
            print(f"    Status: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"    FAILED: {e}")
            print("    Make sure the API server is running: python -m src.main")
            sys.exit(1)

        # 2. Direct analysis
        print("\n[2] Running Direct Analysis (this may take 30-60 seconds)...")
        try:
            resp = await client.post(f"{API_BASE}/analyze", json=SAMPLE_INCIDENT)
            if resp.status_code == 200:
                data = resp.json()
                analysis = data.get("analysis", {})

                print(f" Analysis completed in {data.get('analysis_duration_seconds', 0):.1f}s")

                # Root Cause
                rca = analysis.get("root_cause_analysis", {})
                print(f"\n  ROOT CAUSE:")
                print(f"       Cause: {rca.get('root_cause', 'N/A')[:200]}")
                print(f"       Category: {rca.get('root_cause_category', 'N/A')}")
                print(f"       Confidence: {rca.get('confidence_score', 'N/A')}")

                # Impact
                impact = analysis.get("system_impact", {})
                affected = [s.get("system_name") for s in impact.get("affected_systems", [])]
                print(f"\n   AFFECTED SYSTEMS: {', '.join(affected)}")
                print(f"       Blast Radius: {impact.get('blast_radius', 'N/A')[:150]}")
                print(f"       User Impact: {impact.get('user_impact', 'N/A')[:150]}")

                # Prevention
                prevention = analysis.get("prevention_plan", {})
                immediate = prevention.get("immediate_actions", [])
                print(f"\n    PREVENTION ({len(immediate)} immediate actions):")
                for action in immediate[:3]:
                    print(f"       [{action.get('priority')}] {action.get('action', '')[:100]}")

                # Postmortem
                postmortem = analysis.get("postmortem", {})
                print(f"\n    POSTMORTEM: {postmortem.get('title', 'N/A')}")
                print(f"       Summary: {postmortem.get('executive_summary', 'N/A')[:200]}")

                # Save full output
                with open("rca_output.json", "w") as f:
                    json.dump(data, f, indent=2, default=str)
                print(f"\n    Full output saved to rca_output.json")

            else:
                print(f"    Analysis failed: {resp.status_code}")
                print(f"    Response: {resp.text[:500]}")
        except Exception as e:
            print(f"    FAILED: {e}")

        # 3. Create persistent incident (if DB is available)
        print("\n[3] Testing Incident CRUD (requires PostgreSQL)...")
        try:
            create_payload = {
                "title": "Test Incident for Integration",
                "severity": "medium",
                "timeline": SAMPLE_INCIDENT["timeline"][:3],
                "logs": SAMPLE_INCIDENT["logs"][:3],
                "alerts": SAMPLE_INCIDENT["alerts"][:2],
            }
            resp = await client.post(f"{API_BASE}/incidents", json=create_payload)
            if resp.status_code == 201:
                incident = resp.json()
                print(f"   Incident created: {incident['id']}")

                # Get incident
                resp = await client.get(f"{API_BASE}/incidents/{incident['id']}")
                if resp.status_code == 200:
                    detail = resp.json()
                    print(f"    Incident retrieved: {detail['title']}")
                    print(f"       Logs: {len(detail.get('logs', []))}")
                    print(f"       Alerts: {len(detail.get('alerts', []))}")

                # List incidents
                resp = await client.get(f"{API_BASE}/incidents")
                if resp.status_code == 200:
                    incidents = resp.json()
                    print(f"    Listed {len(incidents)} incidents")

            else:
                print(f"    ⚠Skipped (DB not available): {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"    Skipped (DB not available): {e}")

    print("\n" + "=" * 80)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_integration_test())