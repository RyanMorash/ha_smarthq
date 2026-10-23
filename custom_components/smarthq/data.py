"""Runtime types for the SmartHQ integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from pysmarthq import EventStream, SmartHQApi

    from .auth import SmartHQHomeAssistantAuth
    from .coordinator import SmartHQDataUpdateCoordinator


type SmartHQConfigEntry = ConfigEntry[SmartHQData]


@dataclass
class SmartHQData:
    """Objects shared by the platforms of one SmartHQ account."""

    api: SmartHQApi
    auth: SmartHQHomeAssistantAuth
    coordinator: SmartHQDataUpdateCoordinator
    stream: EventStream
