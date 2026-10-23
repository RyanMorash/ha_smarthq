"""Diagnostics support for SmartHQ."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import TO_REDACT

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SmartHQConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a SmartHQ config entry."""
    devices = [
        deepcopy(device.raw_data)
        for device in entry.runtime_data.coordinator.data.values()
    ]
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "devices": devices,
        },
        TO_REDACT,
    )
