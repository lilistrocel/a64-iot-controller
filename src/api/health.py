"""
Health Check Endpoints

System health monitoring and status endpoints.
"""

import time
from datetime import datetime
from typing import Dict, Any

import psutil
from fastapi import APIRouter

from ..config import settings
from ..core.database import get_db
from .. import __version__

router = APIRouter()

# Track startup time
_start_time = time.time()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint.

    Returns system status including:
    - Database connectivity
    - Memory usage
    - Disk usage
    - Uptime
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": __version__,
        "uptime_seconds": round(time.time() - _start_time, 2),
        "checks": {}
    }

    # Database check
    try:
        db = await get_db()
        is_ok = await db.check_integrity()
        health["checks"]["database"] = {
            "status": "ok" if is_ok else "error",
            "path": str(settings.database_path)
        }
        if not is_ok:
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["database"] = {"status": "error", "message": str(e)}
        health["status"] = "unhealthy"

    # Memory check
    try:
        memory = psutil.virtual_memory()
        health["checks"]["memory"] = {
            "status": "ok" if memory.percent < 80 else "warning",
            "percent": round(memory.percent, 1),
            "available_mb": round(memory.available / (1024 * 1024), 1)
        }
        if memory.percent >= 90:
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["memory"] = {"status": "error", "message": str(e)}

    # Disk check
    try:
        disk = psutil.disk_usage("/")
        health["checks"]["disk"] = {
            "status": "ok" if disk.percent < 80 else "warning",
            "percent": round(disk.percent, 1),
            "free_gb": round(disk.free / (1024 * 1024 * 1024), 2)
        }
        if disk.percent >= 95:
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["disk"] = {"status": "error", "message": str(e)}

    # CPU check
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        health["checks"]["cpu"] = {
            "status": "ok" if cpu_percent < 80 else "warning",
            "percent": round(cpu_percent, 1)
        }
    except Exception as e:
        health["checks"]["cpu"] = {"status": "error", "message": str(e)}

    return health


@router.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint - basic API info"""
    return {
        "name": "A64 IoT Controller",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health"
    }


@router.get("/status")
async def status() -> Dict[str, Any]:
    """Quick status endpoint"""
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": __version__,
        "uptime_seconds": round(time.time() - _start_time, 2)
    }


@router.get("/devices/status")
async def device_manager_status() -> Dict[str, Any]:
    """Get device manager status including gateway connections"""
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest

    # Import at runtime to avoid circular imports
    from ..main import device_manager

    if device_manager is None:
        return {
            "status": "not_initialized",
            "message": "Device manager not yet started"
        }

    return device_manager.get_status()
