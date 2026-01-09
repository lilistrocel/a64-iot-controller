"""
Readings API Endpoints

Sensor readings retrieval and history.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from .deps import DatabaseDep
from ..core.models import Reading

router = APIRouter()


@router.get("", response_model=List[Reading])
async def get_latest_readings(db: DatabaseDep) -> List[Reading]:
    """Get the latest reading for each sensor channel"""
    readings = await db.get_latest_readings()
    return [Reading(**r) for r in readings]


@router.get("/{channel_id}", response_model=List[Reading])
async def get_channel_readings(
    channel_id: str,
    db: DatabaseDep,
    limit: int = Query(default=100, ge=1, le=10000, description="Max readings to return"),
    hours: Optional[int] = Query(default=None, ge=1, le=720, description="Only readings from last N hours")
) -> List[Reading]:
    """Get readings for a specific channel"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    since = None
    if hours:
        since = datetime.now() - timedelta(hours=hours)

    readings = await db.get_channel_readings(channel_id, limit=limit, since=since)
    return [Reading(**r) for r in readings]


@router.get("/{channel_id}/latest", response_model=Optional[Reading])
async def get_latest_channel_reading(channel_id: str, db: DatabaseDep) -> Optional[Reading]:
    """Get the most recent reading for a channel"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    readings = await db.get_channel_readings(channel_id, limit=1)
    if readings:
        return Reading(**readings[0])
    return None


@router.get("/{channel_id}/stats")
async def get_channel_stats(
    channel_id: str,
    db: DatabaseDep,
    hours: int = Query(default=24, ge=1, le=720, description="Hours to analyze")
):
    """Get statistics for a channel's readings"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    since = datetime.now() - timedelta(hours=hours)
    readings = await db.get_channel_readings(channel_id, limit=10000, since=since)

    if not readings:
        return {
            "channel_id": channel_id,
            "period_hours": hours,
            "count": 0,
            "min": None,
            "max": None,
            "avg": None,
            "latest": None
        }

    values = [r["value"] for r in readings]
    return {
        "channel_id": channel_id,
        "period_hours": hours,
        "count": len(values),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(sum(values) / len(values), 2),
        "latest": readings[0]["value"] if readings else None
    }
