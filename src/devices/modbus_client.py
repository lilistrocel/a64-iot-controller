"""
Modbus TCP Client Wrapper

Handles communication with RS485-ETH gateways using pymodbus.
Supports automatic reconnection and error handling.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModbusResponse:
    """Response from a Modbus operation"""
    success: bool
    data: Optional[List[int]] = None
    error: Optional[str] = None


class ModbusClient:
    """
    Async Modbus TCP client for RS485-ETH gateway communication.

    Features:
    - Automatic reconnection on connection loss
    - Configurable timeout and retries
    - Thread-safe async operations
    """

    def __init__(
        self,
        host: str,
        port: int = 4196,
        timeout: float = None,
        retries: int = 3
    ):
        self.host = host
        self.port = port
        self.timeout = timeout or settings.modbus_timeout
        self.retries = retries
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected and self._client is not None

    async def connect(self) -> bool:
        """
        Connect to the Modbus gateway.

        Returns:
            True if connection successful, False otherwise
        """
        async with self._lock:
            if self._connected and self._client:
                return True

            try:
                logger.info(f"Connecting to Modbus gateway {self.host}:{self.port}")

                self._client = AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout
                )

                connected = await self._client.connect()

                if connected:
                    self._connected = True
                    logger.info(f"Connected to Modbus gateway {self.host}:{self.port}")
                    return True
                else:
                    logger.error(f"Failed to connect to {self.host}:{self.port}")
                    self._client = None
                    return False

            except Exception as e:
                logger.error(f"Connection error to {self.host}:{self.port}: {e}")
                self._client = None
                self._connected = False
                return False

    async def disconnect(self) -> None:
        """Disconnect from the Modbus gateway"""
        async with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
                finally:
                    self._client = None
                    self._connected = False
                    logger.info(f"Disconnected from {self.host}:{self.port}")

    async def _ensure_connected(self) -> bool:
        """Ensure connection is established, reconnect if needed"""
        if not self._connected or not self._client:
            return await self.connect()
        return True

    async def read_holding_registers(
        self,
        address: int,
        count: int,
        slave: int
    ) -> ModbusResponse:
        """
        Read holding registers from a device.

        Args:
            address: Starting register address
            count: Number of registers to read
            slave: Modbus slave address (device address)

        Returns:
            ModbusResponse with data or error
        """
        for attempt in range(self.retries):
            try:
                if not await self._ensure_connected():
                    return ModbusResponse(
                        success=False,
                        error="Failed to connect to gateway"
                    )

                async with self._lock:
                    response = await self._client.read_holding_registers(
                        address=address,
                        count=count,
                        device_id=slave
                    )

                if response.isError():
                    error_msg = str(response)
                    logger.warning(
                        f"Modbus error reading slave {slave}, "
                        f"addr {address}: {error_msg}"
                    )
                    return ModbusResponse(success=False, error=error_msg)

                return ModbusResponse(
                    success=True,
                    data=list(response.registers)
                )

            except ConnectionException as e:
                logger.warning(f"Connection lost (attempt {attempt + 1}): {e}")
                self._connected = False
                if attempt < self.retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return ModbusResponse(success=False, error=f"Connection lost: {e}")

            except ModbusException as e:
                logger.error(f"Modbus exception: {e}")
                return ModbusResponse(success=False, error=str(e))

            except Exception as e:
                logger.error(f"Unexpected error reading registers: {e}")
                return ModbusResponse(success=False, error=str(e))

        return ModbusResponse(success=False, error="Max retries exceeded")

    async def read_input_registers(
        self,
        address: int,
        count: int,
        slave: int
    ) -> ModbusResponse:
        """
        Read input registers from a device.

        Args:
            address: Starting register address
            count: Number of registers to read
            slave: Modbus slave address

        Returns:
            ModbusResponse with data or error
        """
        for attempt in range(self.retries):
            try:
                if not await self._ensure_connected():
                    return ModbusResponse(
                        success=False,
                        error="Failed to connect to gateway"
                    )

                async with self._lock:
                    response = await self._client.read_input_registers(
                        address=address,
                        count=count,
                        device_id=slave
                    )

                if response.isError():
                    return ModbusResponse(success=False, error=str(response))

                return ModbusResponse(
                    success=True,
                    data=list(response.registers)
                )

            except ConnectionException as e:
                logger.warning(f"Connection lost (attempt {attempt + 1}): {e}")
                self._connected = False
                if attempt < self.retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return ModbusResponse(success=False, error=f"Connection lost: {e}")

            except Exception as e:
                logger.error(f"Error reading input registers: {e}")
                return ModbusResponse(success=False, error=str(e))

        return ModbusResponse(success=False, error="Max retries exceeded")

    async def write_single_register(
        self,
        address: int,
        value: int,
        slave: int
    ) -> ModbusResponse:
        """
        Write a single holding register.

        Args:
            address: Register address
            value: Value to write (0-65535)
            slave: Modbus slave address

        Returns:
            ModbusResponse indicating success/failure
        """
        for attempt in range(self.retries):
            try:
                if not await self._ensure_connected():
                    return ModbusResponse(
                        success=False,
                        error="Failed to connect to gateway"
                    )

                async with self._lock:
                    response = await self._client.write_register(
                        address=address,
                        value=value,
                        device_id=slave
                    )

                if response.isError():
                    return ModbusResponse(success=False, error=str(response))

                logger.debug(
                    f"Written value {value} to slave {slave}, addr {address}"
                )
                return ModbusResponse(success=True)

            except ConnectionException as e:
                logger.warning(f"Connection lost (attempt {attempt + 1}): {e}")
                self._connected = False
                if attempt < self.retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return ModbusResponse(success=False, error=f"Connection lost: {e}")

            except Exception as e:
                logger.error(f"Error writing register: {e}")
                return ModbusResponse(success=False, error=str(e))

        return ModbusResponse(success=False, error="Max retries exceeded")

    async def write_coil(
        self,
        address: int,
        value: bool,
        slave: int
    ) -> ModbusResponse:
        """
        Write a single coil (for relay control).

        Args:
            address: Coil address
            value: True for ON, False for OFF
            slave: Modbus slave address

        Returns:
            ModbusResponse indicating success/failure
        """
        for attempt in range(self.retries):
            try:
                if not await self._ensure_connected():
                    return ModbusResponse(
                        success=False,
                        error="Failed to connect to gateway"
                    )

                async with self._lock:
                    response = await self._client.write_coil(
                        address=address,
                        value=value,
                        device_id=slave
                    )

                if response.isError():
                    return ModbusResponse(success=False, error=str(response))

                logger.debug(
                    f"Written coil {'ON' if value else 'OFF'} to "
                    f"slave {slave}, addr {address}"
                )
                return ModbusResponse(success=True)

            except ConnectionException as e:
                logger.warning(f"Connection lost (attempt {attempt + 1}): {e}")
                self._connected = False
                if attempt < self.retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return ModbusResponse(success=False, error=f"Connection lost: {e}")

            except Exception as e:
                logger.error(f"Error writing coil: {e}")
                return ModbusResponse(success=False, error=str(e))

        return ModbusResponse(success=False, error="Max retries exceeded")

    async def read_coils(
        self,
        address: int,
        count: int,
        slave: int
    ) -> ModbusResponse:
        """
        Read coil status (for relay state).

        Args:
            address: Starting coil address
            count: Number of coils to read
            slave: Modbus slave address

        Returns:
            ModbusResponse with coil states (as 0/1 values)
        """
        for attempt in range(self.retries):
            try:
                if not await self._ensure_connected():
                    return ModbusResponse(
                        success=False,
                        error="Failed to connect to gateway"
                    )

                async with self._lock:
                    response = await self._client.read_coils(
                        address=address,
                        count=count,
                        device_id=slave
                    )

                if response.isError():
                    return ModbusResponse(success=False, error=str(response))

                # Convert bits to list of 0/1
                coil_values = [1 if bit else 0 for bit in response.bits[:count]]
                return ModbusResponse(success=True, data=coil_values)

            except ConnectionException as e:
                logger.warning(f"Connection lost (attempt {attempt + 1}): {e}")
                self._connected = False
                if attempt < self.retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return ModbusResponse(success=False, error=f"Connection lost: {e}")

            except Exception as e:
                logger.error(f"Error reading coils: {e}")
                return ModbusResponse(success=False, error=str(e))

        return ModbusResponse(success=False, error="Max retries exceeded")
