from fastapi import Depends, FastAPI

from .auth import require_owner
from .config import get_settings
from .repository import SupabaseRepository

app = FastAPI(title="SignalWatch API", version="0.1.0", docs_url=None, redoc_url=None)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/admin/system-health")
async def system_health(_: dict = Depends(require_owner)) -> dict:
    repository = SupabaseRepository(get_settings())
    try:
        return await repository.health_snapshot()
    finally:
        await repository.close()
