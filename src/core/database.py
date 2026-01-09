"""
Database Management

SQLite database with WAL mode for crash resistance.
Async operations via aiosqlite.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, List
from contextlib import asynccontextmanager

import aiosqlite

from ..config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Database Schema
# =============================================================================

SCHEMA = """
-- System configuration key-value store
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RS485-ETH Gateway chains
CREATE TABLE IF NOT EXISTS gateways (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    port INTEGER DEFAULT 4196,
    enabled INTEGER DEFAULT 1,
    online INTEGER DEFAULT 0,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ip_address, port)
);

-- Devices (sensors, relay controllers)
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    gateway_id TEXT REFERENCES gateways(id) ON DELETE CASCADE,
    modbus_address INTEGER NOT NULL,
    device_type TEXT NOT NULL CHECK(device_type IN ('sensor', 'relay_controller')),
    model TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    wifi_ip TEXT,
    wifi_enabled INTEGER DEFAULT 0,
    poll_interval INTEGER DEFAULT 10,
    enabled INTEGER DEFAULT 1,
    online INTEGER DEFAULT 0,
    last_seen TIMESTAMP,
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gateway_id, modbus_address)
);

-- Channels (individual sensors/relays within a device)
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    device_id TEXT REFERENCES devices(id) ON DELETE CASCADE,
    channel_num INTEGER NOT NULL,
    channel_type TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    unit TEXT,
    min_value REAL,
    max_value REAL,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_id, channel_num)
);

-- Sensor readings history
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    value REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relay state changes
CREATE TABLE IF NOT EXISTS relay_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    state INTEGER NOT NULL,
    source TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedules
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    channel_id TEXT REFERENCES channels(id) ON DELETE CASCADE,
    name TEXT,
    enabled INTEGER DEFAULT 1,
    time_on TEXT NOT NULL,
    time_off TEXT NOT NULL,
    days_of_week TEXT DEFAULT '[0,1,2,3,4,5,6]',
    priority INTEGER DEFAULT 0,
    sync_to_esp32 INTEGER DEFAULT 1,
    esp32_synced_at TIMESTAMP,
    a64core_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger rules
CREATE TABLE IF NOT EXISTS triggers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    source_channel_id TEXT REFERENCES channels(id) ON DELETE CASCADE,
    operator TEXT NOT NULL CHECK(operator IN ('>', '<', '>=', '<=', '==', '!=')),
    threshold REAL NOT NULL,
    target_channel_id TEXT REFERENCES channels(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK(action IN ('on', 'off', 'toggle')),
    duration INTEGER,
    cooldown INTEGER DEFAULT 300,
    priority INTEGER DEFAULT 0,
    last_triggered TIMESTAMP,
    a64core_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ESP32 sync tracking
CREATE TABLE IF NOT EXISTS esp32_sync (
    device_id TEXT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    schedules_hash TEXT,
    last_sync TIMESTAMP,
    sync_status TEXT CHECK(sync_status IN ('synced', 'pending', 'failed')),
    error_message TEXT
);

-- Sensor/Device Model Registry
-- Defines how to communicate with different device models
CREATE TABLE IF NOT EXISTS sensor_models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    manufacturer TEXT,
    device_type TEXT NOT NULL CHECK(device_type IN ('sensor', 'relay_controller')),
    description TEXT,
    default_poll_interval INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Register Mappings for Sensor Models
-- Defines how to read each channel type from a device model
CREATE TABLE IF NOT EXISTS register_mappings (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL REFERENCES sensor_models(id) ON DELETE CASCADE,
    channel_type TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    register_address INTEGER NOT NULL,
    register_count INTEGER DEFAULT 1,
    function_code TEXT NOT NULL CHECK(function_code IN ('read_holding', 'read_input', 'read_coil', 'write_coil', 'write_register')),
    data_type TEXT DEFAULT 'uint16' CHECK(data_type IN ('uint16', 'int16', 'uint32', 'int32', 'float32', 'bool')),
    byte_order TEXT DEFAULT 'big' CHECK(byte_order IN ('big', 'little')),
    scale REAL DEFAULT 1.0,
    offset REAL DEFAULT 0.0,
    unit TEXT,
    min_value REAL,
    max_value REAL,
    category TEXT,
    channel_num INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_id, channel_type),
    UNIQUE(model_id, channel_num)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_readings_channel_time ON readings(channel_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_relay_states_channel_time ON relay_states(channel_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_devices_gateway ON devices(gateway_id);
CREATE INDEX IF NOT EXISTS idx_channels_device ON channels(device_id);
CREATE INDEX IF NOT EXISTS idx_schedules_channel ON schedules(channel_id);
CREATE INDEX IF NOT EXISTS idx_triggers_source ON triggers(source_channel_id);
CREATE INDEX IF NOT EXISTS idx_triggers_target ON triggers(target_channel_id);
CREATE INDEX IF NOT EXISTS idx_register_mappings_model ON register_mappings(model_id);
"""

# =============================================================================
# Default Sensor Models - Seed Data
# =============================================================================

DEFAULT_SENSOR_MODELS = [
    {
        "id": "model-sht20",
        "name": "SHT20",
        "manufacturer": "Sensirion",
        "device_type": "sensor",
        "description": "RS485 Temperature and Humidity Sensor",
        "default_poll_interval": 10
    },
    {
        "id": "model-soil-7in1",
        "name": "Soil-7in1",
        "manufacturer": "Generic",
        "device_type": "sensor",
        "description": "7-in-1 Soil Sensor (NPK, pH, EC, Moisture, Temperature)",
        "default_poll_interval": 10
    },
    {
        "id": "model-esp32-6ch",
        "name": "ESP32-6CH",
        "manufacturer": "Custom",
        "device_type": "relay_controller",
        "description": "ESP32-based 6-channel Relay Controller",
        "default_poll_interval": 5
    }
]

DEFAULT_REGISTER_MAPPINGS = [
    # SHT20 mappings - uses INPUT registers
    {"id": "map-sht20-temp", "model_id": "model-sht20", "channel_type": "temperature", "channel_name": "Temperature",
     "register_address": 1, "register_count": 1, "function_code": "read_input", "data_type": "uint16",
     "scale": 0.1, "offset": 0, "unit": "C", "category": "environment", "channel_num": 1},
    {"id": "map-sht20-hum", "model_id": "model-sht20", "channel_type": "humidity", "channel_name": "Humidity",
     "register_address": 2, "register_count": 1, "function_code": "read_input", "data_type": "uint16",
     "scale": 0.1, "offset": 0, "unit": "%", "category": "environment", "channel_num": 2},

    # Soil 7-in-1 mappings - uses HOLDING registers starting at address 6
    {"id": "map-soil-moist", "model_id": "model-soil-7in1", "channel_type": "moisture", "channel_name": "Soil Moisture",
     "register_address": 6, "register_count": 1, "function_code": "read_holding", "data_type": "uint16",
     "scale": 0.1, "offset": 0, "unit": "%", "category": "soil", "channel_num": 1},
    {"id": "map-soil-temp", "model_id": "model-soil-7in1", "channel_type": "temperature", "channel_name": "Soil Temperature",
     "register_address": 7, "register_count": 1, "function_code": "read_holding", "data_type": "uint16",
     "scale": 0.01, "offset": 0, "unit": "C", "category": "soil", "channel_num": 2},
    {"id": "map-soil-ec", "model_id": "model-soil-7in1", "channel_type": "conductivity", "channel_name": "Soil EC",
     "register_address": 8, "register_count": 1, "function_code": "read_holding", "data_type": "uint16",
     "scale": 1, "offset": 0, "unit": "uS/cm", "category": "soil", "channel_num": 3},
    {"id": "map-soil-ph", "model_id": "model-soil-7in1", "channel_type": "ph", "channel_name": "Soil pH",
     "register_address": 9, "register_count": 1, "function_code": "read_holding", "data_type": "uint16",
     "scale": 0.01, "offset": 0, "unit": "pH", "category": "soil", "channel_num": 4},
    {"id": "map-soil-n", "model_id": "model-soil-7in1", "channel_type": "nitrogen", "channel_name": "Nitrogen",
     "register_address": 10, "register_count": 1, "function_code": "read_holding", "data_type": "uint16",
     "scale": 1, "offset": 0, "unit": "mg/kg", "category": "soil", "channel_num": 5},
    {"id": "map-soil-p", "model_id": "model-soil-7in1", "channel_type": "phosphorus", "channel_name": "Phosphorus",
     "register_address": 11, "register_count": 1, "function_code": "read_holding", "data_type": "uint16",
     "scale": 1, "offset": 0, "unit": "mg/kg", "category": "soil", "channel_num": 6},
    {"id": "map-soil-k", "model_id": "model-soil-7in1", "channel_type": "potassium", "channel_name": "Potassium",
     "register_address": 12, "register_count": 1, "function_code": "read_holding", "data_type": "uint16",
     "scale": 1, "offset": 0, "unit": "mg/kg", "category": "soil", "channel_num": 7},

    # ESP32-6CH relay mappings - uses COILS
    {"id": "map-esp32-ch0", "model_id": "model-esp32-6ch", "channel_type": "relay", "channel_name": "Channel 0",
     "register_address": 0, "register_count": 1, "function_code": "write_coil", "data_type": "bool",
     "scale": 1, "offset": 0, "category": "relay", "channel_num": 0},
    {"id": "map-esp32-ch1", "model_id": "model-esp32-6ch", "channel_type": "relay", "channel_name": "Channel 1",
     "register_address": 1, "register_count": 1, "function_code": "write_coil", "data_type": "bool",
     "scale": 1, "offset": 0, "category": "relay", "channel_num": 1},
    {"id": "map-esp32-ch2", "model_id": "model-esp32-6ch", "channel_type": "relay", "channel_name": "Channel 2",
     "register_address": 2, "register_count": 1, "function_code": "write_coil", "data_type": "bool",
     "scale": 1, "offset": 0, "category": "relay", "channel_num": 2},
    {"id": "map-esp32-ch3", "model_id": "model-esp32-6ch", "channel_type": "relay", "channel_name": "Channel 3",
     "register_address": 3, "register_count": 1, "function_code": "write_coil", "data_type": "bool",
     "scale": 1, "offset": 0, "category": "relay", "channel_num": 3},
    {"id": "map-esp32-ch4", "model_id": "model-esp32-6ch", "channel_type": "relay", "channel_name": "Channel 4",
     "register_address": 4, "register_count": 1, "function_code": "write_coil", "data_type": "bool",
     "scale": 1, "offset": 0, "category": "relay", "channel_num": 4},
    {"id": "map-esp32-ch5", "model_id": "model-esp32-6ch", "channel_type": "relay", "channel_name": "Channel 5",
     "register_address": 5, "register_count": 1, "function_code": "write_coil", "data_type": "bool",
     "scale": 1, "offset": 0, "category": "relay", "channel_num": 5},
]


# =============================================================================
# Database Class
# =============================================================================

class Database:
    """Async SQLite database manager with WAL mode"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or settings.database_path)
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to database and initialize schema"""
        if self._connection is not None:
            return

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Connecting to database: {self.db_path}")

        self._connection = await aiosqlite.connect(
            self.db_path,
            isolation_level=None  # Auto-commit mode
        )

        # Enable WAL mode for crash resistance
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._connection.execute("PRAGMA busy_timeout=5000")

        # Row factory for dict-like access
        self._connection.row_factory = aiosqlite.Row

        # Initialize schema
        await self._init_schema()

        logger.info("Database connected and initialized")

    async def _init_schema(self) -> None:
        """Create tables if they don't exist"""
        await self._connection.executescript(SCHEMA)
        await self._connection.commit()

        # Seed default sensor models if not present
        await self._seed_default_models()

    async def _seed_default_models(self) -> None:
        """Seed default sensor models and register mappings"""
        # Check if models already exist
        cursor = await self._connection.execute(
            "SELECT COUNT(*) FROM sensor_models"
        )
        count = (await cursor.fetchone())[0]

        if count > 0:
            return  # Already seeded

        logger.info("Seeding default sensor models...")

        # Insert default models
        for model in DEFAULT_SENSOR_MODELS:
            await self._connection.execute(
                """
                INSERT OR IGNORE INTO sensor_models
                (id, name, manufacturer, device_type, description, default_poll_interval)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    model["id"], model["name"], model.get("manufacturer"),
                    model["device_type"], model.get("description"),
                    model.get("default_poll_interval", 10)
                )
            )

        # Insert default register mappings
        for mapping in DEFAULT_REGISTER_MAPPINGS:
            await self._connection.execute(
                """
                INSERT OR IGNORE INTO register_mappings
                (id, model_id, channel_type, channel_name, register_address,
                 register_count, function_code, data_type, byte_order,
                 scale, offset, unit, min_value, max_value, category, channel_num)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping["id"], mapping["model_id"], mapping["channel_type"],
                    mapping["channel_name"], mapping["register_address"],
                    mapping.get("register_count", 1), mapping["function_code"],
                    mapping.get("data_type", "uint16"), mapping.get("byte_order", "big"),
                    mapping.get("scale", 1.0), mapping.get("offset", 0.0),
                    mapping.get("unit"), mapping.get("min_value"),
                    mapping.get("max_value"), mapping.get("category"),
                    mapping["channel_num"]
                )
            )

        await self._connection.commit()
        logger.info(f"Seeded {len(DEFAULT_SENSOR_MODELS)} models and {len(DEFAULT_REGISTER_MAPPINGS)} mappings")

    async def close(self) -> None:
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    async def execute(
        self,
        query: str,
        params: tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = False
    ) -> Any:
        """Execute a query with optional fetch"""
        async with self._lock:
            cursor = await self._connection.execute(query, params)

            if fetch_one:
                return await cursor.fetchone()
            elif fetch_all:
                return await cursor.fetchall()
            else:
                await self._connection.commit()
                return cursor.lastrowid

    async def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """Execute a query with multiple parameter sets"""
        async with self._lock:
            await self._connection.executemany(query, params_list)
            await self._connection.commit()

    # =========================================================================
    # Integrity & Maintenance
    # =========================================================================

    async def check_integrity(self) -> bool:
        """Check database integrity"""
        result = await self.execute(
            "PRAGMA integrity_check",
            fetch_one=True
        )
        return result[0] == "ok" if result else False

    async def cleanup_old_readings(self, days: int = None) -> int:
        """Delete readings older than specified days"""
        days = days or settings.db_retention_days
        cutoff = datetime.now() - timedelta(days=days)

        cursor = await self._connection.execute(
            "DELETE FROM readings WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        await self._connection.commit()

        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old readings (>{days} days)")

        return deleted

    async def cleanup_old_relay_states(self, days: int = None) -> int:
        """Delete relay states older than specified days"""
        days = days or settings.db_retention_days
        cutoff = datetime.now() - timedelta(days=days)

        cursor = await self._connection.execute(
            "DELETE FROM relay_states WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        await self._connection.commit()

        return cursor.rowcount

    async def vacuum(self) -> None:
        """Reclaim disk space"""
        await self._connection.execute("VACUUM")
        logger.info("Database vacuumed")

    # =========================================================================
    # System Config
    # =========================================================================

    async def get_config(self, key: str, default: Any = None) -> Any:
        """Get a system config value"""
        row = await self.execute(
            "SELECT value FROM system_config WHERE key = ?",
            (key,),
            fetch_one=True
        )
        return row["value"] if row else default

    async def set_config(self, key: str, value: Any) -> None:
        """Set a system config value"""
        await self.execute(
            """
            INSERT INTO system_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, str(value))
        )

    # =========================================================================
    # Gateway Operations
    # =========================================================================

    async def get_all_gateways(self) -> List[dict]:
        """Get all gateways"""
        rows = await self.execute(
            "SELECT * FROM gateways ORDER BY name",
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_gateway(self, gateway_id: str) -> Optional[dict]:
        """Get a gateway by ID"""
        row = await self.execute(
            "SELECT * FROM gateways WHERE id = ?",
            (gateway_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def create_gateway(self, gateway: dict) -> str:
        """Create a new gateway"""
        await self.execute(
            """
            INSERT INTO gateways (id, name, ip_address, port, enabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                gateway["id"],
                gateway["name"],
                gateway["ip_address"],
                gateway.get("port", 4196),
                gateway.get("enabled", True)
            )
        )
        return gateway["id"]

    async def update_gateway(self, gateway_id: str, updates: dict) -> None:
        """Update a gateway"""
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        await self.execute(
            f"UPDATE gateways SET {set_clause} WHERE id = ?",
            (*updates.values(), gateway_id)
        )

    async def update_gateway_status(
        self,
        gateway_id: str,
        online: bool,
        last_seen: datetime = None
    ) -> None:
        """Update gateway online status"""
        await self.execute(
            "UPDATE gateways SET online = ?, last_seen = ? WHERE id = ?",
            (online, (last_seen or datetime.now()).isoformat(), gateway_id)
        )

    async def delete_gateway(self, gateway_id: str) -> None:
        """Delete a gateway (cascades to devices)"""
        await self.execute("DELETE FROM gateways WHERE id = ?", (gateway_id,))

    # =========================================================================
    # Device Operations
    # =========================================================================

    async def get_all_devices(self, gateway_id: str = None) -> List[dict]:
        """Get all devices, optionally filtered by gateway"""
        if gateway_id:
            rows = await self.execute(
                "SELECT * FROM devices WHERE gateway_id = ? ORDER BY name",
                (gateway_id,),
                fetch_all=True
            )
        else:
            rows = await self.execute(
                "SELECT * FROM devices ORDER BY name",
                fetch_all=True
            )
        return [dict(row) for row in rows]

    async def get_device(self, device_id: str) -> Optional[dict]:
        """Get a device by ID"""
        row = await self.execute(
            "SELECT * FROM devices WHERE id = ?",
            (device_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def get_device_by_address(
        self,
        gateway_id: str,
        modbus_address: int
    ) -> Optional[dict]:
        """Get a device by gateway and Modbus address"""
        row = await self.execute(
            "SELECT * FROM devices WHERE gateway_id = ? AND modbus_address = ?",
            (gateway_id, modbus_address),
            fetch_one=True
        )
        return dict(row) if row else None

    async def create_device(self, device: dict) -> str:
        """Create a new device"""
        await self.execute(
            """
            INSERT INTO devices (
                id, gateway_id, modbus_address, device_type, model,
                name, category, wifi_ip, wifi_enabled, poll_interval, enabled, config
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device["id"],
                device["gateway_id"],
                device["modbus_address"],
                device["device_type"],
                device["model"],
                device["name"],
                device.get("category"),
                device.get("wifi_ip"),
                device.get("wifi_enabled", False),
                device.get("poll_interval", 10),
                device.get("enabled", True),
                device.get("config")
            )
        )
        return device["id"]

    async def update_device(self, device_id: str, updates: dict) -> None:
        """Update a device"""
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        await self.execute(
            f"UPDATE devices SET {set_clause} WHERE id = ?",
            (*updates.values(), device_id)
        )

    async def update_device_status(
        self,
        device_id: str,
        online: bool,
        last_seen: datetime = None
    ) -> None:
        """Update device online status"""
        await self.execute(
            "UPDATE devices SET online = ?, last_seen = ? WHERE id = ?",
            (online, (last_seen or datetime.now()).isoformat(), device_id)
        )

    async def delete_device(self, device_id: str) -> None:
        """Delete a device (cascades to channels)"""
        await self.execute("DELETE FROM devices WHERE id = ?", (device_id,))

    # =========================================================================
    # Channel Operations
    # =========================================================================

    async def get_device_channels(self, device_id: str) -> List[dict]:
        """Get all channels for a device"""
        rows = await self.execute(
            "SELECT * FROM channels WHERE device_id = ? ORDER BY channel_num",
            (device_id,),
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_channel(self, channel_id: str) -> Optional[dict]:
        """Get a channel by ID"""
        row = await self.execute(
            "SELECT * FROM channels WHERE id = ?",
            (channel_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def get_relay_channels(self) -> List[dict]:
        """Get all relay channels"""
        rows = await self.execute(
            """
            SELECT c.*, d.gateway_id, d.modbus_address, d.name as device_name
            FROM channels c
            JOIN devices d ON c.device_id = d.id
            WHERE c.channel_type = 'relay'
            ORDER BY d.name, c.channel_num
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_sensor_channels(self) -> List[dict]:
        """Get all sensor channels"""
        rows = await self.execute(
            """
            SELECT c.*, d.gateway_id, d.modbus_address, d.name as device_name
            FROM channels c
            JOIN devices d ON c.device_id = d.id
            WHERE c.channel_type != 'relay'
            ORDER BY d.name, c.channel_num
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def create_channel(self, channel: dict) -> str:
        """Create a new channel"""
        await self.execute(
            """
            INSERT INTO channels (
                id, device_id, channel_num, channel_type, name,
                category, unit, min_value, max_value, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                channel["id"],
                channel["device_id"],
                channel["channel_num"],
                channel["channel_type"],
                channel["name"],
                channel.get("category"),
                channel.get("unit"),
                channel.get("min_value"),
                channel.get("max_value"),
                channel.get("enabled", True)
            )
        )
        return channel["id"]

    async def update_channel(self, channel_id: str, updates: dict) -> None:
        """Update a channel"""
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        await self.execute(
            f"UPDATE channels SET {set_clause} WHERE id = ?",
            (*updates.values(), channel_id)
        )

    async def delete_channel(self, channel_id: str) -> None:
        """Delete a channel"""
        await self.execute("DELETE FROM channels WHERE id = ?", (channel_id,))

    # =========================================================================
    # Readings Operations
    # =========================================================================

    async def add_reading(self, channel_id: str, value: float) -> int:
        """Add a sensor reading"""
        return await self.execute(
            "INSERT INTO readings (channel_id, value) VALUES (?, ?)",
            (channel_id, value)
        )

    async def add_readings_batch(self, readings: List[tuple]) -> None:
        """Add multiple readings at once: [(channel_id, value), ...]"""
        await self.execute_many(
            "INSERT INTO readings (channel_id, value) VALUES (?, ?)",
            readings
        )

    async def get_latest_readings(self) -> List[dict]:
        """Get the latest reading for each sensor channel"""
        rows = await self.execute(
            """
            SELECT r.*, c.name as channel_name, c.unit, c.category,
                   c.channel_type, c.device_id, d.name as device_name
            FROM readings r
            JOIN channels c ON r.channel_id = c.id
            JOIN devices d ON c.device_id = d.id
            WHERE r.id IN (
                SELECT MAX(id) FROM readings GROUP BY channel_id
            )
            ORDER BY d.name, c.channel_num
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_latest_reading(self, channel_id: str) -> Optional[dict]:
        """Get the latest reading for a specific channel"""
        row = await self.execute(
            """
            SELECT r.*, c.name as channel_name, c.unit, c.category,
                   d.name as device_name
            FROM readings r
            JOIN channels c ON r.channel_id = c.id
            JOIN devices d ON c.device_id = d.id
            WHERE r.channel_id = ?
            ORDER BY r.timestamp DESC LIMIT 1
            """,
            (channel_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def get_channel_readings(
        self,
        channel_id: str,
        limit: int = 100,
        since: datetime = None
    ) -> List[dict]:
        """Get readings for a channel"""
        if since:
            rows = await self.execute(
                """
                SELECT * FROM readings
                WHERE channel_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (channel_id, since.isoformat(), limit),
                fetch_all=True
            )
        else:
            rows = await self.execute(
                """
                SELECT * FROM readings
                WHERE channel_id = ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (channel_id, limit),
                fetch_all=True
            )
        return [dict(row) for row in rows]

    # =========================================================================
    # Relay State Operations
    # =========================================================================

    async def add_relay_state(
        self,
        channel_id: str,
        state: bool,
        source: str
    ) -> int:
        """Record a relay state change"""
        return await self.execute(
            "INSERT INTO relay_states (channel_id, state, source) VALUES (?, ?, ?)",
            (channel_id, state, source)
        )

    async def get_last_relay_state(self, channel_id: str) -> Optional[dict]:
        """Get the last known state of a relay"""
        row = await self.execute(
            """
            SELECT * FROM relay_states
            WHERE channel_id = ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            (channel_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def get_all_relay_states(self) -> List[dict]:
        """Get current state of all relays"""
        rows = await self.execute(
            """
            SELECT rs.*, c.name as channel_name, c.category,
                   d.name as device_name, d.modbus_address
            FROM relay_states rs
            JOIN channels c ON rs.channel_id = c.id
            JOIN devices d ON c.device_id = d.id
            WHERE rs.id IN (
                SELECT MAX(id) FROM relay_states GROUP BY channel_id
            )
            ORDER BY d.name, c.channel_num
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    # =========================================================================
    # Schedule Operations
    # =========================================================================

    async def get_all_schedules(self) -> List[dict]:
        """Get all schedules"""
        rows = await self.execute(
            """
            SELECT s.*, c.name as channel_name, c.category,
                   d.name as device_name
            FROM schedules s
            JOIN channels c ON s.channel_id = c.id
            JOIN devices d ON c.device_id = d.id
            ORDER BY s.name
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_enabled_schedules(self) -> List[dict]:
        """Get all enabled schedules"""
        rows = await self.execute(
            """
            SELECT s.*, c.name as channel_name, c.category,
                   d.name as device_name, d.id as device_id,
                   c.channel_num
            FROM schedules s
            JOIN channels c ON s.channel_id = c.id
            JOIN devices d ON c.device_id = d.id
            WHERE s.enabled = 1
            ORDER BY s.priority DESC, s.name
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_schedule(self, schedule_id: str) -> Optional[dict]:
        """Get a schedule by ID"""
        row = await self.execute(
            "SELECT * FROM schedules WHERE id = ?",
            (schedule_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def create_schedule(self, schedule: dict) -> str:
        """Create a new schedule"""
        await self.execute(
            """
            INSERT INTO schedules (
                id, channel_id, name, enabled, time_on, time_off,
                days_of_week, priority, sync_to_esp32, a64core_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule["id"],
                schedule["channel_id"],
                schedule.get("name"),
                schedule.get("enabled", True),
                schedule["time_on"],
                schedule["time_off"],
                schedule.get("days_of_week", "[0,1,2,3,4,5,6]"),
                schedule.get("priority", 0),
                schedule.get("sync_to_esp32", True),
                schedule.get("a64core_id")
            )
        )
        return schedule["id"]

    async def update_schedule(self, schedule_id: str, updates: dict) -> None:
        """Update a schedule"""
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        await self.execute(
            f"UPDATE schedules SET {set_clause} WHERE id = ?",
            (*updates.values(), schedule_id)
        )

    async def delete_schedule(self, schedule_id: str) -> None:
        """Delete a schedule"""
        await self.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))

    # =========================================================================
    # Trigger Operations
    # =========================================================================

    async def get_all_triggers(self) -> List[dict]:
        """Get all triggers"""
        rows = await self.execute(
            """
            SELECT t.*,
                   sc.name as source_channel_name,
                   tc.name as target_channel_name
            FROM triggers t
            JOIN channels sc ON t.source_channel_id = sc.id
            JOIN channels tc ON t.target_channel_id = tc.id
            ORDER BY t.name
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_enabled_triggers(self) -> List[dict]:
        """Get all enabled triggers"""
        rows = await self.execute(
            """
            SELECT t.*,
                   sc.name as source_channel_name, sc.device_id as source_device_id,
                   tc.name as target_channel_name, tc.device_id as target_device_id,
                   tc.channel_num as target_channel_num
            FROM triggers t
            JOIN channels sc ON t.source_channel_id = sc.id
            JOIN channels tc ON t.target_channel_id = tc.id
            WHERE t.enabled = 1
            ORDER BY t.priority DESC, t.name
            """,
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_trigger(self, trigger_id: str) -> Optional[dict]:
        """Get a trigger by ID"""
        row = await self.execute(
            "SELECT * FROM triggers WHERE id = ?",
            (trigger_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def create_trigger(self, trigger: dict) -> str:
        """Create a new trigger"""
        await self.execute(
            """
            INSERT INTO triggers (
                id, name, enabled, source_channel_id, operator, threshold,
                target_channel_id, action, duration, cooldown, priority, a64core_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trigger["id"],
                trigger["name"],
                trigger.get("enabled", True),
                trigger["source_channel_id"],
                trigger["operator"],
                trigger["threshold"],
                trigger["target_channel_id"],
                trigger["action"],
                trigger.get("duration"),
                trigger.get("cooldown", 300),
                trigger.get("priority", 0),
                trigger.get("a64core_id")
            )
        )
        return trigger["id"]

    async def update_trigger(self, trigger_id: str, updates: dict) -> None:
        """Update a trigger"""
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        await self.execute(
            f"UPDATE triggers SET {set_clause} WHERE id = ?",
            (*updates.values(), trigger_id)
        )

    async def update_trigger_last_triggered(self, trigger_id: str) -> None:
        """Update the last_triggered timestamp"""
        await self.execute(
            "UPDATE triggers SET last_triggered = CURRENT_TIMESTAMP WHERE id = ?",
            (trigger_id,)
        )

    async def delete_trigger(self, trigger_id: str) -> None:
        """Delete a trigger"""
        await self.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))

    # =========================================================================
    # Sensor Model Operations
    # =========================================================================

    async def get_all_sensor_models(self) -> List[dict]:
        """Get all sensor models"""
        rows = await self.execute(
            "SELECT * FROM sensor_models ORDER BY name",
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_sensor_model(self, model_id: str) -> Optional[dict]:
        """Get a sensor model by ID"""
        row = await self.execute(
            "SELECT * FROM sensor_models WHERE id = ?",
            (model_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def get_sensor_model_by_name(self, name: str) -> Optional[dict]:
        """Get a sensor model by name (case-insensitive)"""
        row = await self.execute(
            "SELECT * FROM sensor_models WHERE LOWER(name) = LOWER(?)",
            (name,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def create_sensor_model(self, model: dict) -> str:
        """Create a new sensor model"""
        await self.execute(
            """
            INSERT INTO sensor_models
            (id, name, manufacturer, device_type, description, default_poll_interval)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                model["id"],
                model["name"],
                model.get("manufacturer"),
                model["device_type"],
                model.get("description"),
                model.get("default_poll_interval", 10)
            )
        )
        return model["id"]

    async def update_sensor_model(self, model_id: str, updates: dict) -> None:
        """Update a sensor model"""
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        await self.execute(
            f"UPDATE sensor_models SET {set_clause} WHERE id = ?",
            (*updates.values(), model_id)
        )

    async def delete_sensor_model(self, model_id: str) -> None:
        """Delete a sensor model (cascades to mappings)"""
        await self.execute("DELETE FROM sensor_models WHERE id = ?", (model_id,))

    # =========================================================================
    # Register Mapping Operations
    # =========================================================================

    async def get_model_mappings(self, model_id: str) -> List[dict]:
        """Get all register mappings for a sensor model"""
        rows = await self.execute(
            """
            SELECT rm.*, sm.name as model_name
            FROM register_mappings rm
            JOIN sensor_models sm ON rm.model_id = sm.id
            WHERE rm.model_id = ?
            ORDER BY rm.channel_num
            """,
            (model_id,),
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_mappings_by_model_name(self, model_name: str) -> List[dict]:
        """Get register mappings by model name (case-insensitive)"""
        rows = await self.execute(
            """
            SELECT rm.*, sm.name as model_name
            FROM register_mappings rm
            JOIN sensor_models sm ON rm.model_id = sm.id
            WHERE LOWER(sm.name) = LOWER(?)
            ORDER BY rm.channel_num
            """,
            (model_name,),
            fetch_all=True
        )
        return [dict(row) for row in rows]

    async def get_register_mapping(self, mapping_id: str) -> Optional[dict]:
        """Get a register mapping by ID"""
        row = await self.execute(
            "SELECT * FROM register_mappings WHERE id = ?",
            (mapping_id,),
            fetch_one=True
        )
        return dict(row) if row else None

    async def create_register_mapping(self, mapping: dict) -> str:
        """Create a new register mapping"""
        await self.execute(
            """
            INSERT INTO register_mappings
            (id, model_id, channel_type, channel_name, register_address,
             register_count, function_code, data_type, byte_order,
             scale, offset, unit, min_value, max_value, category, channel_num)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mapping["id"],
                mapping["model_id"],
                mapping["channel_type"],
                mapping["channel_name"],
                mapping["register_address"],
                mapping.get("register_count", 1),
                mapping["function_code"],
                mapping.get("data_type", "uint16"),
                mapping.get("byte_order", "big"),
                mapping.get("scale", 1.0),
                mapping.get("offset", 0.0),
                mapping.get("unit"),
                mapping.get("min_value"),
                mapping.get("max_value"),
                mapping.get("category"),
                mapping["channel_num"]
            )
        )
        return mapping["id"]

    async def update_register_mapping(self, mapping_id: str, updates: dict) -> None:
        """Update a register mapping"""
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        await self.execute(
            f"UPDATE register_mappings SET {set_clause} WHERE id = ?",
            (*updates.values(), mapping_id)
        )

    async def delete_register_mapping(self, mapping_id: str) -> None:
        """Delete a register mapping"""
        await self.execute("DELETE FROM register_mappings WHERE id = ?", (mapping_id,))


# =============================================================================
# Global Database Instance
# =============================================================================

_db_instance: Optional[Database] = None


async def get_db() -> Database:
    """Get the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        await _db_instance.connect()
    return _db_instance


async def close_db() -> None:
    """Close the global database instance"""
    global _db_instance
    if _db_instance:
        await _db_instance.close()
        _db_instance = None
