"""DataUpdateCoordinator for smarthq."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SmartHqApiClientAuthenticationError,
    SmartHqApiClientError,
    SmartHqApiClientRateLimitError,
)

if TYPE_CHECKING:
    from .data import SmartHqConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class SmartHqDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: SmartHqConfigEntry

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        try:
            return await self.config_entry.runtime_data.client.async_get_data()
        except SmartHqApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except SmartHqApiClientRateLimitError as exception:
            raise UpdateFailed(
                exception,
                retry_after=exception.retry_after,
            ) from exception
        except SmartHqApiClientError as exception:
            raise UpdateFailed(exception) from exception
