"""Chain for generating a prevention plan."""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.engine.schemas.output_schemas import PreventionPlan
from src.config import get_settings
import structlog

logger = structlog.get_logger(__name__)

PREVENTION_SYSTEM_PROMPT = """You are an expert SRE creating a prevention plan to ensure an incident does not recur.

Given the incident data, root cause, and impact analysis, create a comprehensive prevention plan with:
1. **Immediate actions** (next 24-48 hours) — hotfixes, rollbacks, config changes
2. **Short-term actions** (1-2 weeks) — code fixes, test additions, process changes
3. **Long-term actions** (next quarter) — architectural improvements, tooling investments
4. **Monitoring improvements** — new alerts, dashboards, or observability enhancements

Be specific and actionable. Assign priority levels and suggest responsible teams.

{format_instructions}
"""

PREVENTION_HUMAN_PROMPT = """Based on the following incident analysis, create a prevention plan:

{incident_context}

## Root Cause
{root_cause_results}

## Impact Analysis
{impact_results}

Generate specific, actionable prevention measures."""


def create_prevention_chain():
    """Create the prevention plan chain."""
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.2,
        api_key=settings.openai_api_key,
    )

    parser = PydanticOutputParser(pydantic_object=PreventionPlan)

    prompt = ChatPromptTemplate.from_messages([
        ("system", PREVENTION_SYSTEM_PROMPT),
        ("human", PREVENTION_HUMAN_PROMPT),
    ])

    prompt = prompt.partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser
    return chain


async def run_prevention