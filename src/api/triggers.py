"""
Trigger API Endpoints

CRUD operations for automation triggers (sensor → relay rules).
"""

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from .deps import DatabaseDep, APIKeyDep
from ..core.models import Trigger, TriggerCreate, TriggerUpdate, APIResponse

router = APIRouter()


@router.get("", response_model=List[Trigger])
async def list_triggers(db: DatabaseDep) -> List[Trigger]:
    """List all triggers"""
    triggers = await db.get_all_triggers()
    return [Trigger(**t) for t in triggers]


@router.get("/active", response_model=List[Trigger])
async def list_active_triggers(db: DatabaseDep) -> List[Trigger]:
    """List only enabled triggers"""
    triggers = await db.get_enabled_triggers()
    return [Trigger(**t) for t in triggers]


@router.get("/{trigger_id}", response_model=Trigger)
async def get_trigger(trigger_id: str, db: DatabaseDep) -> Trigger:
    """Get a specific trigger by ID"""
    trigger = await db.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found"
        )
    return Trigger(**trigger)


@router.post("", response_model=Trigger, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    trigger: TriggerCreate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Trigger:
    """Create a new trigger"""
    # Verify source channel exists
    source_channel = await db.get_channel(trigger.source_channel_id)
    if not source_channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source channel {trigger.source_channel_id} not found"
        )

    if source_channel["channel_type"] == "relay":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trigger source must be a sensor channel"
        )

    # Verify target channel exists
    target_channel = await db.get_channel(trigger.target_channel_id)
    if not target_channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target channel {trigger.target_channel_id} not found"
        )

    if target_channel["channel_type"] != "relay":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trigger target must be a relay channel"
        )

    trigger_data = trigger.model_dump()
    trigger_data["id"] = str(uuid4())

    await db.create_trigger(trigger_data)

    created = await db.get_trigger(trigger_data["id"])
    return Trigger(**created)


@router.put("/{trigger_id}", response_model=Trigger)
async def update_trigger(
    trigger_id: str,
    updates: TriggerUpdate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Trigger:
    """Update a trigger"""
    trigger = await db.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found"
        )

    update_data = updates.model_dump(exclude_unset=True)
    if update_data:
        await db.update_trigger(trigger_id, update_data)

    updated = await db.get_trigger(trigger_id)
    return Trigger(**updated)


@router.delete("/{trigger_id}", response_model=APIResponse)
async def delete_trigger(
    trigger_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> APIResponse:
    """Delete a trigger"""
    trigger = await db.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found"
        )

    await db.delete_trigger(trigger_id)
    return APIResponse(message=f"Trigger {trigger_id} deleted")


@router.post("/{trigger_id}/enable", response_model=Trigger)
async def enable_trigger(
    trigger_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Trigger:
    """Enable a trigger"""
    trigger = await db.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found"
        )

    await db.update_trigger(trigger_id, {"enabled": True})
    updated = await db.get_trigger(trigger_id)
    return Trigger(**updated)


@router.post("/{trigger_id}/disable", response_model=Trigger)
async def disable_trigger(
    trigger_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Trigger:
    """Disable a trigger"""
    trigger = await db.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found"
        )

    await db.update_trigger(trigger_id, {"enabled": False})
    updated = await db.get_trigger(trigger_id)
    return Trigger(**updated)
