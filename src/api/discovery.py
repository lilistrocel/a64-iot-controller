"""
Device Discovery API Endpoints

Scan RS485 bus for Modbus devices.
"""

import asyncio
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from .deps import DatabaseDep, APIKeyDep

router = APIRouter()


class DiscoveredDevice(BaseModel):
    """A device found during discovery scan"""
    gateway_id: str
    modbus_address: int
    device_type: Optional[str] = None
    model: Optional[str] = None
    channels: int = 0
    already_configured: bool = False
    existing_device_id: Optional[str] = None


class DiscoveryResult(BaseModel):
    """Result of a discovery scan"""
    gateway_id: str
    gateway_name: str
    addresses_scanned: int
    devices_found: int
    discovered: List[DiscoveredDevice]
    errors: List[str]


class ScanRequest(BaseModel):
    """Request parameters for discovery scan"""
    gateway_id: str
    start_address: int = 1
    end_address: int = 247
    timeout_ms: int = 500


async def probe_modbus_device(
    host: str,
    port: int,
    address: int,
    timeout_ms: int
) -> Optional[Dict[str, Any]]:
    """
    Probe a single Modbus address to check if a device exists.

    Returns device info if found, None otherwise.

    This is a placeholder - actual implementation will use pymodbus.
    """
    # TODO: Implement actual Modbus probing with pymodbus
    # This will:
    # 1. Try to read holding registers to detect device
    # 2. Read device identification registers if available
    # 3. Detect device type based on register layout

    # For now, return None (no device found)
    # Real implementation will be in Phase 2: Device Manager
    return None


@router.post("/scan", response_model=DiscoveryResult)
async def scan_for_devices(
    request: ScanRequest,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> DiscoveryResult:
    """
    Scan a gateway's RS485 bus for Modbus devices.

    This scans addresses from start_address to end_address and reports
    any devices that respond. Already-configured devices are marked.
    """
    gateway = await db.get_gateway(request.gateway_id)
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway {request.gateway_id} not found"
        )

    # Get existing devices on this gateway
    existing_devices = await db.get_all_devices(request.gateway_id)
    existing_addresses = {d["modbus_address"]: d for d in existing_devices}

    discovered = []
    errors = []
    addresses_scanned = 0

    # Scan each address
    for address in range(request.start_address, request.end_address + 1):
        addresses_scanned += 1

        try:
            device_info = await probe_modbus_device(
                host=gateway["ip_address"],
                port=gateway["port"],
                address=address,
                timeout_ms=request.timeout_ms
            )

            if device_info:
                # Check if already configured
                existing = existing_addresses.get(address)

                discovered.append(DiscoveredDevice(
                    gateway_id=request.gateway_id,
                    modbus_address=address,
                    device_type=device_info.get("device_type"),
                    model=device_info.get("model"),
                    channels=device_info.get("channels", 0),
                    already_configured=existing is not None,
                    existing_device_id=existing["id"] if existing else None
                ))

        except Exception as e:
            errors.append(f"Error probing address {address}: {str(e)}")

    return DiscoveryResult(
        gateway_id=request.gateway_id,
        gateway_name=gateway["name"],
        addresses_scanned=addresses_scanned,
        devices_found=len(discovered),
        discovered=discovered,
        errors=errors
    )


@router.get("/quick-scan/{gateway_id}", response_model=DiscoveryResult)
async def quick_scan(
    gateway_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep,
    common_only: bool = Query(True, description="Only scan common addresses (1-32)")
) -> DiscoveryResult:
    """
    Quick scan of common Modbus addresses.

    By default only scans addresses 1-32 which covers most setups.
    """
    end_address = 32 if common_only else 247

    request = ScanRequest(
        gateway_id=gateway_id,
        start_address=1,
        end_address=end_address,
        timeout_ms=300
    )

    return await scan_for_devices(request, db, api_key)


@router.post("/test-connection")
async def test_gateway_connection(
    gateway_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
) -> Dict[str, Any]:
    """
    Test connection to a gateway.

    Attempts to establish a TCP connection to the gateway.
    """
    gateway = await db.get_gateway(gateway_id)
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway {gateway_id} not found"
        )

    try:
        # Try to open a TCP connection
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(gateway["ip_address"], gateway["port"]),
            timeout=5.0
        )
        writer.close()
        await writer.wait_closed()

        return {
            "gateway_id": gateway_id,
            "host": gateway["ip_address"],
            "port": gateway["port"],
            "status": "connected",
            "message": "Gateway is reachable"
        }

    except asyncio.TimeoutError:
        return {
            "gateway_id": gateway_id,
            "host": gateway["ip_address"],
            "port": gateway["port"],
            "status": "timeout",
            "message": "Connection timed out after 5 seconds"
        }

    except ConnectionRefusedError:
        return {
            "gateway_id": gateway_id,
            "host": gateway["ip_address"],
            "port": gateway["port"],
            "status": "refused",
            "message": "Connection refused - gateway may be offline or port is wrong"
        }

    except Exception as e:
        return {
            "gateway_id": gateway_id,
            "host": gateway["ip_address"],
            "port": gateway["port"],
            "status": "error",
            "message": f"Connection failed: {str(e)}"
        }
