"""
Relay Control API Endpoints

Control and monitor relay states.
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status

from .deps import DatabaseDep, APIKeyDep
from ..core.models import RelayState, RelayCommand, APIResponse

router = APIRouter()


@router.get("", response_model=List[Dict[str, Any]])
async def get_all_relay_states(db: DatabaseDep) -> List[Dict[str, Any]]:
    """Get current state of all relays"""
    states = await db.get_all_relay_states()

    # Get all relay channels for relays without state history
    relay_channels = await db.get_relay_channels()
    channel_ids_with_state = {s["channel_id"] for s in states}

    result = []

    # Add relays with known states
    for state in states:
        result.append({
            "channel_id": state["channel_id"],
            "channel_name": state["channel_name"],
            "category": state["category"],
            "device_name": state["device_name"],
            "state": bool(state["state"]),
            "source": state["source"],
            "last_changed": state["timestamp"]
        })

    # Add relays without state history (default to OFF)
    for channel in relay_channels:
        if channel["id"] not in channel_ids_with_state:
            result.append({
                "channel_id": channel["id"],
                "channel_name": channel["name"],
                "category": channel["category"],
                "device_name": channel["device_name"],
                "state": False,
                "source": None,
                "last_changed": None
            })

    return result


@router.get("/{channel_id}", response_model=Dict[str, Any])
async def get_relay_state(channel_id: str, db: DatabaseDep) -> Dict[str, Any]:
    """Get current state of a specific relay"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    if channel["channel_type"] != "relay":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel {channel_id} is not a relay"
        )

    state = await db.get_last_relay_state(channel_id)

    return {
        "channel_id": channel_id,
        "channel_name": channel["name"],
        "state": bool(state["state"]) if state else False,
        "source": state["source"] if state else None,
        "last_changed": state["timestamp"] if state else None
    }


@router.put("/{channel_id}", response_model=Dict[str, Any])
async def control_relay(
    channel_id: str,
    command: RelayCommand,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Dict[str, Any]:
    """
    Control a relay.

    This endpoint records the command in the database.
    The actual hardware control is handled by the device manager (polling loop).
    """
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    if channel["channel_type"] != "relay":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel {channel_id} is not a relay"
        )

    # Record the state change
    await db.add_relay_state(channel_id, command.state, command.source.value)

    # TODO: Actually send command to hardware via device manager
    # For now, we just record the desired state

    return {
        "channel_id": channel_id,
        "channel_name": channel["name"],
        "state": command.state,
        "source": command.source.value,
        "message": f"Relay {'ON' if command.state else 'OFF'} command recorded"
    }


@router.get("/{channel_id}/history", response_model=List[RelayState])
async def get_relay_history(
    channel_id: str,
    db: DatabaseDep,
    limit: int = 100
) -> List[RelayState]:
    """Get state change history for a relay"""
    channel = await db.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel {channel_id} not found"
        )

    # For now, use a simple query - could add to database.py
    rows = await db.execute(
        """
        SELECT * FROM relay_states
        WHERE channel_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (channel_id, limit),
        fetch_all=True
    )

    return [RelayState(**dict(row)) for row in rows]
