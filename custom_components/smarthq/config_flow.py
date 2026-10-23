"""Config flow for SmartHQ."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pysmarthq import SmartHQApi
from pysmarthq.errors import SmartHQAuthError, SmartHQError

from .auth import SmartHQTokenAuth
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from logging import Logger

_TITLE = "SmartHQ"


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a SmartHQ OAuth config flow."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> Logger:
        """Return the logger used by the OAuth helper."""
        return LOGGER

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:  # noqa: ARG002
        """Start reauthentication when the stored token is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm before opening SmartHQ login again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the account entry after SmartHQ returns a token."""
        user_id, reason = await self._async_account_id(data)
        if reason is not None or user_id is None:
            return self.async_abort(reason=reason or "unknown")
        await self.async_set_unique_id(user_id)
        if self.source == SOURCE_REAUTH:
            return self._async_reauth_result(user_id, data)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=_TITLE, data=data)

    async def _async_account_id(
        self, data: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Return the user id, or an abort reason when the account cannot be read."""
        token = data.get("token")
        access_token = token.get("access_token") if isinstance(token, dict) else None
        if not isinstance(access_token, str) or not access_token:
            return None, "oauth_error"
        try:
            user_id = await self._async_user_id(access_token)
        except SmartHQAuthError:
            LOGGER.debug(
                "SmartHQ rejected the new access token while reading the user id"
            )
            return None, "oauth_unauthorized"
        except SmartHQError:
            LOGGER.debug("SmartHQ device list failed during account linking")
            return None, "cannot_connect"
        if user_id is None:
            return None, "unknown"
        return user_id, None

    def _async_reauth_result(
        self, user_id: str, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Update the entry that is being reauthenticated."""
        reauth_entry = self._get_reauth_entry()
        if reauth_entry.unique_id != user_id:
            return self.async_abort(reason="wrong_account")
        return self.async_update_reload_and_abort(reauth_entry, data_updates=data)

    async def _async_user_id(self, access_token: str) -> str | None:
        """Return the SmartHQ user id for the authorized account."""
        auth = SmartHQTokenAuth(async_get_clientsession(self.hass), access_token)
        listed = await SmartHQApi(auth).async_get_devices()
        user_id = listed.userId
        if isinstance(user_id, str) and user_id:
            return user_id
        return None
