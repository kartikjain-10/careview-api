from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field


# ── Health check ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str


# ── Wearable ──────────────────────────────────────────────────────────────────

class WearableSnapshot(BaseModel):
    parent_id: str
    date: date
    steps: int = Field(ge=0)
    sleep_hours: float = Field(ge=0, le=24)
    resting_heart_rate: int = Field(ge=0, le=300)
    active_minutes: int = Field(ge=0)
    mood_score: int = Field(ge=1, le=10)


class WearableSyncRequest(BaseModel):
    snapshots: list[WearableSnapshot]


class WearableSyncResponse(BaseModel):
    inserted: int


class WearableSnapshotRecord(WearableSnapshot):
    id: int
    created_at: datetime


# ── Insights ──────────────────────────────────────────────────────────────────

class InsightRequest(BaseModel):
    parent_id: str
    query: str


class InsightResponse(BaseModel):
    insight: str
    parent_id: str


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentMetadata(BaseModel):
    document_id: str
    parent_id: str
    filename: str
    upload_date: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadata]


# ── WhatsApp ──────────────────────────────────────────────────────────────────

class WhatsAppGenerateRequest(BaseModel):
    parent_id: str
    ward_id: str
    language: Literal["hindi", "english"]
    phone_number: str


class WhatsAppGenerateResponse(BaseModel):
    message: str
    whatsapp_link: str
    language: Literal["hindi", "english"]
