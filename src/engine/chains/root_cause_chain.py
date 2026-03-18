"""Chain for root cause analysis (reasoning chains + structured output)."""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.engine.schemas.output_schemas import RootCauseAnalysis
from src.config import get_settings
import structlog

logger = structlog.get_logger(__name__)

ROOT_CAUSE_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) performing root cause analysis on production incidents.

You must analyze the provided incident data — logs, alerts, timeline, and monitoring data — and determine the most probable root cause.

Follow this reasoning approach:
1. **Identify anomalies**: Look for errors, spikes, timeouts, or unusual patterns in logs and alerts.
2. **Correlate events**: Match timestamps across logs and alerts to find causal relationships.
3. **Trace dependencies**: Consider upstream/downstream service dependencies.
4. **Eliminate hypotheses**: Consider multiple possible causes and use evidence to narrow down.
5. **Determine root cause**: Identify the single most probable root cause with supporting evidence.

Be specific and technical. Reference actual log lines, alert names, and timestamps in your evidence.

{format_instructions}
"""

ROOT_CAUSE_HUMAN_PROMPT = """Analyze the following incident data and determine the root cause:

{incident_context}

Provide your analysis with step-by-step reasoning, the identified root cause, evidence, and confidence level."""


def create_root_cause_chain():
    """Create the root cause analysis chain with structured output."""
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )

    parser = PydanticOutputParser(pydantic_object=RootCauseAnalysis)

    prompt = ChatPromptTemplate.from_messages([
        ("system", ROOT_CAUSE_SYSTEM_PROMPT),
        ("human", ROOT_CAUSE_HUMAN_PROMPT),
    ])

    prompt = prompt.partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser

    return chain


async def run_root_cause_analysis(incident_context: str) -> RootCauseAnalysis:
    """Execute the root cause analysis chain."""
    logger.info("Running root cause analysis chain")
    chain = create_root_cause_chain()
    result = await chain.ainvoke({"incident_context": incident_context})
    logger.info(
        "Root cause analysis complete",
        category=result.root_cause_category,
        confidence=result.confidence_score,
    )
    return result