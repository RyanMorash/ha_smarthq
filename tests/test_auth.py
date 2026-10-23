"""OAuth token tests for SmartHQ."""

import asyncio
from unittest.mock import AsyncMock, Mock

from homeassistant.core import HomeAssistant
from pysmarthq.errors import SmartHQAuthError

from custom_components.smarthq.auth import (
    SmartHQHomeAssistantAuth,
    SmartHQOAuth2Implementation,
)
from custom_components.smarthq.const import AUTHORIZE_URL, DOMAIN, TOKEN_URL


async def test_refresh_keeps_previous_refresh_token(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """A blank or omitted refresh token does not replace the stored one."""
    implementation = SmartHQOAuth2Implementation(
        hass,
        DOMAIN,
        "client-id",
        "client-secret",
        AUTHORIZE_URL,
        TOKEN_URL,
    )
    original = {"access_token": "old", "expires_in": 1, "refresh_token": "keep-me"}
    aioclient_mock.post(
        TOKEN_URL, json={"access_token": "new", "expires_in": 30, "refresh_token": ""}
    )
    refreshed = await implementation.async_refresh_token(original)
    assert refreshed["access_token"] == "new"
    assert refreshed["refresh_token"] == "keep-me"

    aioclient_mock.clear_requests()
    aioclient_mock.post(TOKEN_URL, json={"access_token": "newer", "expires_in": 30})
    refreshed = await implementation.async_refresh_token(original)
    assert refreshed["access_token"] == "newer"
    assert refreshed["refresh_token"] == "keep-me"


async def test_authorize_url_requests_offline_access(
    hass: HomeAssistant, current_request_with_host
) -> None:
    """The authorize URL asks for a refresh token and does not use PKCE."""
    implementation = SmartHQOAuth2Implementation(
        hass,
        DOMAIN,
        "client-id",
        "client-secret",
        AUTHORIZE_URL,
        TOKEN_URL,
    )
    url = await implementation.async_generate_authorize_url("flow-id")
    assert "access_type=offline" in url
    assert "code_challenge" not in url


async def test_force_refresh_writes_the_config_entry(hass: HomeAssistant) -> None:
    """HTTP 401 refreshes even when the stored expiry is still in the future."""
    session = Mock()
    session.token = {
        "access_token": "stale",
        "expires_at": 10**10,
        "refresh_token": "refresh",
    }
    session._token_lock = asyncio.Lock()
    session.implementation.async_refresh_token = AsyncMock(
        return_value={
            "access_token": "fresh",
            "expires_at": 10**10,
            "refresh_token": "refresh",
        }
    )
    entry = Mock()
    entry.data = {"token": session.token}
    session.config_entry = entry
    hass.config_entries.async_update_entry = Mock()
    auth = SmartHQHomeAssistantAuth(hass, Mock(), session)

    await auth.async_force_refresh()

    hass.config_entries.async_update_entry.assert_called_once()
    updated = hass.config_entries.async_update_entry.call_args.kwargs["data"]["token"]
    assert updated["access_token"] == "fresh"


async def test_missing_access_token_raises(hass: HomeAssistant) -> None:
    """A session without an access token is an authentication error."""
    session = Mock()
    session.token = {}
    session.async_ensure_token_valid = AsyncMock()
    auth = SmartHQHomeAssistantAuth(hass, Mock(), session)
    try:
        await auth.async_get_access_token()
    except SmartHQAuthError:
        return
    message = "expected SmartHQAuthError"
    raise AssertionError(message)
