from functools import lru_cache
from fastapi import Depends
from langchain_groq import ChatGroq
from langchain_chroma import Chroma

from app.core.config import Settings, settings as _default_settings
from app.ai.llm import build_llm
from app.ai.vectorstore import build_vectorstore


@lru_cache
def get_settings() -> Settings:
    return _default_settings


def get_llm(s: Settings = Depends(get_settings)) -> ChatGroq:
    return build_llm(s)


def get_vectorstore(s: Settings = Depends(get_settings)) -> Chroma:
    return build_vectorstore(s)
