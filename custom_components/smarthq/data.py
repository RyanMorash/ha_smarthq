"""Custom types for smarthq."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import SmartHqApiClient
    from .coordinator import SmartHqDataUpdateCoordinator


type SmartHqConfigEntry = ConfigEntry[SmartHqData]


@dataclass
class SmartHqData:
    """Data for the SmartHQ integration."""

    client: SmartHqApiClient
    coordinator: SmartHqDataUpdateCoordinator
    integration: Integration
