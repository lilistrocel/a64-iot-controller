"""
Schedule API Endpoints

CRUD operations for relay schedules.
"""

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from .deps import DatabaseDep, APIKeyDep
from ..core.models import Schedule, ScheduleCreate, ScheduleUpdate, APIResponse

router = APIRouter()


@router.get("", response_model=List[Schedule])
async def list_schedules(db: DatabaseDep) -> List[Schedule]:
    """List all schedules"""
    schedules = await db.get_all_schedules()
    return [Schedule(**s) for s in schedules]


@router.get("/active", response_model=List[Schedule])
async def list_active_schedules(db: DatabaseDep) -> List[Schedule]:
    """List only enabled schedules"""
    schedules = await db.get_enabled_schedules()
    return [Schedule(**s) for s in schedules]


@router.get("/{schedule_id}", response_model=Schedule)
async def get_schedule(schedule_id: str, db: DatabaseDep) -> Schedule:
    """Get a specific schedule by ID"""
    schedule = await db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    return Schedule(**schedule)


@router.post("", response_model=Schedule, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Schedule:
    """Create a new schedule"""
    # Verify channel exists and is a relay
    channel = await db.get_channel(schedule.channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {schedule.channel_id} not found"
        )

    if channel["channel_type"] != "relay":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedules can only be created for relay channels"
        )

    schedule_data = schedule.model_dump()
    schedule_data["id"] = str(uuid4())

    await db.create_schedule(schedule_data)

    created = await db.get_schedule(schedule_data["id"])
    return Schedule(**created)


@router.put("/{schedule_id}", response_model=Schedule)
async def update_schedule(
    schedule_id: str,
    updates: ScheduleUpdate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Schedule:
    """Update a schedule"""
    schedule = await db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    update_data = updates.model_dump(exclude_unset=True)
    if update_data:
        await db.update_schedule(schedule_id, update_data)

    updated = await db.get_schedule(schedule_id)
    return Schedule(**updated)


@router.delete("/{schedule_id}", response_model=APIResponse)
async def delete_schedule(
    schedule_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> APIResponse:
    """Delete a schedule"""
    schedule = await db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    await db.delete_schedule(schedule_id)
    return APIResponse(message=f"Schedule {schedule_id} deleted")


@router.post("/{schedule_id}/enable", response_model=Schedule)
async def enable_schedule(
    schedule_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Schedule:
    """Enable a schedule"""
    schedule = await db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    await db.update_schedule(schedule_id, {"enabled": True})
    updated = await db.get_schedule(schedule_id)
    return Schedule(**updated)


@router.post("/{schedule_id}/disable", response_model=Schedule)
async def disable_schedule(
    schedule_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Schedule:
    """Disable a schedule"""
    schedule = await db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    await db.update_schedule(schedule_id, {"enabled": False})
    updated = await db.get_schedule(schedule_id)
    return Schedule(**updated)
