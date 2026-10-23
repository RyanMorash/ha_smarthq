"""Water heater platform for SmartHQ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import (
    COMMAND_WATER_HEATER_SET,
    SERVICE_TEMPERATURE,
    SERVICE_WATER_HEATER,
    WATER_HEATER_MODES,
)
from .entity import SmartHQServiceEntity
from .util import (
    as_mapping,
    device_services,
    first_number,
    has_command,
    humanize,
    option_map,
    read_temperature,
    service_name,
    temperature_bounds,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from pysmarthq.models import Service

    from .coordinator import SmartHQDataUpdateCoordinator
    from .data import SmartHQConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ water heaters."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        SmartHQWaterHeater(coordinator, device_id, service)
        for device_id, device in coordinator.data.items()
        for service in device_services(device)
        if service.serviceType == SERVICE_WATER_HEATER
        and has_command(service, COMMAND_WATER_HEATER_SET)
    )


class SmartHQWaterHeater(SmartHQServiceEntity, WaterHeaterEntity):
    """A waterheater.v1 service."""

    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the water heater."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "water_heater",
            service_name(service),
        )

    @property
    def temperature_unit(self) -> str:
        """Return the setpoint unit."""
        _value, unit = self._setpoint()
        return unit

    @property
    def current_operation(self) -> str | None:
        """Return the current mode label."""
        service = self.service
        if service is None:
            return None
        mode = as_mapping(service.state).get("mode")
        if not isinstance(mode, str) or mode.endswith(".unknown"):
            return None
        return _mode_labels().get(mode, humanize(mode))

    @property
    def operation_list(self) -> list[str]:
        """Return the water heater modes."""
        service = self.service
        config = as_mapping(service.config) if service is not None else {}
        configured = config.get("supportedModes")
        if isinstance(configured, list) and all(
            isinstance(item, str) for item in configured
        ):
            return list(
                option_map(
                    [item for item in configured if not item.endswith(".unknown")]
                )
            )
        return list(option_map(list(WATER_HEATER_MODES)))

    @property
    def target_temperature(self) -> float | None:
        """Return the setpoint."""
        value, _unit = self._setpoint()
        return value

    @property
    def current_temperature(self) -> float | None:
        """Return a sibling temperature that is not the setpoint."""
        for service in device_services(self.device):
            if service.serviceType != SERVICE_TEMPERATURE:
                continue
            if service.domainType and "setpoint" in service.domainType:
                continue
            value, _unit = read_temperature(
                as_mapping(service.state), self.hass.config.units.temperature_unit
            )
            if value is not None:
                return value
        return None

    @property
    def min_temp(self) -> float:
        """Return the lowest setpoint."""
        low, _high = self._bounds()
        if low is not None:
            return low
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return 30
        return 90

    @property
    def max_temp(self) -> float:
        """Return the highest setpoint."""
        _low, high = self._bounds()
        if high is not None:
            return high
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return 60
        return 140

    async def async_set_temperature(self, **kwargs: object) -> None:
        """Set the water heater setpoint."""
        service = self.service
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if service is None or not isinstance(temperature, (int, float)):
            return
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            await self.coordinator.async_send_command(
                service, COMMAND_WATER_HEATER_SET, setpointCelsius=temperature
            )
            return
        await self.coordinator.async_send_command(
            service, COMMAND_WATER_HEATER_SET, setpointFahrenheit=temperature
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set the water heater mode."""
        service = self.service
        if service is None:
            return
        raw = _raw_modes().get(operation_mode)
        if raw is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_WATER_HEATER_SET, mode=raw
        )

    def _setpoint(self) -> tuple[float | None, str]:
        """Return the configured setpoint."""
        service = self.service
        state = as_mapping(service.state) if service is not None else {}
        return read_temperature(
            state, self.hass.config.units.temperature_unit, prefix="setpoint"
        )

    def _bounds(self) -> tuple[float | None, float | None]:
        """Return setpoint limits."""
        service = self.service
        config = as_mapping(service.config) if service is not None else {}
        low, high = temperature_bounds(config, self.temperature_unit, prefix="setpoint")
        if low is None:
            low = first_number(config, ("minimum",))
        if high is None:
            high = first_number(config, ("maximum",))
        return low, high


def _mode_labels() -> dict[str, str]:
    """Map raw water heater modes to labels."""
    labels = option_map(list(WATER_HEATER_MODES))
    return {raw: label for label, raw in labels.items()}


def _raw_modes() -> dict[str, str]:
    """Map water heater labels back to raw modes."""
    return option_map(list(WATER_HEATER_MODES))
