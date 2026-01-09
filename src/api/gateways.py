"""
Gateway API Endpoints

CRUD operations for RS485-ETH gateways.
"""

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from .deps import DatabaseDep, APIKeyDep
from ..core.models import Gateway, GatewayCreate, GatewayUpdate, APIResponse

router = APIRouter()


@router.get("", response_model=List[Gateway])
async def list_gateways(db: DatabaseDep) -> List[Gateway]:
    """List all configured gateways"""
    gateways = await db.get_all_gateways()
    return [Gateway(**gw) for gw in gateways]


@router.get("/{gateway_id}", response_model=Gateway)
async def get_gateway(gateway_id: str, db: DatabaseDep) -> Gateway:
    """Get a specific gateway by ID"""
    gateway = await db.get_gateway(gateway_id)
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway {gateway_id} not found"
        )
    return Gateway(**gateway)


@router.post("", response_model=Gateway, status_code=status.HTTP_201_CREATED)
async def create_gateway(
    gateway: GatewayCreate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Gateway:
    """Create a new gateway"""
    gateway_data = gateway.model_dump()
    gateway_data["id"] = str(uuid4())

    try:
        await db.create_gateway(gateway_data)
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Gateway with IP {gateway.ip_address}:{gateway.port} already exists"
            )
        raise

    created = await db.get_gateway(gateway_data["id"])
    return Gateway(**created)


@router.put("/{gateway_id}", response_model=Gateway)
async def update_gateway(
    gateway_id: str,
    updates: GatewayUpdate,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Gateway:
    """Update a gateway"""
    gateway = await db.get_gateway(gateway_id)
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway {gateway_id} not found"
        )

    update_data = updates.model_dump(exclude_unset=True)
    if update_data:
        await db.update_gateway(gateway_id, update_data)

    updated = await db.get_gateway(gateway_id)
    return Gateway(**updated)


@router.delete("/{gateway_id}", response_model=APIResponse)
async def delete_gateway(
    gateway_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> APIResponse:
    """Delete a gateway (cascades to devices)"""
    gateway = await db.get_gateway(gateway_id)
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway {gateway_id} not found"
        )

    await db.delete_gateway(gateway_id)
    return APIResponse(message=f"Gateway {gateway_id} deleted")
