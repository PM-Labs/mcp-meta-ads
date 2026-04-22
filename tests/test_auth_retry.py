"""
Regression test for the auto-retry-on-token-invalidate behaviour in
make_api_request.

Before this change: on a 401/403 or Meta error code 190/102/200/10, the
function invalidated the cached token and returned an error — the caller
saw one failure before the self-heal kicked in on the next call.

After this change: the function refreshes the token and replays the
request once. Callers only see an error if the retry also fails.
"""
import hashlib
import hmac
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from meta_ads_mcp.core import api as api_module
from meta_ads_mcp.core.api import make_api_request


def _http_error(status: int, payload: dict) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://graph.facebook.com/v23.0/me")
    response = httpx.Response(status, json=payload, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


@pytest.mark.asyncio
async def test_auth_error_retries_once_with_refreshed_token(monkeypatch):
    """On error code 190, invalidate → refresh → retry once → return success."""
    calls = []

    async def fake_make(method, url, **kwargs):
        calls.append(("outbound", kwargs.get("params", {}).get("access_token")))
        if len(calls) == 1:
            raise _http_error(400, {"error": {"code": 190, "message": "token expired"}})
        request = httpx.Request(method, url)
        return httpx.Response(200, json={"data": [{"id": "1"}]}, request=request)

    async def client_get(url, **kw):
        return await fake_make("GET", url, **kw)

    client = AsyncMock()
    client.get = client_get
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    fresh_token_calls = []

    async def fake_fresh_token():
        fresh_token_calls.append(True)
        return "FRESH_TOKEN"

    with patch.object(api_module.httpx, "AsyncClient", return_value=client):
        with patch("meta_ads_mcp.core.auth.get_current_access_token", side_effect=fake_fresh_token):
            invalidate_mock = MagicMock()
            monkeypatch.setattr(api_module.auth_manager, "invalidate_token", invalidate_mock)
            result = await make_api_request("me", "STALE_TOKEN")

    assert result == {"data": [{"id": "1"}]}, result
    assert len(calls) == 2, f"expected 2 outbound calls (first + retry), got {len(calls)}"
    assert calls[0][1] == "STALE_TOKEN"
    assert calls[1][1] == "FRESH_TOKEN"
    assert len(fresh_token_calls) == 1
    invalidate_mock.assert_called_once()


@pytest.mark.asyncio
async def test_auth_error_does_not_retry_twice(monkeypatch):
    """If the retry also fails with auth, return the error — no infinite loop."""
    calls = []

    async def fake_make(method, url, **kwargs):
        calls.append(("outbound", kwargs.get("params", {}).get("access_token")))
        raise _http_error(401, {"error": {"message": "invalid token"}})

    async def client_get(url, **kw):
        return await fake_make("GET", url, **kw)

    client = AsyncMock()
    client.get = client_get
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    async def fake_fresh_token():
        return "FRESH_BUT_ALSO_BAD"

    with patch.object(api_module.httpx, "AsyncClient", return_value=client):
        with patch("meta_ads_mcp.core.auth.get_current_access_token", side_effect=fake_fresh_token):
            monkeypatch.setattr(api_module.auth_manager, "invalidate_token", MagicMock())
            result = await make_api_request("me", "STALE_TOKEN")

    assert "error" in result
    assert len(calls) == 2, f"expected exactly 2 calls (first + single retry), got {len(calls)}"


@pytest.mark.asyncio
async def test_rate_limit_does_not_retry(monkeypatch):
    """Code 4 (rate limit) must NOT invalidate or retry — token is still valid."""
    calls = []

    async def fake_make(method, url, **kwargs):
        calls.append(True)
        raise _http_error(
            400,
            {"error": {"code": 4, "message": "rate limited", "error_subcode": 1349195}},
        )

    async def client_get(url, **kw):
        return await fake_make("GET", url, **kw)

    client = AsyncMock()
    client.get = client_get
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    invalidate_mock = MagicMock()
    fresh_mock = AsyncMock(return_value="NOT_CALLED")

    with patch.object(api_module.httpx, "AsyncClient", return_value=client):
        with patch("meta_ads_mcp.core.auth.get_current_access_token", fresh_mock):
            monkeypatch.setattr(api_module.auth_manager, "invalidate_token", invalidate_mock)
            result = await make_api_request("me", "STILL_VALID_TOKEN")

    assert "error" in result
    assert len(calls) == 1, "rate-limited requests must not retry"
    invalidate_mock.assert_not_called()
    fresh_mock.assert_not_called()


@pytest.mark.asyncio
async def test_app_id_misconfiguration_does_not_retry(monkeypatch):
    """Code 200 with 'Provide valid app ID' is terminal config error — no retry."""
    calls = []

    async def fake_make(method, url, **kwargs):
        calls.append(True)
        raise _http_error(
            400,
            {"error": {"code": 200, "message": "Provide valid app ID"}},
        )

    async def client_get(url, **kw):
        return await fake_make("GET", url, **kw)

    client = AsyncMock()
    client.get = client_get
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    fresh_mock = AsyncMock(return_value="NOT_CALLED")

    with patch.object(api_module.httpx, "AsyncClient", return_value=client):
        with patch("meta_ads_mcp.core.auth.get_current_access_token", fresh_mock):
            monkeypatch.setattr(api_module.auth_manager, "invalidate_token", MagicMock())
            result = await make_api_request("me", "TOKEN")

    assert "error" in result
    assert "authentication configuration issue" in result["error"]["message"].lower()
    assert len(calls) == 1
    fresh_mock.assert_not_called()
