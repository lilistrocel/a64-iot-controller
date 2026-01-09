"""
Device Manager

Orchestrates communication with all devices via Modbus.
Handles sensor polling, relay control, and device status tracking.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

from .modbus_client import ModbusClient
from ..core.database import Database
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class GatewayConnection:
    """Represents a connection to an RS485-ETH gateway"""
    gateway_id: str
    host: str
    port: int
    client: ModbusClient
    devices: List[dict] = field(default_factory=list)
    last_poll: Optional[datetime] = None
    error_count: int = 0


class DeviceManager:
    """
    Manages all device communication.

    Features:
    - Maintains connections to multiple gateways
    - Polls sensors at configurable intervals
    - Executes relay commands from the database
    - Tracks device online/offline status
    """

    def __init__(self, db: Database):
        self.db = db
        self._gateways: Dict[str, GatewayConnection] = {}
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._relay_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the device manager"""
        if self._running:
            logger.warning("Device manager already running")
            return

        logger.info("Starting device manager...")
        self._running = True

        # Load and connect to gateways
        await self._load_gateways()

        # Start background tasks
        self._poll_task = asyncio.create_task(self._sensor_poll_loop())
        self._relay_task = asyncio.create_task(self._relay_control_loop())

        logger.info("Device manager started")

    async def stop(self) -> None:
        """Stop the device manager"""
        if not self._running:
            return

        logger.info("Stopping device manager...")
        self._running = False

        # Cancel tasks
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._relay_task:
            self._relay_task.cancel()
            try:
                await self._relay_task
            except asyncio.CancelledError:
                pass

        # Disconnect all gateways
        for gateway in self._gateways.values():
            await gateway.client.disconnect()

        self._gateways.clear()
        logger.info("Device manager stopped")

    async def _load_gateways(self) -> None:
        """Load gateway configurations and connect"""
        gateways = await self.db.get_all_gateways()

        for gw in gateways:
            if not gw["enabled"]:
                continue

            gateway_id = gw["id"]
            client = ModbusClient(
                host=gw["ip_address"],
                port=gw["port"],
                timeout=settings.modbus_timeout
            )

            # Get devices for this gateway
            devices = await self.db.get_all_devices(gateway_id)

            self._gateways[gateway_id] = GatewayConnection(
                gateway_id=gateway_id,
                host=gw["ip_address"],
                port=gw["port"],
                client=client,
                devices=[d for d in devices if d["enabled"]]
            )

            # Try to connect
            connected = await client.connect()
            await self.db.update_gateway_status(
                gateway_id,
                online=connected,
                last_seen=datetime.now() if connected else None
            )

            if connected:
                logger.info(f"Connected to gateway {gw['name']} ({gw['ip_address']})")
            else:
                logger.warning(f"Failed to connect to gateway {gw['name']}")

    async def _sensor_poll_loop(self) -> None:
        """Main sensor polling loop"""
        logger.info("Sensor polling loop started")

        while self._running:
            try:
                for gateway in self._gateways.values():
                    if not gateway.client.is_connected:
                        # Try to reconnect
                        connected = await gateway.client.connect()
                        await self.db.update_gateway_status(
                            gateway.gateway_id,
                            online=connected
                        )
                        if not connected:
                            continue

                    # Poll each device on this gateway
                    for device in gateway.devices:
                        if device["device_type"] == "sensor":
                            await self._poll_sensor(gateway, device)

                    gateway.last_poll = datetime.now()

                # Wait for next poll interval
                await asyncio.sleep(settings.sensor_poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sensor poll loop: {e}")
                await asyncio.sleep(5)

        logger.info("Sensor polling loop stopped")

    async def _poll_sensor(
        self,
        gateway: GatewayConnection,
        device: dict
    ) -> None:
        """Poll a single sensor device"""
        device_id = device["id"]
        modbus_addr = device["modbus_address"]
        model = device.get("model", "").lower()

        try:
            # Get channels for this device
            channels = await self.db.get_device_channels(device_id)

            # Read sensor data based on model
            readings = await self._read_sensor_data(
                gateway.client,
                modbus_addr,
                model,
                channels
            )

            if readings:
                # Store readings in database
                for channel_id, value in readings.items():
                    await self.db.add_reading(channel_id, value)

                # Update device status
                await self.db.update_device_status(
                    device_id,
                    online=True,
                    last_seen=datetime.now()
                )
                gateway.error_count = 0

                logger.debug(
                    f"Polled sensor {device['name']}: {len(readings)} readings"
                )
            else:
                gateway.error_count += 1
                if gateway.error_count >= 3:
                    await self.db.update_device_status(device_id, online=False)

        except Exception as e:
            logger.error(f"Error polling sensor {device['name']}: {e}")
            gateway.error_count += 1

    async def _read_sensor_data(
        self,
        client: ModbusClient,
        slave: int,
        model: str,
        channels: List[dict]
    ) -> Dict[str, float]:
        """
        Read sensor data based on device model.

        Returns dict of channel_id -> value
        """
        readings = {}

        # Soil 7-in-1 sensor (common model)
        if "soil" in model or "7in1" in model:
            # Read 7 registers starting at 0x0000
            response = await client.read_holding_registers(
                address=0x0000,
                count=7,
                slave=slave
            )

            if response.success and response.data:
                # Map registers to channel types
                register_map = {
                    0: ("moisture", 0.1),      # Moisture %
                    1: ("temperature", 0.1),   # Temp °C
                    2: ("conductivity", 1),    # EC µS/cm
                    3: ("ph", 0.1),            # pH
                    4: ("nitrogen", 1),        # N mg/kg
                    5: ("phosphorus", 1),      # P mg/kg
                    6: ("potassium", 1),       # K mg/kg
                }

                for channel in channels:
                    ch_type = channel["channel_type"].lower()
                    for reg_idx, (sensor_type, scale) in register_map.items():
                        if sensor_type in ch_type:
                            raw_value = response.data[reg_idx]
                            readings[channel["id"]] = raw_value * scale
                            break

        # Generic sensor - read holding registers based on channel_num
        else:
            for channel in channels:
                ch_num = channel["channel_num"]
                response = await client.read_holding_registers(
                    address=ch_num,
                    count=1,
                    slave=slave
                )

                if response.success and response.data:
                    # Apply simple scaling (could be enhanced with channel config)
                    readings[channel["id"]] = response.data[0] * 0.1

        return readings

    async def _relay_control_loop(self) -> None:
        """Main relay control loop - checks for pending commands"""
        logger.info("Relay control loop started")

        while self._running:
            try:
                # Get all relay channels
                relay_channels = await self.db.get_relay_channels()

                for channel in relay_channels:
                    # Get the latest desired state
                    last_state = await self.db.get_last_relay_state(channel["id"])

                    if last_state and last_state["source"] != "hardware":
                        # Send command to hardware
                        await self._send_relay_command(
                            channel,
                            bool(last_state["state"])
                        )

                # Short interval for relay responsiveness
                await asyncio.sleep(settings.sensor_poll_interval / 2)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in relay control loop: {e}")
                await asyncio.sleep(5)

        logger.info("Relay control loop stopped")

    async def _send_relay_command(
        self,
        channel: dict,
        state: bool
    ) -> bool:
        """Send a relay command to hardware"""
        gateway_id = channel.get("gateway_id")

        if not gateway_id or gateway_id not in self._gateways:
            logger.warning(f"Gateway not found for relay {channel['name']}")
            return False

        gateway = self._gateways[gateway_id]

        if not gateway.client.is_connected:
            if not await gateway.client.connect():
                return False

        modbus_addr = channel["modbus_address"]
        ch_num = channel["channel_num"]

        # Try coil write first (most relay controllers use this)
        response = await gateway.client.write_coil(
            address=ch_num - 1,  # Coils are often 0-indexed
            value=state,
            slave=modbus_addr
        )

        if response.success:
            logger.info(
                f"Relay {channel['name']} set to {'ON' if state else 'OFF'}"
            )
            return True
        else:
            # Fallback: try writing to holding register
            response = await gateway.client.write_single_register(
                address=ch_num - 1,
                value=1 if state else 0,
                slave=modbus_addr
            )

            if response.success:
                logger.info(
                    f"Relay {channel['name']} set to {'ON' if state else 'OFF'} "
                    f"(via register)"
                )
                return True

        logger.error(
            f"Failed to set relay {channel['name']}: {response.error}"
        )
        return False

    async def control_relay(
        self,
        channel_id: str,
        state: bool,
        source: str = "api"
    ) -> bool:
        """
        Control a relay immediately.

        Args:
            channel_id: The relay channel ID
            state: True for ON, False for OFF
            source: Source of command (api, schedule, trigger)

        Returns:
            True if command was sent successfully
        """
        channel = await self.db.get_channel(channel_id)
        if not channel:
            logger.error(f"Channel {channel_id} not found")
            return False

        if channel["channel_type"] != "relay":
            logger.error(f"Channel {channel_id} is not a relay")
            return False

        # Get device info
        device = await self.db.get_device(channel["device_id"])
        if not device:
            logger.error(f"Device for channel {channel_id} not found")
            return False

        gateway_id = device["gateway_id"]

        # Build channel dict with gateway info
        relay_info = {
            **channel,
            "gateway_id": gateway_id,
            "modbus_address": device["modbus_address"]
        }

        success = await self._send_relay_command(relay_info, state)

        if success:
            # Record the state change
            await self.db.add_relay_state(channel_id, state, source)

        return success

    async def read_relay_state(self, channel_id: str) -> Optional[bool]:
        """
        Read actual relay state from hardware.

        Returns:
            True if ON, False if OFF, None if read failed
        """
        channel = await self.db.get_channel(channel_id)
        if not channel:
            return None

        device = await self.db.get_device(channel["device_id"])
        if not device:
            return None

        gateway_id = device["gateway_id"]
        if gateway_id not in self._gateways:
            return None

        gateway = self._gateways[gateway_id]

        if not gateway.client.is_connected:
            if not await gateway.client.connect():
                return None

        response = await gateway.client.read_coils(
            address=channel["channel_num"] - 1,
            count=1,
            slave=device["modbus_address"]
        )

        if response.success and response.data:
            return bool(response.data[0])

        return None

    async def refresh_gateway(self, gateway_id: str) -> None:
        """Refresh devices for a gateway"""
        if gateway_id not in self._gateways:
            return

        gateway = self._gateways[gateway_id]
        devices = await self.db.get_all_devices(gateway_id)
        gateway.devices = [d for d in devices if d["enabled"]]

        logger.info(f"Refreshed gateway {gateway_id}: {len(gateway.devices)} devices")

    def get_status(self) -> Dict[str, Any]:
        """Get device manager status"""
        return {
            "running": self._running,
            "gateways": {
                gw_id: {
                    "host": gw.host,
                    "port": gw.port,
                    "connected": gw.client.is_connected,
                    "device_count": len(gw.devices),
                    "last_poll": gw.last_poll.isoformat() if gw.last_poll else None,
                    "error_count": gw.error_count
                }
                for gw_id, gw in self._gateways.items()
            }
        }
