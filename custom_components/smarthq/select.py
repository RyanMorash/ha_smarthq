"""Select platform for SmartHQ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .const import (
    COMMAND_BREW_SET,
    COMMAND_DISHWASHER_SET,
    COMMAND_LAUNDRY_SET,
    COMMAND_MODE_SET,
    DISHWASHER_STRING_FIELDS,
    LAUNDRY_STRING_FIELDS,
    SERVICE_BREW_MODE,
    SERVICE_COOKING_MODE,
    SERVICE_COOKING_STATE,
    SERVICE_DISHWASHER_MODE,
    SERVICE_LAUNDRY_MODE,
)
from .entity import SmartHQEntity, SmartHQServiceEntity
from .service_map import mode_kind
from .util import (
    as_mapping,
    choice_options,
    cooking_command_fields,
    cooking_update_command,
    device_services,
    has_command,
    humanize,
    option_map,
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
_FIELD_COMMANDS = {
    SERVICE_BREW_MODE: COMMAND_BREW_SET,
    SERVICE_DISHWASHER_MODE: COMMAND_DISHWASHER_SET,
    SERVICE_LAUNDRY_MODE: COMMAND_LAUNDRY_SET,
}
_FIELD_NAMES = {
    SERVICE_DISHWASHER_MODE: DISHWASHER_STRING_FIELDS,
    SERVICE_LAUNDRY_MODE: LAUNDRY_STRING_FIELDS,
}


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ selects."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SelectEntity] = []
    for device_id, device in coordinator.data.items():
        entities.extend(_selects_for_device(coordinator, device_id, device))
    async_add_entities(entities)


def _selects_for_device(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    device: Device,
) -> list[SelectEntity]:
    """Return selects for one appliance."""
    entities: list[SelectEntity] = []
    cooking: dict[str, list[Service]] = {}
    for service in device_services(device):
        service_type = service.serviceType
        if mode_kind(service) == "select":
            entities.append(SmartHQModeSelect(coordinator, device_id, service))
        elif service_type == SERVICE_COOKING_MODE:
            cooking.setdefault(service.serviceDeviceType or device_id, []).append(
                service
            )
        elif service_type in _FIELD_NAMES and has_command(
            service, _FIELD_COMMANDS[service_type]
        ):
            entities.extend(_field_selects(coordinator, device_id, service))
        elif service_type == SERVICE_BREW_MODE and has_command(
            service, COMMAND_BREW_SET
        ):
            entities.extend(_brew_selects(coordinator, device_id, service))
    entities.extend(
        SmartHQCookModeSelect(coordinator, device_id, service_device_type, services)
        for service_device_type, services in cooking.items()
        if services
    )
    return entities


def _field_selects(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    service: Service,
) -> list[SelectEntity]:
    """Return selects for string fields that publish an option list."""
    config = as_mapping(service.config)
    command = _FIELD_COMMANDS[service.serviceType or ""]
    entities: list[SelectEntity] = []
    for field in _FIELD_NAMES.get(service.serviceType or "", ()):
        options = choice_options(config, field)
        if not options:
            continue
        label = " ".join(part.capitalize() for part in _split_identifier(field))
        entities.append(
            SmartHQFieldSelect(
                coordinator, device_id, service, field, command, options, label
            )
        )
    return entities


def _brew_selects(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    service: Service,
) -> list[SelectEntity]:
    """Return a brew select when the config lists choices."""
    config = as_mapping(service.config)
    for field in ("myBrewMode", "mode"):
        options = choice_options(config, field)
        if options:
            return [
                SmartHQFieldSelect(
                    coordinator,
                    device_id,
                    service,
                    field,
                    COMMAND_BREW_SET,
                    options,
                    service_name(service),
                )
            ]
    return []


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


class SmartHQModeSelect(SmartHQServiceEntity, SelectEntity):
    """A writable mode service."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the mode select."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "mode",
            service_name(service),
        )

    @property
    def options(self) -> list[str]:
        """Return the mode labels."""
        service = self.service
        if service is None:
            return []
        return list(option_map(supported_modes(service)))

    @property
    def current_option(self) -> str | None:
        """Return the current mode label."""
        service = self.service
        if service is None:
            return None
        return _label_for(
            option_map(supported_modes(service)), as_mapping(service.state).get("mode")
        )

    async def async_select_option(self, option: str) -> None:
        """Set the mode."""
        service = self.service
        if service is None:
            return
        raw = option_map(supported_modes(service)).get(option)
        if raw is None:
            return
        await self.coordinator.async_send_command(service, COMMAND_MODE_SET, mode=raw)


class SmartHQFieldSelect(SmartHQServiceEntity, SelectEntity):
    """A string command field with a fixed option list."""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        field: str,
        command: str,
        options: list[str],
        name: str,
    ) -> None:
        """Store the field and its options."""
        super().__init__(coordinator, device_id, service.serviceId or "", field, name)
        self._field = field
        self._command = command
        self._raw_options = options

    @property
    def options(self) -> list[str]:
        """Return the option labels."""
        return list(option_map(self._raw_options))

    @property
    def current_option(self) -> str | None:
        """Return the current field label."""
        service = self.service
        if service is None:
            return None
        return _label_for(
            option_map(self._raw_options), as_mapping(service.state).get(self._field)
        )

    async def async_select_option(self, option: str) -> None:
        """Set the field."""
        service = self.service
        if service is None:
            return
        raw = option_map(self._raw_options).get(option)
        if raw is None:
            return
        await self.coordinator.async_send_command(
            service, self._command, **{self._field: raw}
        )


class SmartHQCookModeSelect(SmartHQEntity, SelectEntity):
    """One select for every cooking mode service on a cavity."""

    _attr_name = "Cook mode"

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service_device_type: str,
        services: list[Service],
    ) -> None:
        """Store the cavity these modes belong to."""
        super().__init__(coordinator, device_id, f"{service_device_type}_cook_mode")
        self._service_device_type = service_device_type
        self._domains = [
            service.domainType
            for service in services
            if isinstance(service.domainType, str)
        ]

    @property
    def _modes(self) -> list[Service]:
        """Return the live cooking mode services for this cavity."""
        return [
            service
            for service in device_services(self.device)
            if service.serviceType == SERVICE_COOKING_MODE
            and service.serviceDeviceType == self._service_device_type
        ]

    @property
    def options(self) -> list[str]:
        """Return the cooking mode labels."""
        return list(option_map([domain for domain in self._domains if domain]))

    @property
    def current_option(self) -> str | None:
        """Return the mode reported by the cooking state service."""
        return _label_for(
            option_map(self._domains),
            _cooking_state_mode(self.device, self._service_device_type),
        )

    async def async_select_option(self, option: str) -> None:
        """Apply the selected cooking mode."""
        raw = option_map(self._domains).get(option)
        service = next((item for item in self._modes if item.domainType == raw), None)
        if service is None:
            return
        command = cooking_update_command(service)
        if command is None:
            return
        fields = cooking_command_fields(
            service, self.hass.config.units.temperature_unit
        )
        await self.coordinator.async_send_command(service, command, **fields)


def _cooking_state_mode(device: Device | None, service_device_type: str) -> str | None:
    """Return the active cooking mode domain for a cavity."""
    for service in device_services(device):
        if service.serviceType != SERVICE_COOKING_STATE:
            continue
        if service.serviceDeviceType not in {None, service_device_type}:
            continue
        mode = as_mapping(service.state).get("mode")
        if isinstance(mode, str):
            return mode
    return None


def _label_for(mapping: dict[str, str], raw: object) -> str | None:
    """Return the label whose raw value matches."""
    if not isinstance(raw, str):
        return None
    for label, value in mapping.items():
        if value == raw:
            return label
    return humanize(raw) if raw in mapping.values() else None
