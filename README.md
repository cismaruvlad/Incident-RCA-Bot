# Incident RCA (Root Cause Analysis) Bot

An AI-powered Root Cause Analysis bot that analyzes production incidents using LangChain, 
OpenAI, PostgreSQL, and OpenTelemetry. It ingests incident timelines, logs, alerts, and 
monitoring data to produce comprehensive root cause analysis, system impact reports, 
prevention plans, and postmortem summaries.

## Architecture
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Incident Logs│ │Alerts/Timeline│ │Monitoring Data│
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
│ │ │
└────────────┬────┴────────────────┘
▼
┌─────────────────────┐
│ LangChain RCA │
│ Engine │◄──── Multi-step Agent
│ (Orchestrator) │ (Tool-based pre-analysis)
└────────┬────────────┘
│
┌────────▼────────┐
│ LLM (OpenAI) │
└────────┬────────┘
│
┌─────────────┼─────────────────┐
▼ ▼ ▼
┌────────┐ ┌──────────┐ ┌──────────────┐
│Root │ │System │ │Postmortem │
│Cause │ │Impact │ │Summary │
│Analysis │ │Report │ │ │
└────────┘ └──────────┘ └──────────────┘
│
┌───────────▼──────────┐
│ Ticket/Issue Creation │
└──────────────────────┘


## Features

- **Multi-source ingestion**: Parse logs (raw text, structured, OpenTelemetry), alerts 
  (Prometheus, PagerDuty, Datadog), and incident timelines
- **Multi-step agent**: LangChain agent with tools for log pattern analysis, 
  alert-timeline correlation, and service identification
- **Structured output**: Pydantic-validated output schemas for all analysis stages
- **Reasoning chains**: Sequential chains for root cause → impact → prevention → postmortem
- **Memory**: Cross-step context management so each analysis stage builds on previous findings
- **Persistence**: PostgreSQL storage for incidents and RCA results
- **Ticketing**: Webhook-based ticket/issue creation (Jira, Slack, ServiceNow compatible)
- **Observability**: OpenTelemetry tracing for the bot

## LangChain Concepts Used

| Concept | Implementation |
|---------|---------------|
| **Structured Output** | Pydantic output parsers for all 4 analysis chains |
| **Reasoning Chains** | Sequential analysis: root cause → impact → prevention → postmortem |
| **Memory** | `IncidentMemory` maintains context across all chain steps |
| **Multi-step Agents** | `AgentExecutor` with tools for log analysis, correlation, service ID |

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key
- Docker & Docker Compose (for PostgreSQL and OTel)

### 1. Clone and setup

```bash
git clone <repo-url>
cd incident-rca-bot

python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

pip install -r requirements.txt

2. Configure environment
bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

3. Start infrastructure
bash
docker-compose up -d postgres otel-collector jaeger

4. Run database migrations
bash
alembic upgrade head

5. Start the API server
bash
python -m src.main
The API will be available at http://localhost:8000.

Swagger docs: http://localhost:8000/docs
Health check: http://localhost:8000/health

6. Run an analysis
bash
# Quick test with the integration script
python scripts/test_integration.py
Or use curl:

bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Payment Service Outage",
    "severity": "critical",
    "logs": [
      {"timestamp": "2024-01-15T14:00:12Z", "level": "ERROR", "source": "payment-service", "message": "Failed to acquire database connection: pool exhausted"},
      {"timestamp": "2024-01-15T13:55:00Z", "level": "WARN", "source": "payment-service", "message": "Database connection pool utilization at 95%"},
      {"timestamp": "2024-01-15T13:50:00Z", "level": "INFO", "source": "deploy", "message": "Deployed payment-service v2.3.1"}
    ],
    "alerts": [
      {"alert_name": "HighErrorRate", "source": "prometheus", "severity": "critical", "triggered_at": "2024-01-15T14:02:00Z", "description": "Error rate > 50%"}
    ],
    "timeline": [
      {"timestamp": "2024-01-15T13:50:00Z", "description": "Deployed v2.3.1", "type": "deployment"},
      {"timestamp": "2024-01-15T14:00:00Z", "description": "Errors started", "type": "observation"},
      {"timestamp": "2024-01-15T14:20:00Z", "description": "Rolled back", "type": "action"}
    ],
    "run_agent": false
  }'


API Endpoints
Method	Endpoint	Description
GET	/health	Health check
POST	/api/v1/analyze	Direct analysis (no DB persistence)
POST	/api/v1/incidents	Create an incident
GET	/api/v1/incidents	List incidents
GET	/api/v1/incidents/{id}	Get incident details
POST	/api/v1/incidents/{id}/analyze	Analyze a persisted incident
GET	/api/v1/incidents/{id}/rca	Get RCA results

Running Tests

# Unit tests (no API key or DB needed)
pytest tests/ -v

# Testing coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Specific test files
pytest tests/test_ingestion.py -v
pytest tests/test_engine.py -v
pytest tests/test_chains.py -v
pytest tests/test_api.py -v
Project Structure
text
src/
├── api/              # FastAPI app and routes
├── db/               # SQLAlchemy models, database, repository
├── engine/           # LangChain RCA engine
│   ├── agents/       # Multi-step agent with tools
│   ├── chains/       # Analysis chains (root cause, impact, prevention, postmortem)
│   ├── memory/       # Cross-step context memory
│   └── schemas/      # Pydantic output schemas
├── ingestion/        # Log, alert, and OTel data parsers
