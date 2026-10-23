"""Config flow tests for SmartHQ."""

from unittest.mock import patch

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component
from pysmarthq.errors import SmartHQAuthError, SmartHQError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

from custom_components.smarthq.const import DOMAIN, TOKEN_URL

from .common import USER_ID, FlowApi, token


async def _start_credentials(hass: HomeAssistant) -> None:
    """Register one SmartHQ application credential."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("client-id", "client-secret"),
    )


async def _finish_oauth(hass: HomeAssistant, flow_id: str, authorize_url: str) -> dict:
    """Exchange the authorization code and return the finished flow result."""
    query = URL(authorize_url).query
    assert query["access_type"] == "offline"
    assert "code_challenge" not in query
    state = config_entry_oauth2_flow._decode_jwt(hass, query["state"])
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"code": "abc", "state": state}
    )
    if result["type"] is FlowResultType.EXTERNAL_STEP_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    return result


async def test_config_flow_creates_entry(
    hass: HomeAssistant,
    aioclient_mock,
    current_request_with_host,
) -> None:
    """A completed login stores the user id and an offline refresh token."""
    await _start_credentials(hass)
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "access-1",
            "expires_in": 3600,
            "refresh_token": "refresh-1",
            "token_type": "Bearer",
        },
    )
    FlowApi.user_id = USER_ID
    FlowApi.error = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    with patch("custom_components.smarthq.config_flow.SmartHQApi", FlowApi):
        result = await _finish_oauth(hass, result["flow_id"], result["url"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_ID
    assert result["result"].data["token"]["refresh_token"] == "refresh-1"
    assert result["result"].data["token"]["access_token"] == "access-1"


async def test_duplicate_user_aborts(
    hass: HomeAssistant,
    aioclient_mock,
    current_request_with_host,
) -> None:
    """The same SmartHQ user cannot be added twice."""
    await _start_credentials(hass)
    MockConfigEntry(
        domain=DOMAIN, unique_id=USER_ID, data={"token": token()}
    ).add_to_hass(hass)
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "access-1",
            "expires_in": 60,
            "refresh_token": "refresh-1",
        },
    )
    FlowApi.user_id = USER_ID
    FlowApi.error = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch("custom_components.smarthq.config_flow.SmartHQApi", FlowApi):
        result = await _finish_oauth(hass, result["flow_id"], result["url"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_replaces_token(
    hass: HomeAssistant,
    aioclient_mock,
    current_request_with_host,
) -> None:
    """Reauthentication stores the new token on the existing entry."""
    await _start_credentials(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": token(access="old-access", refresh="old-refresh"),
        },
    )
    entry.add_to_hass(hass)
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access",
            "expires_in": 60,
            "refresh_token": "new-refresh",
        },
    )
    FlowApi.user_id = USER_ID
    FlowApi.error = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": USER_ID,
        },
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    with (
        patch("custom_components.smarthq.config_flow.SmartHQApi", FlowApi),
        patch("custom_components.smarthq.SmartHQApi", FlowApi),
        patch(
            "custom_components.smarthq.EventStream",
            lambda *_args, **_kwargs: _IdleStream(),
        ),
    ):
        result = await _finish_oauth(hass, result["flow_id"], result["url"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == "new-access"
    assert entry.data["token"]["refresh_token"] == "new-refresh"


async def test_cannot_connect_aborts(
    hass: HomeAssistant,
    aioclient_mock,
    current_request_with_host,
) -> None:
    """A device-list failure aborts the flow."""
    await _start_credentials(hass)
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "access-1",
            "expires_in": 60,
            "refresh_token": "refresh-1",
        },
    )
    FlowApi.error = SmartHQError("down")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch("custom_components.smarthq.config_flow.SmartHQApi", FlowApi):
        result = await _finish_oauth(hass, result["flow_id"], result["url"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_unauthorized_aborts(
    hass: HomeAssistant,
    aioclient_mock,
    current_request_with_host,
) -> None:
    """A rejected access token aborts the flow."""
    await _start_credentials(hass)
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "access-1",
            "expires_in": 60,
            "refresh_token": "refresh-1",
        },
    )
    FlowApi.error = SmartHQAuthError("rejected")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch("custom_components.smarthq.config_flow.SmartHQApi", FlowApi):
        result = await _finish_oauth(hass, result["flow_id"], result["url"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"


class _IdleStream:
    """Stream that never connects. Reauth reload must not open a socket."""

    async def async_close(self) -> None:
        """Accept the close that unload performs when setup fails."""
