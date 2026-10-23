"""Sensor platform for SmartHQ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)

from .const import (
    BREW_NUMBER_FIELDS,
    COMMAND_BREW_SET,
    DISHWASHER_STRING_FIELDS,
    LAUNDRY_STRING_FIELDS,
    SERVICE_BATTERY,
    SERVICE_BREW_MODE,
    SERVICE_COFFEE_V1,
    SERVICE_COFFEE_V2,
    SERVICE_COOKING_STATE,
    SERVICE_CYCLE_TIMER,
    SERVICE_DISHWASHER_MODE,
    SERVICE_DISHWASHER_STATE,
    SERVICE_ENVIRONMENTAL,
    SERVICE_FILTER,
    SERVICE_FIRMWARE,
    SERVICE_LAUNDRY_MODE,
    SERVICE_LAUNDRY_STATE,
    SERVICE_METER,
    SERVICE_STOPWATCH,
    SERVICE_STRING,
    STATUS_FIELDS,
)
from .entity import SmartHQServiceEntity
from .service_map import double_kind, integer_kind, mode_kind, temperature_kind
from .util import (
    as_mapping,
    choice_options,
    device_services,
    first_number,
    has_command,
    humanize,
    read_temperature,
    service_name,
    supported_modes,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from pysmarthq.models import Device, Service

    from .coordinator import SmartHQDataUpdateCoordinator
    from .data import SmartHQConfigEntry

PARALLEL_UPDATES = 0

_INTEGER_UNITS: dict[str, tuple[SensorDeviceClass | None, str | None]] = {
    "cloud.smarthq.type.integerunits.amps": (
        SensorDeviceClass.CURRENT,
        UnitOfElectricCurrent.AMPERE,
    ),
    "cloud.smarthq.type.integerunits.days": (
        SensorDeviceClass.DURATION,
        UnitOfTime.DAYS,
    ),
    "cloud.smarthq.type.integerunits.dbm": (
        SensorDeviceClass.SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
    "cloud.smarthq.type.integerunits.gallons": (
        SensorDeviceClass.VOLUME,
        UnitOfVolume.GALLONS,
    ),
    "cloud.smarthq.type.integerunits.hours": (
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
    ),
    "cloud.smarthq.type.integerunits.kwh": (
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
    ),
    "cloud.smarthq.type.integerunits.minutes": (
        SensorDeviceClass.DURATION,
        UnitOfTime.MINUTES,
    ),
    "cloud.smarthq.type.integerunits.percentage": (None, PERCENTAGE),
    "cloud.smarthq.type.integerunits.seconds": (
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
    ),
    "cloud.smarthq.type.integerunits.temperature.fahrenheit": (
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.FAHRENHEIT,
    ),
    "cloud.smarthq.type.integerunits.volts": (
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
    ),
    "cloud.smarthq.type.integerunits.watts": (
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
    ),
}

_ENV_DOMAINS: dict[str, tuple[SensorDeviceClass | None, str | None]] = {
    "cloud.smarthq.domain.sensor.humidity": (SensorDeviceClass.HUMIDITY, PERCENTAGE),
    "cloud.smarthq.domain.sensor.particles.10um": (
        SensorDeviceClass.PM10,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "cloud.smarthq.domain.sensor.particles.10um.index": (SensorDeviceClass.AQI, None),
    "cloud.smarthq.domain.sensor.particles.1um": (
        getattr(SensorDeviceClass, "PM1", None),
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "cloud.smarthq.domain.sensor.particles.1um.index": (SensorDeviceClass.AQI, None),
    "cloud.smarthq.domain.sensor.particles.4um": (
        getattr(SensorDeviceClass, "PM4", None),
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "cloud.smarthq.domain.sensor.particles.4um.index": (SensorDeviceClass.AQI, None),
    "cloud.smarthq.domain.sensor.particles.fine.air": (
        SensorDeviceClass.PM25,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "cloud.smarthq.domain.sensor.particles.fine.air.index": (
        SensorDeviceClass.AQI,
        None,
    ),
    "cloud.smarthq.domain.sensor.temperature.environmental": (
        SensorDeviceClass.TEMPERATURE,
        None,
    ),
    "cloud.smarthq.domain.sensor.voc": (
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
}

_DURATION_KEYS = (
    "elapsedSeconds",
    "elapsedTime",
    "remainingSeconds",
    "remainingTimeSeconds",
    "seconds",
    "secondsRemaining",
    "timeRemaining",
    "value",
)
_STATE_SERVICES = frozenset(
    {SERVICE_COOKING_STATE, SERVICE_DISHWASHER_STATE, SERVICE_LAUNDRY_STATE}
)
_TEXT_FIELD_SERVICES = {
    SERVICE_BREW_MODE: BREW_NUMBER_FIELDS,
    SERVICE_DISHWASHER_MODE: DISHWASHER_STRING_FIELDS,
    SERVICE_LAUNDRY_MODE: LAUNDRY_STRING_FIELDS,
}


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SmartHQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartHQ sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []
    for device_id, device in coordinator.data.items():
        entities.extend(_sensors_for_device(coordinator, device_id, device))
    async_add_entities(entities)


def _sensors_for_device(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    device: Device,
) -> list[SensorEntity]:
    """Return sensors described by one appliance."""
    entities: list[SensorEntity] = []
    for service in device_services(device):
        entities.extend(_sensors_for_service(coordinator, device_id, service))
    return entities


def _sensors_for_service(  # noqa: PLR0911, PLR0912
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    service: Service,
) -> list[SensorEntity]:
    """Return sensors for one service."""
    service_type = service.serviceType
    if temperature_kind(service) == "sensor":
        return [SmartHQTemperatureSensor(coordinator, device_id, service)]
    if integer_kind(service) == "sensor":
        return [SmartHQIntegerSensor(coordinator, device_id, service)]
    if double_kind(service) == "sensor":
        return [
            SmartHQValueSensor(
                coordinator, device_id, service, ("valueDouble", "value"), "value"
            )
        ]
    if service_type == SERVICE_METER:
        return [SmartHQMeterSensor(coordinator, device_id, service)]
    if service_type == SERVICE_ENVIRONMENTAL:
        return [SmartHQEnvironmentalSensor(coordinator, device_id, service)]
    if service_type == SERVICE_STRING:
        return [
            SmartHQTextSensor(
                coordinator,
                device_id,
                service,
                service_name(service),
                ("stringValue", "value"),
            )
        ]
    if service_type == SERVICE_FIRMWARE:
        return [SmartHQFirmwareSensor(coordinator, device_id, service)]
    if service_type == SERVICE_BATTERY:
        return [SmartHQBatterySensor(coordinator, device_id, service)]
    if service_type == SERVICE_FILTER:
        return _filter_sensors(coordinator, device_id, service)
    if service_type in {SERVICE_CYCLE_TIMER, SERVICE_STOPWATCH}:
        return [SmartHQDurationSensor(coordinator, device_id, service)]
    if mode_kind(service) == "sensor":
        return [SmartHQModeSensor(coordinator, device_id, service)]
    if service_type in _STATE_SERVICES or service_type in {
        SERVICE_COFFEE_V1,
        SERVICE_COFFEE_V2,
        SERVICE_BREW_MODE,
    }:
        return _status_sensors(coordinator, device_id, service)
    if service_type in _TEXT_FIELD_SERVICES:
        return _field_sensors(coordinator, device_id, service)
    return []


def _filter_sensors(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    service: Service,
) -> list[SensorEntity]:
    """Return filter usage and type sensors."""
    state = as_mapping(service.state)
    entities: list[SensorEntity] = []
    if "usagePercent" in state:
        entities.append(SmartHQFilterUsageSensor(coordinator, device_id, service))
    if isinstance(state.get("type"), str):
        entities.append(
            SmartHQTextSensor(
                coordinator, device_id, service, "Filter type", ("type",), suffix="type"
            )
        )
    return entities


def _status_sensors(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    service: Service,
) -> list[SensorEntity]:
    """Return one sensor per status field present on the service."""
    state = as_mapping(service.state)
    config = as_mapping(service.config)
    entities: list[SensorEntity] = []
    for field, name in STATUS_FIELDS:
        if field not in state:
            continue
        if field != "runStatus" and choice_options(config, field):
            continue
        entities.append(
            SmartHQTextSensor(
                coordinator, device_id, service, name, (field,), suffix=field
            )
        )
    if service.serviceType == SERVICE_BREW_MODE:
        entities.extend(
            SmartHQValueSensor(
                coordinator,
                device_id,
                service,
                (field,),
                field,
                name=service_name(service, fallback=field),
            )
            for field in BREW_NUMBER_FIELDS
            if field in state and not has_command(service, COMMAND_BREW_SET)
        )
    return entities


def _field_sensors(
    coordinator: SmartHQDataUpdateCoordinator,
    device_id: str,
    service: Service,
) -> list[SensorEntity]:
    """Return sensors for string fields that have no config option list."""
    state = as_mapping(service.state)
    config = as_mapping(service.config)
    entities: list[SensorEntity] = []
    for field in _TEXT_FIELD_SERVICES.get(service.serviceType or "", ()):
        if field not in state or choice_options(config, field):
            continue
        if not isinstance(state.get(field), str):
            continue
        label = " ".join(part.capitalize() for part in _split_identifier(field))
        entities.append(
            SmartHQTextSensor(
                coordinator, device_id, service, label, (field,), suffix=field
            )
        )
    return entities


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


class SmartHQTemperatureSensor(SmartHQServiceEntity, SensorEntity):
    """A read-only temperature service."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "temperature",
            service_name(service),
        )

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        value, _unit = self._reading()
        return value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        _value, unit = self._reading()
        return unit

    def _reading(self) -> tuple[float | None, str]:
        """Return the preferred temperature reading."""
        service = self.service
        state = as_mapping(service.state) if service is not None else {}
        return read_temperature(state, self.hass.config.units.temperature_unit)


class SmartHQIntegerSensor(SmartHQServiceEntity, SensorEntity):
    """A read-only integer service."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the integer sensor and its unit."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            "integer",
            service_name(service),
        )
        units = as_mapping(service.config).get("integerUnits")
        device_class, unit = (
            _INTEGER_UNITS.get(units, (None, None))
            if isinstance(units, str)
            else (None, None)
        )
        domain = service.domainType or ""
        if domain.endswith("rssi") or unit == SIGNAL_STRENGTH_DECIBELS_MILLIWATT:
            device_class = SensorDeviceClass.SIGNAL_STRENGTH
            unit = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif device_class is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | float | None:
        """Return the integer value."""
        service = self.service
        if service is None:
            return None
        value = first_number(as_mapping(service.state), ("value",))
        if value is None:
            return None
        if value.is_integer():
            return int(value)
        return value


class SmartHQValueSensor(SmartHQServiceEntity, SensorEntity):
    """A numeric sensor that reads the first present state key."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(  # noqa: PLR0913
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        keys: tuple[str, ...],
        suffix: str,
        *,
        name: str | None = None,
    ) -> None:
        """Store the state keys to read."""
        super().__init__(
            coordinator,
            device_id,
            service.serviceId or "",
            suffix,
            name or service_name(service),
        )
        self._keys = keys

    @property
    def native_value(self) -> float | None:
        """Return the numeric state."""
        service = self.service
        if service is None:
            return None
        return first_number(as_mapping(service.state), self._keys)


class SmartHQMeterSensor(SmartHQValueSensor):
    """A meter service."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize a meter sensor from its domain."""
        super().__init__(
            coordinator, device_id, service, ("value", "valueDouble"), "meter"
        )
        domain = service.domainType or ""
        if "energy" in domain:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif "voltage" in domain:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        elif "water" in domain:
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_native_unit_of_measurement = UnitOfVolume.GALLONS


class SmartHQEnvironmentalSensor(SmartHQValueSensor):
    """An environmental sensor service."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize an environmental sensor from its domain."""
        super().__init__(
            coordinator, device_id, service, ("value", "valueDouble"), "environment"
        )
        device_class, unit = _ENV_DOMAINS.get(service.domainType or "", (None, None))
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS


class SmartHQTextSensor(SmartHQServiceEntity, SensorEntity):
    """A sensor whose state is a string or SmartHQ enum."""

    def __init__(  # noqa: PLR0913
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
        name: str,
        keys: tuple[str, ...],
        *,
        suffix: str = "text",
    ) -> None:
        """Store the state keys to display."""
        super().__init__(coordinator, device_id, service.serviceId or "", suffix, name)
        self._keys = keys

    @property
    def native_value(self) -> str | None:
        """Return the display value."""
        service = self.service
        if service is None:
            return None
        state = as_mapping(service.state)
        for key in self._keys:
            value = state.get(key)
            if isinstance(value, str) and value:
                if value.startswith("cloud.smarthq."):
                    return humanize(value)
                return value
        return None


class SmartHQModeSensor(SmartHQTextSensor):
    """A read-only mode service."""

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the mode sensor."""
        super().__init__(
            coordinator,
            device_id,
            service,
            service_name(service),
            ("mode",),
            suffix="mode",
        )

    @property
    def options(self) -> list[str] | None:
        """Return known modes when the config lists them."""
        service = self.service
        if service is None:
            return None
        labels = [humanize(mode) for mode in supported_modes(service)]
        return labels or None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Use the enum device class when the mode list is known."""
        if self.options:
            return SensorDeviceClass.ENUM
        return None


class SmartHQFirmwareSensor(SmartHQTextSensor):
    """The installed firmware version."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the firmware version sensor."""
        super().__init__(
            coordinator,
            device_id,
            service,
            _firmware_name(service),
            ("versionCurrent",),
            suffix="firmware",
        )


class SmartHQBatterySensor(SmartHQValueSensor):
    """A battery percentage."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(
            coordinator,
            device_id,
            service,
            ("percentage", "percent", "value", "level"),
            "battery",
        )


class SmartHQFilterUsageSensor(SmartHQValueSensor):
    """Filter life used, as a percentage."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the filter usage sensor."""
        super().__init__(
            coordinator,
            device_id,
            service,
            ("usagePercent",),
            "usage",
            name="Filter usage",
        )


class SmartHQDurationSensor(SmartHQValueSensor):
    """A cycle timer or stopwatch, in seconds."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self,
        coordinator: SmartHQDataUpdateCoordinator,
        device_id: str,
        service: Service,
    ) -> None:
        """Initialize the duration sensor."""
        super().__init__(coordinator, device_id, service, _DURATION_KEYS, "duration")


def _firmware_name(service: Service) -> str:
    """Return a firmware sensor name that includes the module when it is known."""
    last = (service.serviceDeviceType or "").rsplit(".", 1)[-1]
    if last and last not in {"appliance", "firmware"}:
        return f"{last.replace('_', ' ').capitalize()} firmware"
    return "Firmware"
