import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from signalwatch.auth import require_owner


class AuthSettings:
    supabase_url = "https://example.supabase.co"
    supabase_anon_key = SecretStr("anon-key")


@pytest.mark.asyncio
async def test_owner_auth_relies_on_private_settings_rls(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/private_settings"
        assert request.headers["authorization"] == "Bearer owner-jwt"
        return httpx.Response(200, json=[{"id": True}])

    original_client = httpx.AsyncClient
    monkeypatch.setattr("signalwatch.auth.get_settings", lambda: AuthSettings())
    monkeypatch.setattr(
        "signalwatch.auth.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler)),
    )
    assert await require_owner("Bearer owner-jwt") == {"id": True}


@pytest.mark.asyncio
async def test_non_owner_is_rejected_by_empty_rls_result(monkeypatch) -> None:
    original_client = httpx.AsyncClient
    monkeypatch.setattr("signalwatch.auth.get_settings", lambda: AuthSettings())
    monkeypatch.setattr(
        "signalwatch.auth.httpx.AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
        ),
    )
    with pytest.raises(HTTPException) as exc:
        await require_owner("Bearer non-owner-jwt")
    assert exc.value.status_code == 403
