"""The SmartHQ integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pysmarthq import EventStream, SmartHQApi

from .auth import SmartHQHomeAssistantAuth
from .coordinator import SmartHQDataUpdateCoordinator
from .data import SmartHQConfigEntry, SmartHQData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


async def async_setup_entry(hass: HomeAssistant, entry: SmartHQConfigEntry) -> bool:
    """Set up a SmartHQ account from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    websession = async_get_clientsession(hass)
    auth = SmartHQHomeAssistantAuth(hass, websession, session)
    api = SmartHQApi(auth)
    stream = EventStream(auth)
    coordinator = SmartHQDataUpdateCoordinator(hass, entry, api, stream)
    entry.runtime_data = SmartHQData(
        api=api, auth=auth, coordinator=coordinator, stream=stream
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start_stream()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartHQConfigEntry) -> bool:
    """Unload a SmartHQ config entry."""
    await entry.runtime_data.coordinator.async_stop_stream()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
