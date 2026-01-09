"""
Pydantic Models

Type-safe data models for API requests/responses and internal operations.
"""

from datetime import datetime, time
from enum import Enum
from typing import Optional, List, Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================

class DeviceType(str, Enum):
    SENSOR = "sensor"
    RELAY_CONTROLLER = "relay_controller"


class ChannelType(str, Enum):
    # Sensor types
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    SOIL_MOISTURE = "soil_moisture"
    SOIL_TEMPERATURE = "soil_temperature"
    SOIL_EC = "soil_ec"
    SOIL_PH = "soil_ph"
    SOIL_NITROGEN = "soil_nitrogen"
    SOIL_PHOSPHORUS = "soil_phosphorus"
    SOIL_POTASSIUM = "soil_potassium"
    # Relay type
    RELAY = "relay"


class RelayCategory(str, Enum):
    FAN = "fan"
    PUMP = "pump"
    VALVE = "valve"
    LIGHT = "light"
    HEATER = "heater"
    OTHER = "other"


class TriggerOperator(str, Enum):
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NE = "!="


class TriggerAction(str, Enum):
    ON = "on"
    OFF = "off"
    TOGGLE = "toggle"


class RelaySource(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    TRIGGER = "trigger"
    API = "api"
    RECOVERY = "recovery"
    ESP32 = "esp32"


# =============================================================================
# Base Models
# =============================================================================

class BaseModelWithId(BaseModel):
    """Base model with auto-generated ID"""
    id: str = Field(default_factory=lambda: str(uuid4()))


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# Gateway Models
# =============================================================================

class GatewayBase(BaseModel):
    """Base gateway fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Gateway name")
    ip_address: str = Field(..., description="Gateway IP address")
    port: int = Field(default=4196, ge=1, le=65535, description="Gateway port")
    enabled: bool = Field(default=True, description="Whether gateway is enabled")


class GatewayCreate(GatewayBase):
    """Create a new gateway"""
    pass


class GatewayUpdate(BaseModel):
    """Update gateway fields"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    ip_address: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    enabled: Optional[bool] = None


class Gateway(GatewayBase, BaseModelWithId):
    """Full gateway model"""
    online: bool = False
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Device Models
# =============================================================================

class DeviceBase(BaseModel):
    """Base device fields"""
    gateway_id: str = Field(..., description="Parent gateway ID")
    modbus_address: int = Field(..., ge=1, le=247, description="Modbus address")
    device_type: DeviceType = Field(..., description="Device type")
    model: str = Field(..., min_length=1, max_length=50, description="Device model")
    name: str = Field(..., min_length=1, max_length=100, description="Device name")
    category: Optional[str] = Field(None, max_length=50, description="Device category")
    wifi_ip: Optional[str] = Field(None, description="WiFi IP for ESP32 sync")
    wifi_enabled: bool = Field(default=False, description="Enable WiFi sync")
    poll_interval: int = Field(default=10, ge=1, le=3600, description="Poll interval seconds")
    enabled: bool = Field(default=True, description="Whether device is enabled")


class DeviceCreate(DeviceBase):
    """Create a new device"""
    pass


class DeviceUpdate(BaseModel):
    """Update device fields"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    wifi_ip: Optional[str] = None
    wifi_enabled: Optional[bool] = None
    poll_interval: Optional[int] = Field(None, ge=1, le=3600)
    enabled: Optional[bool] = None


class Device(DeviceBase, BaseModelWithId):
    """Full device model"""
    online: bool = False
    last_seen: Optional[datetime] = None
    config: Optional[str] = None
    created_at: Optional[datetime] = None
    channels: List["Channel"] = Field(default_factory=list)

    class Config:
        from_attributes = True


# =============================================================================
# Channel Models
# =============================================================================

class ChannelBase(BaseModel):
    """Base channel fields"""
    device_id: str = Field(..., description="Parent device ID")
    channel_num: int = Field(..., ge=0, description="Channel number")
    channel_type: str = Field(..., description="Channel type")
    name: str = Field(..., min_length=1, max_length=100, description="Channel name")
    category: Optional[str] = Field(None, max_length=50, description="Channel category")
    unit: Optional[str] = Field(None, max_length=20, description="Unit of measurement")
    min_value: Optional[float] = Field(None, description="Minimum expected value")
    max_value: Optional[float] = Field(None, description="Maximum expected value")
    enabled: bool = Field(default=True, description="Whether channel is enabled")


class ChannelCreate(ChannelBase):
    """Create a new channel"""
    pass


class ChannelUpdate(BaseModel):
    """Update channel fields"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    unit: Optional[str] = Field(None, max_length=20)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    enabled: Optional[bool] = None


class Channel(ChannelBase, BaseModelWithId):
    """Full channel model"""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Reading Models
# =============================================================================

class Reading(BaseModel):
    """Sensor reading"""
    id: Optional[int] = None
    channel_id: str
    value: float
    timestamp: Optional[datetime] = None
    # Joined fields
    channel_name: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    device_name: Optional[str] = None

    class Config:
        from_attributes = True


class ReadingCreate(BaseModel):
    """Create a reading"""
    channel_id: str
    value: float


# =============================================================================
# Relay State Models
# =============================================================================

class RelayState(BaseModel):
    """Relay state record"""
    id: Optional[int] = None
    channel_id: str
    state: bool
    source: str
    timestamp: Optional[datetime] = None
    # Joined fields
    channel_name: Optional[str] = None
    category: Optional[str] = None
    device_name: Optional[str] = None
    modbus_address: Optional[int] = None

    class Config:
        from_attributes = True


class RelayCommand(BaseModel):
    """Command to control a relay"""
    state: bool = Field(..., description="Desired relay state (true=ON, false=OFF)")
    source: RelaySource = Field(default=RelaySource.API, description="Command source")


# =============================================================================
# Schedule Models
# =============================================================================

class ScheduleBase(BaseModel):
    """Base schedule fields"""
    channel_id: str = Field(..., description="Target relay channel ID")
    name: Optional[str] = Field(None, max_length=100, description="Schedule name")
    enabled: bool = Field(default=True, description="Whether schedule is enabled")
    time_on: str = Field(..., description="Turn ON time (HH:MM)")
    time_off: str = Field(..., description="Turn OFF time (HH:MM)")
    days_of_week: str = Field(
        default="[0,1,2,3,4,5,6]",
        description="Days of week (JSON array, 0=Monday)"
    )
    priority: int = Field(default=0, ge=0, le=100, description="Priority (higher wins)")
    sync_to_esp32: bool = Field(default=True, description="Sync schedule to ESP32")

    @field_validator("time_on", "time_off")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time format HH:MM"""
        try:
            parts = v.split(":")
            assert len(parts) == 2
            hour, minute = int(parts[0]), int(parts[1])
            assert 0 <= hour <= 23 and 0 <= minute <= 59
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, AssertionError):
            raise ValueError("Time must be in HH:MM format")


class ScheduleCreate(ScheduleBase):
    """Create a new schedule"""
    pass


class ScheduleUpdate(BaseModel):
    """Update schedule fields"""
    name: Optional[str] = Field(None, max_length=100)
    enabled: Optional[bool] = None
    time_on: Optional[str] = None
    time_off: Optional[str] = None
    days_of_week: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    sync_to_esp32: Optional[bool] = None

    @field_validator("time_on", "time_off")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            parts = v.split(":")
            assert len(parts) == 2
            hour, minute = int(parts[0]), int(parts[1])
            assert 0 <= hour <= 23 and 0 <= minute <= 59
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, AssertionError):
            raise ValueError("Time must be in HH:MM format")


class Schedule(ScheduleBase, BaseModelWithId):
    """Full schedule model"""
    esp32_synced_at: Optional[datetime] = None
    a64core_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields
    channel_name: Optional[str] = None
    category: Optional[str] = None
    device_name: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# Trigger Models
# =============================================================================

class TriggerBase(BaseModel):
    """Base trigger fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Trigger name")
    enabled: bool = Field(default=True, description="Whether trigger is enabled")
    source_channel_id: str = Field(..., description="Source sensor channel ID")
    operator: TriggerOperator = Field(..., description="Comparison operator")
    threshold: float = Field(..., description="Threshold value")
    target_channel_id: str = Field(..., description="Target relay channel ID")
    action: TriggerAction = Field(..., description="Action to perform")
    duration: Optional[int] = Field(
        None, ge=1, le=86400,
        description="Auto-off duration in seconds (null=permanent)"
    )
    cooldown: int = Field(
        default=300, ge=0, le=86400,
        description="Minimum seconds between triggers"
    )
    priority: int = Field(default=0, ge=0, le=100, description="Priority (higher wins)")


class TriggerCreate(TriggerBase):
    """Create a new trigger"""
    pass


class TriggerUpdate(BaseModel):
    """Update trigger fields"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    source_channel_id: Optional[str] = None
    operator: Optional[TriggerOperator] = None
    threshold: Optional[float] = None
    target_channel_id: Optional[str] = None
    action: Optional[TriggerAction] = None
    duration: Optional[int] = Field(None, ge=1, le=86400)
    cooldown: Optional[int] = Field(None, ge=0, le=86400)
    priority: Optional[int] = Field(None, ge=0, le=100)


class Trigger(TriggerBase, BaseModelWithId):
    """Full trigger model"""
    last_triggered: Optional[datetime] = None
    a64core_id: Optional[str] = None
    created_at: Optional[datetime] = None
    # Joined fields
    source_channel_name: Optional[str] = None
    target_channel_name: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# Discovery Models
# =============================================================================

class DiscoveredDevice(BaseModel):
    """Device discovered during scan"""
    modbus_address: int
    device_type: DeviceType
    model: str
    suggested_name: str
    channels: int
    responding: bool = True


class DiscoveryScan(BaseModel):
    """Discovery scan results"""
    gateway_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    devices_found: List[DiscoveredDevice] = Field(default_factory=list)
    addresses_scanned: int = 0
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# System Models
# =============================================================================

class SystemStatus(BaseModel):
    """System status information"""
    status: str = "healthy"
    timestamp: datetime
    uptime_seconds: float
    version: str
    checks: dict = Field(default_factory=dict)


class HealthCheck(BaseModel):
    """Health check result"""
    status: str
    message: Optional[str] = None


# =============================================================================
# API Response Models
# =============================================================================

class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    """Paginated response"""
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 50
    pages: int = 1


# Forward references
Device.model_rebuild()
