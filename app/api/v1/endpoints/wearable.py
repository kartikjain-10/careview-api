from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.db.database import get_db
from app.db.repository import WearableRepository
from app.models.schemas import (
    WearableSnapshotRecord,
    WearableSyncRequest,
    WearableSyncResponse,
)

router = APIRouter(prefix="/wearable", tags=["wearable"])


@router.post("/sync", response_model=WearableSyncResponse)
async def sync_wearable_data(
    body: WearableSyncRequest,
    settings: Settings = Depends(get_settings),
) -> WearableSyncResponse:
    if not body.snapshots:
        raise HTTPException(status_code=422, detail="snapshots list must not be empty")

    async with get_db(settings) as db:
        repo = WearableRepository(db)
        for snapshot in body.snapshots:
            await repo.insert_snapshot(snapshot)

    return WearableSyncResponse(inserted=len(body.snapshots))


@router.get("/{parent_id}", response_model=list[WearableSnapshotRecord])
async def get_wearable_data(
    parent_id: str,
    settings: Settings = Depends(get_settings),
) -> list[WearableSnapshotRecord]:
    async with get_db(settings) as db:
        repo = WearableRepository(db)
        snapshots = await repo.get_snapshots_by_parent(parent_id)

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No wearable data found for parent '{parent_id}' in the last 30 days",
        )

    return snapshots
