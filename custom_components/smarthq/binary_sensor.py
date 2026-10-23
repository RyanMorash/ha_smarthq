"""Binary sensor platform for SmartHQ."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .const import (
    COMMAND_TOGGLE_SET,
    DOOR_FIELDS,
    PRESENCE_ONLINE,
    SERVICE_COOKING_STATE,
    SERVICE_DOOR,
    SERVICE_FILTER,
    SERVICE_TOGGLE,
)
from .entity import SmartHQEntity, SmartHQServiceEntity
from .util import as_mapping, device_services, has_command, service_name

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from pysmarthq.models import Device, Service

    from .coordinator import SmartHQDataUpdateCoordinator
    from .data import SmartHQConfigEntry

PARALLEL_UPDATES = 0
_DOOR_SPLIT = re.compile(r"(?<!^)(?=[A-Z])")


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ binary sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[BinarySensorEntity] = []
    for device_id, device in coordinator.data.items():
        entities.append(SmartHQPresenceBinarySensor(coordinator, device_id))
        entities.extend(_binary_sensors(coordinator, device_id, device))
    async_add_entities(entities)


def _binary_sensors(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    device: Device,
) -> list[BinarySensorEntity]:
    """Return binary sensors for one appliance."""
    entities: list[BinarySensorEntity] = []
    for service in device_services(device):
        service_type = service.serviceType
        state = as_mapping(service.state)
        if service_type == SERVICE_DOOR:
            entities.extend(_door_sensors(coordinator, device_id, service, state))
        elif service_type == SERVICE_FILTER and "expired" in state:
            entities.append(SmartHQFilterBinarySensor(coordinator, device_id, service))
        elif service_type == SERVICE_COOKING_STATE:
            if "doorOpen" in state:
                entities.append(
                    SmartHQFlagBinarySensor(
                        coordinator, device_id, service, "doorOpen", "Door", "door"
                    )
                )
            if "remoteEnable" in state:
                entities.append(
                    SmartHQFlagBinarySensor(
                        coordinator,
                        device_id,
                        service,
                        "remoteEnable",
                        "Remote control",
                        "remote",
                    )
                )
        elif (
            service_type == SERVICE_TOGGLE
            and not has_command(service, COMMAND_TOGGLE_SET)
            and "on" in state
        ):
            entities.append(
                SmartHQFlagBinarySensor(
                    coordinator, device_id, service, "on", service_name(service), "on"
                )
            )
    return entities


def _door_sensors(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    service: Service,
    state: dict,
) -> list[BinarySensorEntity]:
    """Return one door sensor per open flag the appliance reports."""
    entities: list[BinarySensorEntity] = []
    for field in DOOR_FIELDS:
        if field not in state:
            continue
        entities.append(
            SmartHQFlagBinarySensor(
                coordinator,
                device_id,
                service,
                field,
                _door_name(field),
                field,
                device_class=BinarySensorDeviceClass.DOOR,
            )
        )
    return entities


def _door_name(field: str) -> str:
    """Return a door name from a state field such as ``topLeftOpen``."""
    if field == "singleOpen":
        return "Door"
    stem = field.removesuffix("Open")
    return f"{_DOOR_SPLIT.sub(' ', stem)} door"


class SmartHQPresenceBinarySensor(SmartHQEntity, BinarySensorEntity):
    """Cloud connection for one appliance."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Cloud connection"

    def __init__(
        self, coordinator: SmartHQDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the connectivity sensor."""
        super().__init__(coordinator, device_id, "presence")

    @property
    def available(self) -> bool:
        """Stay available while the account can be read."""
        return super(SmartHQEntity, self).available and self.device is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the appliance is online."""
        device = self.device
        if device is None:
            return None
        return device.presence == PRESENCE_ONLINE


class SmartHQFlagBinarySensor(SmartHQServiceEntity, BinarySensorEntity):
    """A boolean flag on a service state."""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        field: str,
        name: str,
        suffix: str,
        *,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Store the state field this sensor reads."""
        super().__init__(coordinator, device_id, service.serviceId or "", suffix, name)
        self._field = field
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        """Return the flag."""
        service = self.service
        if service is None:
            return None
        value = as_mapping(service.state).get(self._field)
        if isinstance(value, bool):
            return value
        return None


class SmartHQFilterBinarySensor(SmartHQFlagBinarySensor):
    """Whether a filter is expired."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the filter problem sensor."""
        super().__init__(
            coordinator,
            device_id,
            service,
            "expired",
            "Filter",
            "expired",
            device_class=BinarySensorDeviceClass.PROBLEM,
        )
