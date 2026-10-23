"""OAuth helpers that connect Home Assistant to pysmarthq."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2Implementation,
    OAuth2Session,
)
from pysmarthq.auth import AbstractAuth
from pysmarthq.errors import SmartHQAuthError

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from homeassistant.core import HomeAssistant


class SmartHQOAuth2Implementation(LocalOAuth2Implementation):
    """
    Authorization-code OAuth for SmartHQ, without PKCE.

    SmartHQ issues a refresh token only when the authorize request sends
    ``access_type=offline``. A refresh response that omits the refresh token,
    or sets it blank, leaves the previous refresh token as the valid one.
    """

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Authorize parameters appended to the SmartHQ login URL."""
        return {"access_type": "offline"}

    async def _async_refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Exchange a refresh token and keep the previous one when needed."""
        refreshed = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
            }
        )
        merged = {**token, **refreshed}
        refresh_token = merged.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token:
            merged["refresh_token"] = token["refresh_token"]
        return merged


class SmartHQTokenAuth(AbstractAuth):
    """Auth used once, while the config flow resolves the SmartHQ user id."""

    def __init__(self, websession: ClientSession, access_token: str) -> None:
        """Store the access token from the code exchange."""
        super().__init__(websession)
        self._access_token = access_token

    async def async_get_access_token(self) -> str:
        """Return the access token captured during setup."""
        return self._access_token


class SmartHQHomeAssistantAuth(AbstractAuth):
    """
    Digital Twin auth that stores tokens on the config entry.

    Home Assistant refreshes the token. This object does not construct
    ``SmartHQAuth``, which would rotate the refresh token beside that store.
    """

    def __init__(
        self, hass: HomeAssistant, websession: ClientSession, session: OAuth2Session
    ) -> None:
        """Store the Home Assistant OAuth session."""
        super().__init__(websession)
        self.hass = hass
        self.session = session

    async def async_get_access_token(self) -> str:
        """Return a current access token, refreshing it shortly before expiry."""
        await self.session.async_ensure_token_valid()
        access_token = self.session.token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            message = "Access token is missing"
            raise SmartHQAuthError(message)
        return access_token

    def token_expires_at(self) -> float | None:
        """Return the Unix expiry stored on the config entry token."""
        expires_at = self.session.token.get("expires_at")
        if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
            return None
        return float(expires_at)

    async def async_force_refresh(self) -> None:
        """
        Refresh after HTTP 401 even when the token still looks current.

        ``OAuth2Session.async_ensure_token_valid`` returns immediately while
        ``expires_at`` is in the future, so a rejected access token would be
        sent again.
        """
        async with self.session._token_lock:  # noqa: SLF001
            try:
                refreshed = await self.session.implementation.async_refresh_token(
                    self.session.token
                )
            except Exception as err:
                message = "Access token refresh failed"
                raise SmartHQAuthError(message) from err
            self.hass.config_entries.async_update_entry(
                self.session.config_entry,
                data={**self.session.config_entry.data, "token": refreshed},
            )
