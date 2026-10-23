"""
Classify Digital Twin services into Home Assistant entities.

Device type strings are not used. A service is a sensor, switch, select, or
number based on its type, the commands it accepts, and the modes in its config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import (
    COMMAND_DOUBLE_SET,
    COMMAND_INTEGER_SET,
    COMMAND_MODE_SET,
    COMMAND_TEMPERATURE_SET,
    KNOWN_SERVICE_TYPES,
    SERVICE_DOUBLE,
    SERVICE_INTEGER,
    SERVICE_MODE,
    SERVICE_TEMPERATURE,
)
from .util import binary_mode_pair, has_command, supported_modes

if TYPE_CHECKING:
    from pysmarthq.models import Service


def is_known(service: Service) -> bool:
    """Return whether this integration creates entities for the service type."""
    return service.serviceType in KNOWN_SERVICE_TYPES


def temperature_kind(service: Service) -> str | None:
    """Return ``number`` or ``sensor`` for a temperature service."""
    if service.serviceType != SERVICE_TEMPERATURE:
        return None
    if has_command(service, COMMAND_TEMPERATURE_SET):
        return "number"
    return "sensor"


def integer_kind(service: Service) -> str | None:
    """Return ``number`` or ``sensor`` for an integer service."""
    if service.serviceType != SERVICE_INTEGER:
        return None
    if has_command(service, COMMAND_INTEGER_SET):
        return "number"
    return "sensor"


def double_kind(service: Service) -> str | None:
    """Return ``number`` or ``sensor`` for a double service."""
    if service.serviceType != SERVICE_DOUBLE:
        return None
    if has_command(service, COMMAND_DOUBLE_SET):
        return "number"
    return "sensor"


def mode_kind(service: Service) -> str | None:
    """Return ``switch``, ``select``, or ``sensor`` for a mode service."""
    if service.serviceType != SERVICE_MODE:
        return None
    if not has_command(service, COMMAND_MODE_SET):
        return "sensor"
    modes = supported_modes(service)
    if binary_mode_pair(modes) is not None:
        return "switch"
    if modes:
        return "select"
    return "sensor"
