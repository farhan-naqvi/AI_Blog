import httpx
from fastapi import Header, HTTPException, status

from .config import get_settings


async def require_owner(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    settings = get_settings()
    if not settings.supabase_anon_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="owner auth not configured")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{str(settings.supabase_url).rstrip('/')}/rest/v1/private_settings",
            params={"select": "id", "limit": "1"},
            headers={
                "apikey": settings.supabase_anon_key.get_secret_value(),
                "authorization": authorization,
            },
        )
    rows = response.json() if response.status_code == 200 else []
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner access required")
    return rows[0]
