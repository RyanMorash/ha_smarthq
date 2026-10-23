"""Base entities for SmartHQ appliances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER, PRESENCE_OFFLINE
from .coordinator import SmartHQDataUpdateCoordinator
from .util import as_mapping, find_service, humanize

if TYPE_CHECKING:
    from pysmarthq.models import Device, Service


class SmartHQEntity(CoordinatorEntity[SmartHQDataUpdateCoordinator]):
    """An entity attached to one SmartHQ appliance."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        unique_suffix: str,
    ) -> None:
        """Store the device id and unique id suffix."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{unique_suffix}"

    @property
    def device(self) -> Device | None:
        """Return the current device, if it is still on the account."""
        return self.coordinator.data.get(self._device_id)

    @property
    def available(self) -> bool:
        """Return whether the appliance is online and the last update succeeded."""
        device = self.device
        return (
            super().available
            and device is not None
            and device.presence != PRESENCE_OFFLINE
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the appliance device registry entry."""
        device = self.device
        name = DEFAULT_NAME
        manufacturer = MANUFACTURER
        model = None
        serial_number = None
        sw_version = None
        via_device = None
        if device is not None:
            if isinstance(device.nickname, str) and device.nickname:
                name = device.nickname
            elif isinstance(device.deviceType, str):
                name = humanize(device.deviceType)
            if isinstance(device.brand, str) and device.brand:
                manufacturer = device.brand
            elif isinstance(device.manufacturer, str) and device.manufacturer:
                manufacturer = device.manufacturer
            model = device.model
            serial_number = device.serial
            sw_version = device.version
            gateway_id = device.gatewayId
            if isinstance(gateway_id, str) and gateway_id in self.coordinator.data:
                via_device = (DOMAIN, gateway_id)
        info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=manufacturer,
            model=model,
            name=name,
            serial_number=serial_number,
            sw_version=sw_version,
        )
        if via_device is not None:
            info["via_device"] = via_device
        return info


class SmartHQServiceEntity(SmartHQEntity):
    """An entity backed by one Digital Twin service."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service_id: str,
        suffix: str,
        name: str,
    ) -> None:
        """Store the service id used to read live state."""
        super().__init__(coordinator, device_id, f"{service_id}_{suffix}")
        self._service_id = service_id
        self._attr_name = name

    @property
    def service(self) -> Service | None:
        """Return the live service."""
        return find_service(self.device, self._service_id)

    @property
    def available(self) -> bool:
        """Return whether the service is present and not disabled."""
        service = self.service
        if not super().available or service is None:
            return False
        return as_mapping(service.state).get("disabled") is not True
