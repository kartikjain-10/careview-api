from langchain_groq import ChatGroq
from app.core.config import Settings


def build_llm(settings: Settings) -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )
