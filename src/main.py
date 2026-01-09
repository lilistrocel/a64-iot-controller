"""
A64 IoT Controller - Main Application Entry Point

FastAPI application for managing IoT devices on Raspberry Pi.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .core.database import Database
from .api import api_router
from .devices import DeviceManager
from .scheduler import Scheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

# Add file handler if log directory exists
if settings.log_file:
    try:
        from pathlib import Path
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(settings.log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)
    except Exception as e:
        logging.warning(f"Could not set up file logging: {e}")

logger = logging.getLogger(__name__)

# Global instances
db: Database | None = None
device_manager: DeviceManager | None = None
scheduler: Scheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    global db, device_manager, scheduler

    logger.info("=" * 60)
    logger.info("A64 IoT Controller Starting...")
    logger.info("=" * 60)

    # Initialize database
    logger.info(f"Initializing database: {settings.database_path}")
    db = Database(settings.database_path)
    await db.connect()

    # Run startup recovery if enabled
    if settings.recover_relay_states:
        logger.info("Running startup recovery...")
        try:
            from .startup.recovery import run_startup_recovery
            await run_startup_recovery(db)
        except ImportError:
            logger.warning("Startup recovery module not found - skipping")
        except Exception as e:
            logger.error(f"Startup recovery failed: {e}")

    # Start device manager
    logger.info("Starting device manager...")
    device_manager = DeviceManager(db)
    await device_manager.start()

    # Start scheduler
    logger.info("Starting scheduler...")
    scheduler = Scheduler(db, device_manager)
    await scheduler.start()

    # Store in app state for dependency injection
    app.state.db = db
    app.state.device_manager = device_manager
    app.state.scheduler = scheduler

    logger.info(f"API server ready on {settings.api_host}:{settings.api_port}")
    logger.info("=" * 60)

    # Notify systemd we're ready (if running under systemd)
    try:
        import sdnotify
        n = sdnotify.SystemdNotifier()
        n.notify("READY=1")
        logger.info("Notified systemd: READY")
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Could not notify systemd: {e}")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop scheduler first (before device manager)
    if scheduler:
        await scheduler.stop()
        logger.info("Scheduler stopped")

    # Stop device manager
    if device_manager:
        await device_manager.stop()
        logger.info("Device manager stopped")

    # Close database
    if db:
        await db.close()
        logger.info("Database closed")

    logger.info("Goodbye!")


# Create FastAPI application
app = FastAPI(
    title="A64 IoT Controller",
    description="IoT device management and automation for Raspberry Pi",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.dashboard_enabled else None,
    redoc_url="/api/redoc" if settings.dashboard_enabled else None,
    openapi_url="/api/openapi.json" if settings.dashboard_enabled else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local network access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routes
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint - basic info"""
    return {
        "name": "A64 IoT Controller",
        "version": "1.0.0",
        "status": "running",
        "api_docs": "/api/docs",
        "dashboard": "/dashboard" if settings.dashboard_enabled else None
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )


def run():
    """Run the application with uvicorn"""
    import uvicorn

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
