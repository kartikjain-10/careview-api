from __future__ import annotations

from urllib.parse import quote

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

HINDI_SYSTEM_PROMPT = """आप एक caring family member हैं जो अपनी माँ को WhatsApp पर health update भेज रहे हैं।

आपका काम है — wearable data को देखकर एक warm, loving message लिखना।

सख्त नियम:
- सरल, रोज़मर्रा की हिंदी लिखें — formal या bureaucratic नहीं
- "आप", "माँ", "ठीक हैं", "अच्छा लग रहा है" जैसे शब्द इस्तेमाल करें
- English medical jargon से बचें — "नींद" लिखें, "sleep" नहीं; "कदम" लिखें, "steps" नहीं
- Tone: गर्मजोशी भरी, reassuring — जैसे बेटा/बेटी माँ को लिख रहे हों
- कुछ भी alarming न लिखें — सब कुछ gently frame करें
- कोई भी medical conclusion न निकालें, कोई दवाई suggest न करें
- Data को trend की भाषा में बताएं — "लग रहा है", "लगता है", "शायद"
- Message छोटा रखें — phone screen पर पढ़ने लायक
- अंत में affectionate closing ज़रूर लिखें जैसे:
  "आपका ख्याल रखना ❤️" या "जल्दी मिलते हैं 🙏"
- "नमस्ते माँ 🙏" से शुरू करें
"""

ENGLISH_SYSTEM_PROMPT = """You are a caring family member sending a WhatsApp wellness update to your parent (Maa).

Your job is to look at the wearable data and write a warm, loving message.

Strict rules:
- Conversational and warm — not clinical or formal
- Short paragraphs, easy to read on a phone screen
- Use everyday language — no medical jargon
- Never draw medical conclusions or suggest specific interventions
- Use trend-based language: "seems like", "appears to", "you might want to"
- Never say anything alarming — frame everything gently and reassuringly
- Start with "Hi Maa 🙏" or similar warm greeting
- End affectionately: "Take care, love you 💙" or "Talk soon! 💙" style
"""

USER_TEMPLATE = """Here is the recent wearable data summary for the last 7 days:

{wearable_summary}

Write a warm WhatsApp message to share this update."""

_HINDI_PROMPT = ChatPromptTemplate.from_messages([
    ("system", HINDI_SYSTEM_PROMPT),
    ("human", USER_TEMPLATE),
])

_ENGLISH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", ENGLISH_SYSTEM_PROMPT),
    ("human", USER_TEMPLATE),
])


def build_whatsapp_link(phone_number: str, message: str) -> str:
    """Build a WhatsApp deep link. Strips leading '+' and URL-encodes the message."""
    clean_phone = phone_number.lstrip("+")
    encoded_message = quote(message, safe="")
    return f"https://wa.me/{clean_phone}?text={encoded_message}"


def build_whatsapp_chain(llm: ChatGroq):
    hindi_chain = _HINDI_PROMPT | llm | StrOutputParser()
    english_chain = _ENGLISH_PROMPT | llm | StrOutputParser()

    def run(language: str, wearable_summary: str) -> str:
        chain = hindi_chain if language == "hindi" else english_chain
        return chain.invoke({"wearable_summary": wearable_summary})

    return run
