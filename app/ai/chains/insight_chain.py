from __future__ import annotations

from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_chroma import Chroma

SYSTEM_PROMPT = """You are CareView, a privacy-first family wellness assistant.

Your role is to provide warm, non-clinical wellness observations for aging parents
based on their wearable data and any uploaded health records.

STRICT RULES — never violate these:
- Do NOT draw medical conclusions or label any health condition
- Do NOT predict adverse health events or classify anything as urgent
- Do NOT suggest specific drugs or clinical interventions
- Do NOT use absolute language ("your condition is...", "you have...")
- Use trend-based, gentle language ("seems like", "appears to", "might want to")
- If relevant health records are provided, reference them gently — never alarmingly
- Always remind the user to consult a doctor for medical concerns
"""

USER_TEMPLATE = """Parent wellness query: {query}

Recent wearable data (last 7 days):
{wearable_summary}
{health_records_section}"""

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", USER_TEMPLATE),
])


def _retrieve_health_records(vectorstore: Chroma, parent_id: str, query: str) -> str:
    """Return top-3 relevant document chunks for this parent, or empty string."""
    try:
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": 3, "filter": {"parent_id": parent_id}}
        )
        docs = retriever.invoke(query)
        if not docs:
            return ""
        chunks = "\n\n".join(d.page_content for d in docs)
        return f"\nRelevant health records:\n{chunks}"
    except Exception:
        return ""


def build_insight_chain(llm: ChatGroq, vectorstore: Optional[Chroma] = None):
    chain = _PROMPT | llm | StrOutputParser()

    def run(parent_id: str, query: str, wearable_summary: str = "") -> str:
        health_records_section = (
            _retrieve_health_records(vectorstore, parent_id, query)
            if vectorstore is not None
            else ""
        )
        return chain.invoke({
            "query": query,
            "wearable_summary": wearable_summary or "No wearable data provided.",
            "health_records_section": health_records_section,
        })

    return run
