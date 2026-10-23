"""Number platform for SmartHQ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature, UnitOfTime

from .const import (
    BREW_NUMBER_FIELDS,
    COMMAND_BREW_SET,
    COMMAND_COOKING_MODE_START,
    COMMAND_DOUBLE_SET,
    COMMAND_INTEGER_SET,
    COMMAND_TEMPERATURE_SET,
    SERVICE_BREW_MODE,
    SERVICE_COOKING_MODE,
    SERVICE_COOKING_STATE,
)
from .entity import SmartHQEntity, SmartHQServiceEntity
from .service_map import double_kind, integer_kind, temperature_kind
from .util import (
    as_mapping,
    cooking_command_fields,
    cooking_update_command,
    device_services,
    first_number,
    has_command,
    parameter_supported,
    read_temperature,
    service_name,
    temperature_bounds,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from pysmarthq.models import Device, Service

    from .coordinator import SmartHQDataUpdateCoordinator
    from .data import SmartHQConfigEntry

PARALLEL_UPDATES = 1

_COOKING_NUMBERS = (
    (
        "cavity",
        "cavityTemperatureSupported",
        "Cavity temperature",
        NumberDeviceClass.TEMPERATURE,
        None,
    ),
    (
        "probe",
        "probeTemperatureSupported",
        "Probe temperature",
        NumberDeviceClass.TEMPERATURE,
        None,
    ),
    (
        "cook_time",
        "cookTimeSupported",
        "Cook time",
        NumberDeviceClass.DURATION,
        UnitOfTime.SECONDS,
    ),
    ("numeric_option", "numericOptionSupported", "Numeric option", None, None),
    (
        "power_convection",
        "powerLevelConvectionSupported",
        "Convection power",
        None,
        None,
    ),
    ("power_lower", "powerLevelLowerSupported", "Lower power", None, None),
    ("power_microwave", "powerLevelMicrowaveSupported", "Microwave power", None, None),
    ("power_upper", "powerLevelUpperSupported", "Upper power", None, None),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ numbers."""
    coordinator = entry.runtime_data.coordinator
    entities: list[NumberEntity] = []
    for device_id, device in coordinator.data.items():
        entities.extend(_numbers_for_device(coordinator, device_id, device))
    async_add_entities(entities)


def _numbers_for_device(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    device: Device,
) -> list[NumberEntity]:
    """Return numbers for one appliance."""
    entities: list[NumberEntity] = []
    cooking: dict[str, list[Service]] = {}
    for service in device_services(device):
        service_type = service.serviceType
        if temperature_kind(service) == "number":
            entities.append(SmartHQTemperatureNumber(coordinator, device_id, service))
        elif integer_kind(service) == "number":
            entities.append(SmartHQIntegerNumber(coordinator, device_id, service))
        elif double_kind(service) == "number":
            entities.append(SmartHQDoubleNumber(coordinator, device_id, service))
        elif service_type == SERVICE_BREW_MODE and has_command(
            service, COMMAND_BREW_SET
        ):
            entities.extend(
                SmartHQBrewNumber(coordinator, device_id, service, field)
                for field in BREW_NUMBER_FIELDS
                if field in as_mapping(service.state)
                or field in as_mapping(service.config)
            )
        elif service_type == SERVICE_COOKING_MODE:
            cooking.setdefault(service.serviceDeviceType or device_id, []).append(
                service
            )
    for service_device_type, services in cooking.items():
        config = _merged_config(services)
        entities.extend(
            SmartHQCookingNumber(
                coordinator,
                device_id,
                service_device_type,
                kind,
                name,
                device_class,
                unit,
            )
            for kind, flag, name, device_class, unit in _COOKING_NUMBERS
            if parameter_supported(config, flag)
        )
    return entities


def _merged_config(services: list[Service]) -> dict:
    """Return a config that is supported when any mode in the group supports it."""
    merged: dict = {}
    for service in services:
        merged.update(
            {
                key: value
                for key, value in as_mapping(service.config).items()
                if parameter_supported({key: value}, key)
            }
        )
    return merged


class SmartHQTemperatureNumber(SmartHQServiceEntity, NumberEntity):
    """A writable temperature service."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the temperature number."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "temperature",
            service_name(service),
        )

    @property
    def native_value(self) -> float | None:
        """Return the setpoint."""
        value, _unit = self._reading()
        return value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the temperature unit."""
        _value, unit = self._reading()
        return unit

    @property
    def native_min_value(self) -> float:
        """Return the lowest setpoint."""
        low, _high = self._bounds()
        return low if low is not None else self._default_min()

    @property
    def native_max_value(self) -> float:
        """Return the highest setpoint."""
        _low, high = self._bounds()
        return high if high is not None else self._default_max()

    async def async_set_native_value(self, value: float) -> None:
        """Set the temperature."""
        service = self.service
        if service is None:
            return
        _reading, unit = self._reading()
        if unit == UnitOfTemperature.CELSIUS:
            await self.coordinator.async_send_command(
                service, COMMAND_TEMPERATURE_SET, celsius=value
            )
            return
        await self.coordinator.async_send_command(
            service, COMMAND_TEMPERATURE_SET, fahrenheit=value
        )

    def _reading(self) -> tuple[float | None, str]:
        """Return the preferred setpoint."""
        service = self.service
        state = as_mapping(service.state) if service is not None else {}
        return read_temperature(state, self.hass.config.units.temperature_unit)

    def _bounds(self) -> tuple[float | None, float | None]:
        """Return configured limits in the displayed unit."""
        service = self.service
        config = as_mapping(service.config) if service is not None else {}
        _value, unit = self._reading()
        return temperature_bounds(config, unit)

    def _default_min(self) -> float:
        """Return a fallback minimum when the config has no limit."""
        if self.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            return -18
        return 0

    def _default_max(self) -> float:
        """Return a fallback maximum when the config has no limit."""
        if self.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            return 38
        return 100


class SmartHQIntegerNumber(SmartHQServiceEntity, NumberEntity):
    """A writable integer service."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the integer number from its config."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "integer",
            service_name(service),
        )
        config = as_mapping(service.config)
        allowed = config.get("allowedValues")
        if isinstance(allowed, list) and allowed:
            numbers = [
                float(item)
                for item in allowed
                if isinstance(item, (int, float)) and not isinstance(item, bool)
            ]
            self._attr_native_min_value = min(numbers) if numbers else 0
            self._attr_native_max_value = max(numbers) if numbers else 100
            return
        low = first_number(config, ("minimum",))
        high = first_number(config, ("maximum",))
        self._attr_native_min_value = low if low is not None else 0
        self._attr_native_max_value = high if high is not None else 100

    @property
    def native_value(self) -> float | None:
        """Return the integer value."""
        service = self.service
        if service is None:
            return None
        return first_number(as_mapping(service.state), ("value",))

    async def async_set_native_value(self, value: float) -> None:
        """Set the integer."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_INTEGER_SET, value=int(value)
        )


class SmartHQDoubleNumber(SmartHQServiceEntity, NumberEntity):
    """A writable double service."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.1

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the double number."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "double",
            service_name(service),
        )
        config = as_mapping(service.config)
        low = first_number(config, ("minimum",))
        high = first_number(config, ("maximum",))
        self._attr_native_min_value = low if low is not None else 0
        self._attr_native_max_value = high if high is not None else 100

    @property
    def native_value(self) -> float | None:
        """Return the double value."""
        service = self.service
        if service is None:
            return None
        return first_number(as_mapping(service.state), ("valueDouble", "value"))

    async def async_set_native_value(self, value: float) -> None:
        """Set the double."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_DOUBLE_SET, valueDouble=value
        )


class SmartHQBrewNumber(SmartHQServiceEntity, NumberEntity):
    """A numeric brew setting."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        field: str,
    ) -> None:
        """Store the brew command field."""
        label = " ".join(part.capitalize() for part in _split_identifier(field))
        super().__init__(coordinator, device_id, service.serviceId or "", field, label)
        self._field = field
        config = as_mapping(service.config)
        low = first_number(config, (f"{field}Minimum", "minimum"))
        high = first_number(config, (f"{field}Maximum", "maximum"))
        self._attr_native_min_value = low if low is not None else 0
        self._attr_native_max_value = high if high is not None else 100

    @property
    def native_value(self) -> float | None:
        """Return the brew setting."""
        service = self.service
        if service is None:
            return None
        return first_number(as_mapping(service.state), (self._field,))

    async def async_set_native_value(self, value: float) -> None:
        """Set the brew setting."""
        service = self.service
        if service is None:
            return
        await self.coordinator.async_send_command(
            service, COMMAND_BREW_SET, **{self._field: value}
        )


class SmartHQCookingNumber(SmartHQEntity, NumberEntity):
    """A cooking parameter shared by the modes of one cavity."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service_device_type: str,
        kind: str,
        name: str,
        device_class: NumberDeviceClass | None,
        unit: str | None,
    ) -> None:
        """Store which cooking parameter this number edits."""
        super().__init__(coordinator, device_id, f"{service_device_type}_{kind}")
        self._service_device_type = service_device_type
        self._kind = kind
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, following Home Assistant for temperatures."""
        if self._kind in {"cavity", "probe"}:
            return self.hass.config.units.temperature_unit
        return self._attr_native_unit_of_measurement

    @property
    def native_value(self) -> float | None:
        """Return the parameter on the active cooking mode."""
        service = self._active()
        if service is None:
            return None
        return self._value(service)

    @property
    def native_min_value(self) -> float:
        """Return the parameter minimum."""
        low, _high = self._bounds()
        if low is not None:
            return low
        if self._kind in {"cavity", "probe"}:
            return (
                30
                if self.native_unit_of_measurement == UnitOfTemperature.CELSIUS
                else 80
            )
        if self._kind.startswith("power"):
            return 0
        return 0

    @property
    def native_max_value(self) -> float:
        """Return the parameter maximum."""
        _low, high = self._bounds()
        if high is not None:
            return high
        if self._kind in {"cavity", "probe"}:
            return (
                260
                if self.native_unit_of_measurement == UnitOfTemperature.CELSIUS
                else 500
            )
        if self._kind.startswith("power"):
            return 10
        if self._kind == "cook_time":
            return 86400
        return 100

    async def async_set_native_value(self, value: float) -> None:
        """Set the parameter on the active cooking mode."""
        service = self._active()
        if service is None:
            return
        command = cooking_update_command(service)
        if command is None:
            return
        fields = {}
        if command == COMMAND_COOKING_MODE_START:
            fields = cooking_command_fields(
                service, self.hass.config.units.temperature_unit
            )
        fields.update(self._command_value(value))
        await self.coordinator.async_send_command(service, command, **fields)

    def _modes(self) -> list[Service]:
        """Return cooking mode services for this cavity."""
        return [
            service
            for service in device_services(self.device)
            if service.serviceType == SERVICE_COOKING_MODE
            and service.serviceDeviceType == self._service_device_type
        ]

    def _active(self) -> Service | None:
        """Return the mode that matches the cooking state, or the first mode."""
        modes = self._modes()
        current = None
        for service in device_services(self.device):
            if service.serviceType != SERVICE_COOKING_STATE:
                continue
            if service.serviceDeviceType not in {None, self._service_device_type}:
                continue
            mode = as_mapping(service.state).get("mode")
            if isinstance(mode, str):
                current = mode
                break
        for service in modes:
            if service.domainType == current:
                return service
        return modes[0] if modes else None

    def _value(self, service: Service) -> float | None:
        """Return this parameter from a mode state."""
        state = as_mapping(service.state)
        unit = self.hass.config.units.temperature_unit
        if self._kind == "cavity":
            value, _reported = read_temperature(state, unit, prefix="cavityTemperature")
            return value
        if self._kind == "probe":
            value, _reported = read_temperature(state, unit, prefix="probeTemperature")
            return value
        if self._kind == "cook_time":
            return first_number(state, ("cookTimeInitial", "cookTimeSeconds"))
        if self._kind == "numeric_option":
            return first_number(state, ("numericOptionValue",))
        return first_number(state, (self._power_field(),))

    def _bounds(self) -> tuple[float | None, float | None]:
        """Return limits from the active mode config."""
        service = self._active()
        config = as_mapping(service.config) if service is not None else {}
        unit = self.hass.config.units.temperature_unit
        if self._kind == "cavity":
            return temperature_bounds(config, unit, prefix="cavityTemperature")
        if self._kind == "probe":
            return temperature_bounds(config, unit, prefix="probeTemperature")
        if self._kind == "cook_time":
            return first_number(config, ("cookTimeMinimum",)), first_number(
                config, ("cookTimeMaximum",)
            )
        if self._kind == "numeric_option":
            return (
                first_number(config, ("numericOptionMinimum",)),
                first_number(config, ("numericOptionMaximum",)),
            )
        return 0, 10

    def _command_value(self, value: float) -> dict[str, float | int]:
        """Return the command field for a new value."""
        unit = self.hass.config.units.temperature_unit
        if self._kind == "cavity":
            key = (
                "cavityCelsius"
                if unit == UnitOfTemperature.CELSIUS
                else "cavityFahrenheit"
            )
            return {key: value}
        if self._kind == "probe":
            key = (
                "probeCelsius"
                if unit == UnitOfTemperature.CELSIUS
                else "probeFahrenheit"
            )
            return {key: value}
        if self._kind == "cook_time":
            return {"cookTimeSeconds": int(value)}
        if self._kind == "numeric_option":
            return {"numericOptionValue": value}
        return {self._power_field(): int(value)}

    def _power_field(self) -> str:
        """Return the power-level state field for this number."""
        return {
            "power_convection": "powerLevelConvection",
            "power_lower": "powerLevelLower",
            "power_microwave": "powerLevelMicrowave",
            "power_upper": "powerLevelUpper",
        }[self._kind]


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
