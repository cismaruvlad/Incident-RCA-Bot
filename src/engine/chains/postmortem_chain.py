"""Chain for generating a complete postmortem summary."""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.engine.schemas.output_schemas import PostmortemSummary
from src.config import get_settings
import structlog

logger = structlog.get_logger(__name__)

POSTMORTEM_SYSTEM_PROMPT = """You are an expert SRE writing a blameless postmortem document for a production incident.

Given all the analysis data — incident details, root cause, impact, and prevention plan — create a comprehensive 
postmortem document following industry best practices (Google SRE, PagerDuty postmortem guidelines).

The postmortem should be:
- **Blameless**: Focus on systems and processes, not individuals
- **Thorough**: Cover timeline, root cause, impact, resolution, and follow-ups
- **Actionable**: Include clear lessons learned and action items
- **Clear**: Written for both technical and non-technical stakeholders

{format_instructions}
"""

POSTMORTEM_HUMAN_PROMPT = """Generate a complete postmortem document based on all the analysis below:

{incident_context}

## Root Cause Analysis
{root_cause_results}

## System Impact Report
{impact_results}

## Prevention Plan
{prevention_results}

Write a comprehensive, blameless postmortem summary."""


def create_postmortem_chain():
    """Create the postmortem summary chain."""
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.3,
        api_key=settings.openai_api_key,
    )

    parser = PydanticOutputParser(pydantic_object=PostmortemSummary)

    prompt = ChatPromptTemplate.from_messages([
        ("system", POSTMORTEM_SYSTEM_PROMPT),
        ("human", POSTMORTEM_HUMAN_PROMPT),
    ])

    prompt = prompt.partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser
    return chain


async def run_postmortem_generation(
    incident_context: str,
    root_cause_results: str,
    impact_results: str,
    prevention_results: str,
) -> PostmortemSummary:
    """Execute the postmortem generation chain."""
    logger.info("Running postmortem generation chain")
    chain = create_postmortem_chain()
    result = await chain.ainvoke({
        "incident_context": incident_context,
        "root_cause_results": root_cause_results,
        "impact_results": impact_results,
        "prevention_results": prevention_results,
    })
    logger.info("Postmortem generation complete", title=result.title)
    return result