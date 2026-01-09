"""
Configuration Management

Uses pydantic-settings for type-safe configuration with environment variable support.
All settings can be overridden via environment variables or .env file.
"""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # =========================================================================
    # API Server
    # =========================================================================
    api_host: str = Field(default="0.0.0.0", description="API server bind address")
    api_port: int = Field(default=8000, description="API server port")
    api_key: str = Field(default="", description="API key for authenticated endpoints")

    # =========================================================================
    # Dashboard
    # =========================================================================
    dashboard_port: int = Field(default=8080, description="Dashboard web UI port")
    dashboard_user: str = Field(default="admin", description="Dashboard username")
    dashboard_password: str = Field(default="", description="Dashboard password")

    # =========================================================================
    # Database
    # =========================================================================
    database_path: str = Field(default="data/controller.db", description="SQLite database path")
    db_backup_enabled: bool = Field(default=True, description="Enable automatic backups")
    db_backup_interval: int = Field(default=3600, description="Backup interval in seconds")
    db_retention_days: int = Field(default=30, description="Days to retain sensor readings")

    # =========================================================================
    # Default Gateway
    # =========================================================================
    default_gateway_ip: str = Field(default="192.168.1.201", description="Default RS485-ETH gateway IP")
    default_gateway_port: int = Field(default=4196, description="Default gateway port")

    # =========================================================================
    # Polling & Timeouts
    # =========================================================================
    sensor_poll_interval: int = Field(default=10, description="Seconds between sensor polls")
    modbus_timeout: float = Field(default=3.0, description="Modbus request timeout")
    gateway_reconnect_interval: int = Field(default=30, description="Seconds between reconnection attempts")

    # =========================================================================
    # Robustness
    # =========================================================================
    watchdog_enabled: bool = Field(default=True, description="Enable systemd watchdog")
    watchdog_timeout: int = Field(default=60, description="Watchdog timeout in seconds")
    startup_delay: int = Field(default=10, description="Seconds to wait on startup for network")
    recover_relay_states: bool = Field(default=True, description="Restore relay states on boot")
    schedule_catchup: bool = Field(default=True, description="Apply missed schedules on boot")

    # =========================================================================
    # Logging
    # =========================================================================
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/controller.log", description="Log file path")
    log_max_size_mb: int = Field(default=50, description="Max log file size in MB")
    log_backup_count: int = Field(default=3, description="Number of log backups to keep")

    # =========================================================================
    # A64Core Sync
    # =========================================================================
    a64core_url: Optional[str] = Field(default=None, description="A64Core API URL")
    a64core_api_key: Optional[str] = Field(default=None, description="A64Core API key")
    sync_enabled: bool = Field(default=False, description="Enable A64Core sync")

    # =========================================================================
    # Computed Properties
    # =========================================================================
    @property
    def database_full_path(self) -> Path:
        """Get absolute path to database"""
        return Path(self.database_path).resolve()

    @property
    def log_full_path(self) -> Path:
        """Get absolute path to log file"""
        return Path(self.log_file).resolve()

    def ensure_directories(self):
        """Create necessary directories"""
        self.database_full_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_full_path.parent.mkdir(parents=True, exist_ok=True)
        Path("backups").mkdir(exist_ok=True)


# Global settings instance
settings = Settings()
