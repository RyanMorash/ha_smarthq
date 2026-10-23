"""Switch platform for SmartHQ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity

from .const import (
    COMMAND_DISHWASHER_SET,
    COMMAND_LAUNDRY_TOGGLE_SET,
    COMMAND_MODE_SET,
    COMMAND_TOGGLE_SET,
    DISHWASHER_BOOL_FIELDS,
    SERVICE_DISHWASHER_MODE,
    SERVICE_LAUNDRY_TOGGLE,
    SERVICE_TOGGLE,
)
from .entity import SmartHQServiceEntity
from .service_map import mode_kind
from .util import (
    as_mapping,
    binary_mode_pair,
    device_services,
    has_command,
    service_name,
    supported_modes,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from pysmarthq.models import Device, Service

    from .coordinator import SmartHQDataUpdateCoordinator
    from .data import SmartHQConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ switches."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SwitchEntity] = []
    for device_id, device in coordinator.data.items():
        entities.extend(_switches_for_device(coordinator, device_id, device))
    async_add_entities(entities)


def _switches_for_device(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    device: Device,
) -> list[SwitchEntity]:
    """Return switches for one appliance."""
    entities: list[SwitchEntity] = []
    for service in device_services(device):
        service_type = service.serviceType
        if service_type == SERVICE_TOGGLE and has_command(service, COMMAND_TOGGLE_SET):
            entities.append(
                SmartHQToggleSwitch(coordinator, device_id, service, COMMAND_TOGGLE_SET)
            )
        elif service_type == SERVICE_LAUNDRY_TOGGLE and has_command(
            service, COMMAND_LAUNDRY_TOGGLE_SET
        ):
            entities.append(
                SmartHQToggleSwitch(
                    coordinator, device_id, service, COMMAND_LAUNDRY_TOGGLE_SET
                )
            )
        elif mode_kind(service) == "switch":
            pair = binary_mode_pair(supported_modes(service))
            if pair is not None:
                entities.append(
                    SmartHQModeSwitch(coordinator, device_id, service, pair[0], pair[1])
                )
        elif service_type == SERVICE_DISHWASHER_MODE and has_command(
            service, COMMAND_DISHWASHER_SET
        ):
            state = as_mapping(service.state)
            entities.extend(
                SmartHQFieldSwitch(coordinator, device_id, service, field)
                for field in DISHWASHER_BOOL_FIELDS
                if isinstance(state.get(field), bool)
            )
    return entities


class SmartHQToggleSwitch(SmartHQServiceEntity, SwitchEntity):
    """A toggle or laundry toggle service."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        command: str,
    ) -> None:
        """Store the set command used by this toggle."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "toggle",
            service_name(service),
        )
        self._command = command

    @property
    def is_on(self) -> bool | None:
        """Return whether the toggle is on."""
        service = self.service
        if service is None:
            return None
        value = as_mapping(service.state).get("on")
        if isinstance(value, bool):
            return value
        return None

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Turn the toggle on."""
        await self._async_set(on=True)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Turn the toggle off."""
        await self._async_set(on=False)

    async def _async_set(self, *, on: bool) -> None:
        """Send the toggle command."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(service, self._command, on=on)


class SmartHQModeSwitch(SmartHQServiceEntity, SwitchEntity):
    """A mode service whose two modes are on and off."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        on_mode: str,
        off_mode: str,
    ) -> None:
        """Store the raw mode tokens."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "mode",
            service_name(service),
        )
        self._on_mode = on_mode
        self._off_mode = off_mode

    @property
    def is_on(self) -> bool | None:
        """Return whether the current mode is the on token."""
        service = self.service
        if service is None:
            return None
        mode = as_mapping(service.state).get("mode")
        if mode == self._on_mode:
            return True
        if mode == self._off_mode:
            return False
        return None

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Select the on mode."""
        await self._async_set(self._on_mode)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Select the off mode."""
        await self._async_set(self._off_mode)

    async def _async_set(self, mode: str) -> None:
        """Send the mode command."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(service, COMMAND_MODE_SET, mode=mode)


class SmartHQFieldSwitch(SmartHQServiceEntity, SwitchEntity):
    """A boolean field on the dishwasher mode command."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        field: str,
    ) -> None:
        """Store the command field."""
        label = " ".join(part.capitalize() for part in _split_identifier(field))
        super().__init__(coordinator, device_id, service.serviceId or "", field, label)
        self._field = field

    @property
    def is_on(self) -> bool | None:
        """Return the boolean field."""
        service = self.service
        if service is None:
            return None
        value = as_mapping(service.state).get(self._field)
        if isinstance(value, bool):
            return value
        return None

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Enable the option."""
        await self._async_set(value=True)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Disable the option."""
        await self._async_set(value=False)

    async def _async_set(self, *, value: bool) -> None:
        """Send the dishwasher mode command with this field."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_DISHWASHER_SET, **{self._field: value}
        )


def _split_identifier(value: str) -> list[str]:
    """Split a camel-case identifier into words."""
    words: list[str] = []
    current = ""
    for character in value:
        if character.isupper() and current:
            words.append(current)
            current = character
        else:
            current += character
    if current:
        words.append(current)
    return words
