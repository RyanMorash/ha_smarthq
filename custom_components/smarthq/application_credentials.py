"""Application credentials for SmartHQ OAuth."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)

from .auth import SmartHQOAuth2Implementation
from .const import AUTHORIZE_URL, TOKEN_URL

_MORE_INFO_URL = "https://github.com/RyanMorash/ha_smarthq"
_OAUTH_CALLBACK_URL = "https://my.home-assistant.io/redirect/oauth"

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import config_entry_oauth2_flow


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:  # noqa: ARG001
    """Return the SmartHQ authorization server."""
    return AuthorizationServer(authorize_url=AUTHORIZE_URL, token_url=TOKEN_URL)


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return the SmartHQ OAuth implementation for one application credential."""
    return SmartHQOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        credential.client_secret,
        AUTHORIZE_URL,
        TOKEN_URL,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:  # noqa: ARG001
    """Return placeholders for the application credentials dialog."""
    return {
        "more_info_url": _MORE_INFO_URL,
        "oauth_callback_url": _OAUTH_CALLBACK_URL,
    }
