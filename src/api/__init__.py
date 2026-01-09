"""API Router Module"""

from fastapi import APIRouter

from .gateways import router as gateways_router
from .devices import router as devices_router
from .channels import router as channels_router
from .readings import router as readings_router
from .relays import router as relays_router
from .schedules import router as schedules_router
from .triggers import router as triggers_router
from .health import router as health_router
from .discovery import router as discovery_router

# Create main API router
api_router = APIRouter(prefix="/api")

# Include all sub-routers
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(gateways_router, prefix="/gateways", tags=["Gateways"])
api_router.include_router(devices_router, prefix="/devices", tags=["Devices"])
api_router.include_router(channels_router, prefix="/channels", tags=["Channels"])
api_router.include_router(readings_router, prefix="/readings", tags=["Readings"])
api_router.include_router(relays_router, prefix="/relays", tags=["Relays"])
api_router.include_router(schedules_router, prefix="/schedules", tags=["Schedules"])
api_router.include_router(triggers_router, prefix="/triggers", tags=["Triggers"])
api_router.include_router(discovery_router, prefix="/discovery", tags=["Discovery"])

__all__ = ["api_router"]
