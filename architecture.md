# Incident RCA (Root Cause Analysis) Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-0.2-green?style=for-the-badge&logo=chainlink&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql&logoColor=white" />
</p>

<p align="center">
  <strong>An AI-powered bot that analyzes production incidents and generates comprehensive root cause analysis, impact reports, prevention plans, and postmortem documents.</strong>
</p>

---

## 🏗️ Architecture

```text
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Incident Logs│  │Alerts/Timeline│  │Monitoring Data│
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       └────────────┬────┴────────────────┘
                    ▼
         ┌─────────────────────┐
         │  LangChain RCA      │
         │  Engine              │◄── Multi-step Agent
         └────────┬────────────┘
                  ▼
         ┌────────────────┐
         │  OpenAI GPT-4o │
         └────────┬───────┘
    ┌─────────────┼──────────────────┐
    ▼             ▼                  ▼
┌────────┐  ┌──────────┐  ┌──────────────┐
│Root    │  │System    │  │Postmortem    │
│Cause   │  │Impact    │  │Summary       │
│Analysis│  │Report    │  │              │
└────────┘  └──────────┘  └──────────────┘