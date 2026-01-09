"""
Device API Endpoints

CRUD operations for sensors and relay controllers.
"""

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from .deps import DatabaseDep, APIKeyDep
from ..core.models import Device, DeviceCreate, DeviceUpdate, Channel, APIResponse

router = APIRouter()


@router.get("", response_model=List[Device])
async def list_devices(
    db: DatabaseDep,
    gateway_id: Optional[str] = Query(None, description="Filter by gateway")
) -> List[Device]:
    """List all configured devices"""
    devices = await db.get_all_devices(gateway_id)

    result = []
    for dev in devices:
        device = Device(**dev)
        # Load channels for each device
        channels = await db.get_device_channels(dev["id"])
        device.channels = [Channel(**ch) for ch in channels]
        result.append(device)

    return result


@router.get("/{device_id}", response_model=Device)
async def get_device(device_id: str, db: DatabaseDep) -> Device:
    """Get a specific device by ID"""
    device = await db.get_device(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )

    result = Device(**device)
    channels = await db.get_device_channels(device_id)
    result.channels = [Channel(**ch) for ch in channels]
    return result


@router.post("", response_model=Device, status_code=status.HTTP_201_CREATED)
async def create_device(
    device: DeviceCreate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Device:
    """Create a new device"""
    # Verify gateway exists
    gateway = await db.get_gateway(device.gateway_id)
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway {device.gateway_id} not found"
        )

    device_data = device.model_dump()
    device_data["id"] = str(uuid4())

    try:
        await db.create_device(device_data)
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device at address {device.modbus_address} already exists on this gateway"
            )
        raise

    created = await db.get_device(device_data["id"])
    return Device(**created)


@router.put("/{device_id}", response_model=Device)
async def update_device(
    device_id: str,
    updates: DeviceUpdate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Device:
    """Update a device"""
    device = await db.get_device(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )

    update_data = updates.model_dump(exclude_unset=True)
    if update_data:
        await db.update_device(device_id, update_data)

    updated = await db.get_device(device_id)
    result = Device(**updated)
    channels = await db.get_device_channels(device_id)
    result.channels = [Channel(**ch) for ch in channels]
    return result


@router.delete("/{device_id}", response_model=APIResponse)
async def delete_device(
    device_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> APIResponse:
    """Delete a device (cascades to channels)"""
    device = await db.get_device(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )

    await db.delete_device(device_id)
    return APIResponse(message=f"Device {device_id} deleted")


@router.get("/{device_id}/channels", response_model=List[Channel])
async def list_device_channels(device_id: str, db: DatabaseDep) -> List[Channel]:
    """List all channels for a device"""
    device = await db.get_device(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )

    channels = await db.get_device_channels(device_id)
    return [Channel(**ch) for ch in channels]
