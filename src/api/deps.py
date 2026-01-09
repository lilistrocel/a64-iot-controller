"""
API Dependencies

Common dependencies for API endpoints including authentication and database access.
"""

from typing import Annotated
from fastapi import Depends, HTTPException, Header, status

from ..config import settings
from ..core.database import Database, get_db


async def get_database() -> Database:
    """Dependency to get database instance"""
    return await get_db()


DatabaseDep = Annotated[Database, Depends(get_database)]


async def verify_api_key(x_api_key: str = Header(None)) -> str:
    """Verify API key for protected endpoints"""
    if not settings.api_key:
        # No API key configured, allow all requests
        return ""

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header."
        )

    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )

    return x_api_key


APIKeyDep = Annotated[str, Depends(verify_api_key)]


async def optional_api_key(x_api_key: str = Header(None)) -> str:
    """Optional API key verification"""
    return x_api_key or ""


OptionalAPIKeyDep = Annotated[str, Depends(optional_api_key)]
