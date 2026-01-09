"""
A64Core Platform Integration Endpoint

Provides aggregated device data in the format expected by
the A64Core Platform's BlockAutomationTab component.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter

from .deps import DatabaseDep
from ..config import settings

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
async def get_aggregated_devices(db: DatabaseDep) -> Dict[str, Any]:
    """
    Get aggregated device data for A64Core integration.

    Returns data in the format expected by BlockAutomationTab:
    {
        "controllerId": str,
        "controllerName": str,
        "lastUpdate": str (ISO datetime),
        "sensors": [
            {
                "id": str,
                "name": str,
                "type": str,
                "label": str,
                "online": bool,
                "readings": {
                    "temperature": {"value": float, "unit": str},
                    ...
                }
            }
        ],
        "relays": [
            {
                "id": str,
                "label": str,
                "state": bool,
                "online": bool
            }
        ]
    }
    """
    # Get all sensor readings with device info
    latest_readings = await db.get_latest_readings()

    # Get all relay states
    relay_states = await db.get_all_relay_states()
    relay_channels = await db.get_relay_channels()

    # Get all devices to determine online status
    all_devices = await db.get_all_devices()
    device_status = {d["id"]: bool(d.get("online", False)) for d in all_devices}

    # Group sensor readings by device
    sensor_devices: Dict[str, Dict[str, Any]] = {}
    for reading in latest_readings:
        device_id = reading.get("device_id", "")
        device_name = reading.get("device_name", "Unknown Sensor")

        if device_id not in sensor_devices:
            sensor_devices[device_id] = {
                "id": device_id,
                "name": device_name,
                "type": "sensor",
                "label": device_name,
                "online": device_status.get(device_id, False),
                "readings": {}
            }

        # Add reading to device - use channel_name for better display
        channel_name = reading.get("channel_name", reading.get("channel_type", "value"))
        sensor_devices[device_id]["readings"][channel_name] = {
            "value": round(reading["value"], 2),
            "unit": reading.get("unit", "")
        }

    # Build relay list
    relays: List[Dict[str, Any]] = []
    relay_state_map = {s["channel_id"]: s for s in relay_states}

    for channel in relay_channels:
        channel_id = channel["id"]
        state_record = relay_state_map.get(channel_id)

        # Get device online status
        device_id = channel.get("device_id", "")
        is_online = device_status.get(device_id, False)

        relays.append({
            "id": channel_id,
            "label": channel.get("name", f"Relay {channel.get('channel_num', 0)}"),
            "state": bool(state_record["state"]) if state_record else False,
            "online": is_online
        })

    # Build response
    return {
        "controllerId": settings.controller_id,
        "controllerName": settings.controller_name,
        "lastUpdate": datetime.now().isoformat(),
        "sensors": list(sensor_devices.values()),
        "relays": relays
    }
