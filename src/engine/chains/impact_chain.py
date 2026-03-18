"""Chain for system impact analysis."""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.engine.schemas.output_schemas import SystemImpactReport
from src.config import get_settings
import structlog

logger = structlog.get_logger(__name__)

IMPACT_SYSTEM_PROMPT = """You are an expert SRE analyzing the impact of a production incident.

Given the incident data and the root cause analysis, determine:
1. All affected systems and services (direct and indirect)
2. The blast radius of the incident
3. End-user impact
4. Any data loss or integrity issues
5. Duration of impact

Be thorough — consider cascading failures, dependent services, and downstream effects.

{format_instructions}
"""

IMPACT_HUMAN_PROMPT = """Based on the following incident data and root cause analysis, provide a comprehensive system impact report:

{incident_context}

## Root Cause Analysis Results
{root_cause_results}

Identify all affected systems, their impact severity, and the overall blast radius."""


def create_impact_chain():
    """Create the system impact analysis chain."""
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )

    parser = PydanticOutputParser(pydantic_object=SystemImpactReport)

    prompt = ChatPromptTemplate.from_messages([
        ("system", IMPACT_SYSTEM_PROMPT),
        ("human", IMPACT_HUMAN_PROMPT),
    ])

    prompt = prompt.partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser
    return chain


async def run_impact_analysis(
    incident_context: str, root_cause_results: str
) -> SystemImpactReport:
    """Execute the system impact analysis chain."""
    logger.info("Running system impact analysis chain")
    chain = create_impact_chain()
    result = await chain.ainvoke({
        "incident_context": incident_context,
        "root_cause_results": root_cause_results,
    })
    logger.info(
        "Impact analysis complete",
        affected_systems_count=len(result.affected_systems),
    )
    return result