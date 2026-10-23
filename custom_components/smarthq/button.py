"""Button platform for SmartHQ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity

from .const import (
    COMMAND_BREW_RESET,
    COMMAND_COFFEE_V1_START,
    COMMAND_COFFEE_V1_STOP,
    COMMAND_COFFEE_V2_START,
    COMMAND_COFFEE_V2_STOP,
    COMMAND_COOKING_MODE_START,
    COMMAND_COOKING_PAUSE,
    COMMAND_COOKING_RESTORE,
    COMMAND_COOKING_RESUME,
    COMMAND_COOKING_STOP,
    COMMAND_DISHWASHER_PAUSE,
    COMMAND_DISHWASHER_START,
    COMMAND_DISHWASHER_STOP,
    COMMAND_FIRMWARE_UPGRADE,
    COMMAND_STOPWATCH_PAUSE,
    COMMAND_STOPWATCH_RESET,
    COMMAND_STOPWATCH_START,
    COMMAND_TRIGGER,
    SERVICE_BREW_MODE,
    SERVICE_COFFEE_V1,
    SERVICE_COFFEE_V2,
    SERVICE_COOKING_MODE,
    SERVICE_COOKING_STATE,
    SERVICE_DISHWASHER_STATE,
    SERVICE_FIRMWARE,
    SERVICE_STOPWATCH,
    SERVICE_TRIGGER,
)
from .entity import SmartHQEntity, SmartHQServiceEntity
from .util import cooking_command_fields, device_services, has_command, service_name

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from pysmarthq.models import Device, Service

    from .coordinator import SmartHQDataUpdateCoordinator
    from .data import SmartHQConfigEntry

PARALLEL_UPDATES = 1

_SERVICE_BUTTONS = (
    (SERVICE_COOKING_STATE, COMMAND_COOKING_STOP, "Stop", "stop"),
    (SERVICE_COOKING_STATE, COMMAND_COOKING_PAUSE, "Pause", "pause"),
    (SERVICE_COOKING_STATE, COMMAND_COOKING_RESUME, "Resume", "resume"),
    (SERVICE_DISHWASHER_STATE, COMMAND_DISHWASHER_START, "Start", "start"),
    (SERVICE_DISHWASHER_STATE, COMMAND_DISHWASHER_STOP, "Stop", "stop"),
    (SERVICE_DISHWASHER_STATE, COMMAND_DISHWASHER_PAUSE, "Pause", "pause"),
    (SERVICE_STOPWATCH, COMMAND_STOPWATCH_START, "Start stopwatch", "start"),
    (SERVICE_STOPWATCH, COMMAND_STOPWATCH_PAUSE, "Pause stopwatch", "pause"),
    (SERVICE_STOPWATCH, COMMAND_STOPWATCH_RESET, "Reset stopwatch", "reset"),
    (SERVICE_COFFEE_V1, COMMAND_COFFEE_V1_START, "Start brew", "start"),
    (SERVICE_COFFEE_V1, COMMAND_COFFEE_V1_STOP, "Stop brew", "stop"),
    (SERVICE_COFFEE_V2, COMMAND_COFFEE_V2_START, "Start brew", "start"),
    (SERVICE_COFFEE_V2, COMMAND_COFFEE_V2_STOP, "Stop brew", "stop"),
    (SERVICE_BREW_MODE, COMMAND_BREW_RESET, "Reset brew", "reset"),
    (SERVICE_TRIGGER, COMMAND_TRIGGER, None, "trigger"),
    (SERVICE_FIRMWARE, COMMAND_FIRMWARE_UPGRADE, "Install firmware update", "upgrade"),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ buttons."""
    coordinator = entry.runtime_data.coordinator
    entities: list[ButtonEntity] = []
    for device_id, device in coordinator.data.items():
        entities.extend(_buttons_for_device(coordinator, device_id, device))
    async_add_entities(entities)


def _buttons_for_device(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    device: Device,
) -> list[ButtonEntity]:
    """Return buttons for one appliance."""
    entities: list[ButtonEntity] = []
    cooking: dict[str, list[Service]] = {}
    for service in device_services(device):
        for service_type, command, name, suffix in _SERVICE_BUTTONS:
            if service.serviceType != service_type or not has_command(service, command):
                continue
            label = name or service_name(service)
            entities.append(
                SmartHQCommandButton(
                    coordinator, device_id, service, command, label, suffix
                )
            )
        if service.serviceType == SERVICE_COOKING_MODE:
            cooking.setdefault(service.serviceDeviceType or device_id, []).append(
                service
            )
    for service_device_type, services in cooking.items():
        if any(
            has_command(service, COMMAND_COOKING_MODE_START) for service in services
        ):
            entities.append(
                SmartHQCookStartButton(coordinator, device_id, service_device_type)
            )
        if any(has_command(service, COMMAND_COOKING_RESTORE) for service in services):
            entities.append(
                SmartHQCookRestoreButton(coordinator, device_id, service_device_type)
            )
    return entities


class SmartHQCommandButton(SmartHQServiceEntity, ButtonEntity):
    """A button that sends one command."""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        command: str,
        name: str,
        suffix: str,
    ) -> None:
        """Store the command type."""
        super().__init__(coordinator, device_id, service.serviceId or "", suffix, name)
        self._command = command

    async def async_press(self) -> None:
        """Send the command."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(service, self._command)


class SmartHQCookStartButton(SmartHQEntity, ButtonEntity):
    """Start the active cooking mode."""

    _attr_name = "Start"

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service_device_type: str,
    ) -> None:
        """Store the cavity this button starts."""
        super().__init__(coordinator, device_id, f"{service_device_type}_start")
        self._service_device_type = service_device_type

    async def async_press(self) -> None:
        """Start cooking with the parameters currently on the mode."""
        service = _active_cooking_mode(self.device, self._service_device_type)
        if service is None or not has_command(service, COMMAND_COOKING_MODE_START):
            return
        fields = cooking_command_fields(
            service, self.hass.config.units.temperature_unit
        )
        await self.coordinator.async_send_command(
            service, COMMAND_COOKING_MODE_START, **fields
        )


class SmartHQCookRestoreButton(SmartHQEntity, ButtonEntity):
    """Restore the default parameters of the active cooking mode."""

    _attr_name = "Restore defaults"

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service_device_type: str,
    ) -> None:
        """Store the cavity this button restores."""
        super().__init__(coordinator, device_id, f"{service_device_type}_restore")
        self._service_device_type = service_device_type

    async def async_press(self) -> None:
        """Restore the cooking mode defaults."""
        service = _active_cooking_mode(self.device, self._service_device_type)
        if service is None or not has_command(service, COMMAND_COOKING_RESTORE):
            modes = [
                item
                for item in device_services(self.device)
                if item.serviceType == SERVICE_COOKING_MODE
                and item.serviceDeviceType == self._service_device_type
                and has_command(item, COMMAND_COOKING_RESTORE)
            ]
            service = modes[0] if modes else None
        if service is None:
            return
        await self.coordinator.async_send_command(service, COMMAND_COOKING_RESTORE)


def _active_cooking_mode(
    device: Device | None, service_device_type: str
) -> Service | None:
    """Return the cooking mode service that matches the current cooking state."""
    modes = [
        service
        for service in device_services(device)
        if service.serviceType == SERVICE_COOKING_MODE
        and service.serviceDeviceType == service_device_type
    ]
    current = None
    for service in device_services(device):
        if service.serviceType != SERVICE_COOKING_STATE:
            continue
        if service.serviceDeviceType not in {None, service_device_type}:
            continue
        mode = service.state.get("mode") if isinstance(service.state, dict) else None
        if isinstance(mode, str):
            current = mode
            break
    for service in modes:
        if service.domainType == current and has_command(
            service, COMMAND_COOKING_MODE_START
        ):
            return service
    for service in modes:
        if has_command(service, COMMAND_COOKING_MODE_START):
            return service
    return None
