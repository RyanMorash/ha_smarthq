"""Climate platform for SmartHQ thermostats."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import (
    COMMAND_THERMOSTAT_SET,
    FAN_SPEEDS,
    SERVICE_TEMPERATURE,
    SERVICE_THERMOSTAT,
    THERMOSTAT_MODE_BY_HVAC,
    THERMOSTAT_MODES,
)
from .entity import SmartHQServiceEntity
from .util import (
    as_mapping,
    device_services,
    has_command,
    humanize,
    option_map,
    read_temperature,
    service_name,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from pysmarthq.models import Device, Service

    from .coordinator import SmartHQDataUpdateCoordinator
    from .data import SmartHQConfigEntry

PARALLEL_UPDATES = 1

_HVAC = {key: HVACMode(value) for key, value in THERMOSTAT_MODES.items()}
_RAW_BY_HVAC = {HVACMode(key): value for key, value in THERMOSTAT_MODE_BY_HVAC.items()}


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ climate entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        SmartHQThermostat(coordinator, device_id, service)
        for device_id, device in coordinator.data.items()
        for service in device_services(device)
        if service.serviceType == SERVICE_THERMOSTAT
        and has_command(service, COMMAND_THERMOSTAT_SET)
    )


class SmartHQThermostat(SmartHQServiceEntity, ClimateEntity):
    """A thermostat.v1 service."""

    _attr_target_temperature_step = 1.0

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "thermostat",
            service_name(service),
        )

    @property
    def temperature_unit(self) -> str:
        """Return the unit used for the setpoint."""
        _value, unit = self._setpoint()
        return unit

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the HVAC modes this thermostat can report."""
        return list(dict.fromkeys(_HVAC.values()))

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        service = self.service
        if service is None:
            return None
        state = as_mapping(service.state)
        if state.get("on") is False:
            return HVACMode.OFF
        mode = state.get("mode")
        if isinstance(mode, str):
            return _HVAC.get(mode)
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return a sibling temperature that is not a setpoint."""
        value, _unit = _ambient_temperature(
            self.device, self.hass.config.units.temperature_unit
        )
        return value

    @property
    def target_temperature(self) -> float | None:
        """Return the active setpoint."""
        value, _unit = self._setpoint()
        return value

    @property
    def current_humidity(self) -> float | None:
        """Return the humidity reported by the thermostat."""
        service = self.service
        if service is None:
            return None
        humidity = as_mapping(service.state).get("humidity")
        if isinstance(humidity, bool) or not isinstance(humidity, (int, float)):
            return None
        return float(humidity)

    @property
    def fan_modes(self) -> list[str] | None:
        """Return fan speeds when the thermostat reports one."""
        service = self.service
        if service is None or "fanSpeed" not in as_mapping(service.state):
            return None
        return list(option_map(list(FAN_SPEEDS)))

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan speed."""
        service = self.service
        if service is None:
            return None
        raw = as_mapping(service.state).get("fanSpeed")
        if not isinstance(raw, str):
            return None
        for label, value in option_map(list(FAN_SPEEDS)).items():
            if value == raw:
                return label
        return humanize(raw)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the features supported by the current state."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        service = self.service
        if service is not None and "fanSpeed" in as_mapping(service.state):
            features |= ClimateEntityFeature.FAN_MODE
        return features

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the thermostat mode."""
        service = self.service
        raw = _RAW_BY_HVAC.get(hvac_mode)
        if service is None or raw is None:
            return
        fields: dict[str, object] = {"mode": raw}
        if "on" in as_mapping(service.state):
            fields["on"] = hvac_mode is not HVACMode.OFF
        await self.coordinator.async_send_command(
            service, COMMAND_THERMOSTAT_SET, **fields
        )

    async def async_set_temperature(self, **kwargs: object) -> None:
        """Set the active setpoint."""
        service = self.service
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if service is None or not isinstance(temperature, (int, float)):
            return
        _value, unit = self._setpoint()
        prefix = _setpoint_prefix(as_mapping(service.state), self.hvac_mode)
        if unit == UnitOfTemperature.CELSIUS:
            field = f"{prefix}Celsius" if prefix else "coolCelsius"
        else:
            field = f"{prefix}Fahrenheit" if prefix else "coolFahrenheit"
        await self.coordinator.async_send_command(
            service, COMMAND_THERMOSTAT_SET, **{field: temperature}
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        service = self.service
        if service is None:
            return
        raw = option_map(list(FAN_SPEEDS)).get(fan_mode)
        if raw is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_THERMOSTAT_SET, fanSpeed=raw
        )

    async def async_turn_on(self) -> None:
        """Turn the thermostat on."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_THERMOSTAT_SET, on=True
        )

    async def async_turn_off(self) -> None:
        """Turn the thermostat off."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_THERMOSTAT_SET, on=False, mode=_RAW_BY_HVAC[HVACMode.OFF]
        )

    def _setpoint(self) -> tuple[float | None, str]:
        """Return the setpoint for the current mode."""
        service = self.service
        state = as_mapping(service.state) if service is not None else {}
        prefix = _setpoint_prefix(state, self.hvac_mode)
        return read_temperature(
            state, self.hass.config.units.temperature_unit, prefix=prefix
        )


def _setpoint_prefix(state: dict, hvac_mode: HVACMode | None) -> str:
    """Return ``heat`` or ``cool`` for the setpoint fields."""
    if hvac_mode == HVACMode.HEAT or (
        hvac_mode is None
        and "heatFahrenheit" in state
        and "coolFahrenheit" not in state
    ):
        return "heat"
    return "cool"


def _ambient_temperature(device: Device | None, unit: str) -> tuple[float | None, str]:
    """Return a temperature service that is not a setpoint."""
    for service in device_services(device):
        if service.serviceType != SERVICE_TEMPERATURE:
            continue
        domain = service.domainType or ""
        if "setpoint" in domain:
            continue
        value, reported = read_temperature(as_mapping(service.state), unit)
        if value is not None:
            return value, reported
    return None, unit
