"""
Sensor Model Registry API

Endpoints for managing sensor models and register mappings.
Allows adding new sensor types via configuration without code changes.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field

from .deps import DatabaseDep, APIKeyDep

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================

class SensorModelCreate(BaseModel):
    """Schema for creating a sensor model"""
    name: str = Field(..., min_length=1, max_length=50)
    manufacturer: Optional[str] = None
    device_type: str = Field(..., pattern="^(sensor|relay_controller)$")
    description: Optional[str] = None
    default_poll_interval: int = Field(default=10, ge=1, le=3600)


class SensorModelUpdate(BaseModel):
    """Schema for updating a sensor model"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    default_poll_interval: Optional[int] = Field(None, ge=1, le=3600)


class SensorModelResponse(BaseModel):
    """Schema for sensor model response"""
    id: str
    name: str
    manufacturer: Optional[str]
    device_type: str
    description: Optional[str]
    default_poll_interval: int
    created_at: Optional[str]


class RegisterMappingCreate(BaseModel):
    """Schema for creating a register mapping"""
    model_id: str
    channel_type: str = Field(..., min_length=1, max_length=50)
    channel_name: str = Field(..., min_length=1, max_length=100)
    register_address: int = Field(..., ge=0, le=65535)
    register_count: int = Field(default=1, ge=1, le=125)
    function_code: str = Field(
        ...,
        pattern="^(read_holding|read_input|read_coil|write_coil|write_register)$"
    )
    data_type: str = Field(
        default="uint16",
        pattern="^(uint16|int16|uint32|int32|float32|bool)$"
    )
    byte_order: str = Field(default="big", pattern="^(big|little)$")
    scale: float = Field(default=1.0)
    offset: float = Field(default=0.0)
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    category: Optional[str] = None
    channel_num: int = Field(..., ge=0, le=255)


class RegisterMappingUpdate(BaseModel):
    """Schema for updating a register mapping"""
    channel_name: Optional[str] = Field(None, min_length=1, max_length=100)
    register_address: Optional[int] = Field(None, ge=0, le=65535)
    register_count: Optional[int] = Field(None, ge=1, le=125)
    function_code: Optional[str] = Field(
        None,
        pattern="^(read_holding|read_input|read_coil|write_coil|write_register)$"
    )
    data_type: Optional[str] = Field(
        None,
        pattern="^(uint16|int16|uint32|int32|float32|bool)$"
    )
    byte_order: Optional[str] = Field(None, pattern="^(big|little)$")
    scale: Optional[float] = None
    offset: Optional[float] = None
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    category: Optional[str] = None


class RegisterMappingResponse(BaseModel):
    """Schema for register mapping response"""
    id: str
    model_id: str
    model_name: Optional[str] = None
    channel_type: str
    channel_name: str
    register_address: int
    register_count: int
    function_code: str
    data_type: str
    byte_order: str
    scale: float
    offset: float
    unit: Optional[str]
    min_value: Optional[float]
    max_value: Optional[float]
    category: Optional[str]
    channel_num: int


# =============================================================================
# Sensor Model Endpoints
# =============================================================================

@router.get("", response_model=List[SensorModelResponse])
async def list_sensor_models(db: DatabaseDep):
    """List all sensor models in the registry"""
    models = await db.get_all_sensor_models()
    return models


@router.get("/{model_id}", response_model=SensorModelResponse)
async def get_sensor_model(model_id: str, db: DatabaseDep):
    """Get a specific sensor model"""
    model = await db.get_sensor_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor model {model_id} not found"
        )
    return model


@router.post("", response_model=SensorModelResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor_model(
    model: SensorModelCreate,
    db: DatabaseDep,
    api_key: APIKeyDep
):
    """Create a new sensor model"""
    # Check for duplicate name
    existing = await db.get_sensor_model_by_name(model.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sensor model with name '{model.name}' already exists"
        )

    model_dict = model.model_dump()
    model_dict["id"] = f"model-{uuid.uuid4().hex[:8]}"

    await db.create_sensor_model(model_dict)
    return await db.get_sensor_model(model_dict["id"])


@router.patch("/{model_id}", response_model=SensorModelResponse)
async def update_sensor_model(
    model_id: str,
    updates: SensorModelUpdate,
    db: DatabaseDep,
    api_key: APIKeyDep
):
    """Update a sensor model"""
    model = await db.get_sensor_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor model {model_id} not found"
        )

    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    if update_dict:
        await db.update_sensor_model(model_id, update_dict)

    return await db.get_sensor_model(model_id)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sensor_model(
    model_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
):
    """Delete a sensor model (and all its mappings)"""
    model = await db.get_sensor_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor model {model_id} not found"
        )

    await db.delete_sensor_model(model_id)


# =============================================================================
# Register Mapping Endpoints
# =============================================================================

@router.get("/{model_id}/mappings", response_model=List[RegisterMappingResponse])
async def list_model_mappings(model_id: str, db: DatabaseDep):
    """List all register mappings for a sensor model"""
    model = await db.get_sensor_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor model {model_id} not found"
        )

    return await db.get_model_mappings(model_id)


@router.post(
    "/{model_id}/mappings",
    response_model=RegisterMappingResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_register_mapping(
    model_id: str,
    mapping: RegisterMappingCreate,
    db: DatabaseDep,
    api_key: APIKeyDep
):
    """Create a new register mapping for a sensor model"""
    model = await db.get_sensor_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor model {model_id} not found"
        )

    mapping_dict = mapping.model_dump()
    mapping_dict["id"] = f"map-{uuid.uuid4().hex[:8]}"
    mapping_dict["model_id"] = model_id  # Override in case of mismatch

    try:
        await db.create_register_mapping(mapping_dict)
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate channel_type or channel_num for this model"
            )
        raise

    return await db.get_register_mapping(mapping_dict["id"])


@router.patch("/mappings/{mapping_id}", response_model=RegisterMappingResponse)
async def update_register_mapping(
    mapping_id: str,
    updates: RegisterMappingUpdate,
    db: DatabaseDep,
    api_key: APIKeyDep
):
    """Update a register mapping"""
    mapping = await db.get_register_mapping(mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Register mapping {mapping_id} not found"
        )

    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    if update_dict:
        await db.update_register_mapping(mapping_id, update_dict)

    return await db.get_register_mapping(mapping_id)


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_register_mapping(
    mapping_id: str,
    db: DatabaseDep,
    api_key: APIKeyDep
):
    """Delete a register mapping"""
    mapping = await db.get_register_mapping(mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Register mapping {mapping_id} not found"
        )

    await db.delete_register_mapping(mapping_id)


# =============================================================================
# Hot Reload Endpoint
# =============================================================================

@router.post("/reload", status_code=status.HTTP_200_OK)
async def reload_model_mappings(
    request: Request,
    db: DatabaseDep,
    api_key: APIKeyDep
):
    """
    Reload sensor model mappings in the device manager.

    Call this after adding or modifying sensor models/mappings
    to apply changes without restarting the service.
    """
    device_manager = request.app.state.device_manager

    if not device_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Device manager not available"
        )

    await device_manager.reload_model_mappings()

    return {
        "status": "success",
        "message": "Model mappings reloaded",
        "models_loaded": len(device_manager._model_mappings)
    }
