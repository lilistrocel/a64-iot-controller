"""
Channel API Endpoints

CRUD operations for individual sensor/relay channels within devices.
"""

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from .deps import DatabaseDep, APIKeyDep
from ..core.models import Channel, ChannelCreate, ChannelUpdate, APIResponse

router = APIRouter()


@router.get("", response_model=List[Channel])
async def list_channels(db: DatabaseDep) -> List[Channel]:
    """List all channels (from all devices)"""
    # Get all devices, then their channels
    devices = await db.get_all_devices()
    channels = []
    for device in devices:
        device_channels = await db.get_device_channels(device["id"])
        channels.extend([Channel(**ch) for ch in device_channels])
    return channels


@router.get("/relays", response_model=List[Channel])
async def list_relay_channels(db: DatabaseDep) -> List[Channel]:
    """List only relay channels"""
    channels = await db.get_relay_channels()
    return [Channel(**ch) for ch in channels]


@router.get("/sensors", response_model=List[Channel])
async def list_sensor_channels(db: DatabaseDep) -> List[Channel]:
    """List only sensor channels"""
    channels = await db.get_sensor_channels()
    return [Channel(**ch) for ch in channels]


@router.get("/{channel_id}", response_model=Channel)
async def get_channel(channel_id: str, db: DatabaseDep) -> Channel:
    """Get a specific channel by ID"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )
    return Channel(**channel)


@router.post("", response_model=Channel, status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel: ChannelCreate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Channel:
    """Create a new channel"""
    # Verify device exists
    device = await db.get_device(channel.device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {channel.device_id} not found"
        )

    channel_data = channel.model_dump()
    channel_data["id"] = str(uuid4())

    try:
        await db.create_channel(channel_data)
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Channel {channel.channel_num} already exists on this device"
            )
        raise

    created = await db.get_channel(channel_data["id"])
    return Channel(**created)


@router.put("/{channel_id}", response_model=Channel)
async def update_channel(
    channel_id: str,
    updates: ChannelUpdate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Channel:
    """Update a channel"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    update_data = updates.model_dump(exclude_unset=True)
    if update_data:
        await db.update_channel(channel_id, update_data)

    updated = await db.get_channel(channel_id)
    return Channel(**updated)


@router.delete("/{channel_id}", response_model=APIResponse)
async def delete_channel(
    channel_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> APIResponse:
    """Delete a channel"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    await db.delete_channel(channel_id)
    return APIResponse(message=f"Channel {channel_id} deleted")
