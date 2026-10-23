"""Small helpers for SmartHQ service payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import UnitOfTemperature

from .const import (
    BINARY_MODE_OFF,
    BINARY_MODE_ON,
    COMPONENT_LABELS,
    PARAMETER_SUPPORTED,
)

if TYPE_CHECKING:
    from pysmarthq.models import Device, Service

_HUMAN_PREFIXES = (
    "cloud.smarthq.type.mode.",
    "cloud.smarthq.type.thermostatmode.",
    "cloud.smarthq.type.waterheatermode.",
    "cloud.smarthq.type.waterheatercapacity.",
    "cloud.smarthq.type.runstatus.",
    "cloud.smarthq.type.cookingstatus.",
    "cloud.smarthq.type.fanspeed.",
    "cloud.smarthq.type.filter.",
    "cloud.smarthq.type.upgrade.",
    "cloud.smarthq.domain.cooking.",
    "cloud.smarthq.domain.",
    "cloud.smarthq.type.",
    "cloud.smarthq.",
)


def as_mapping(value: Any) -> dict[str, Any]:
    """Return a string-keyed mapping, or an empty one."""
    if isinstance(value, dict):
        return value
    return {}


def commands_of(service: Service) -> set[str]:
    """Return the command types a service accepts."""
    return {
        command
        for command in service.supportedCommands or []
        if isinstance(command, str)
    }


def has_command(service: Service, command: str) -> bool:
    """Return whether the service lists a command type."""
    return command in commands_of(service)


def humanize(value: str) -> str:
    """Return a display label for a SmartHQ enum token."""
    text = value
    for prefix in _HUMAN_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return " ".join(part.capitalize() for part in text.replace("_", " ").split("."))


def component_label(service_device_type: str | None) -> str:
    """Return a compartment label for a nested service device type."""
    if not service_device_type:
        return ""
    if "convertibledrawer" in service_device_type:
        last = service_device_type.rsplit(".", 1)[-1].lower()
        if last.startswith("mode") and last[4:].isdigit():
            return f"Convertible drawer mode {last[4:]}"
        return "Convertible drawer"
    return COMPONENT_LABELS.get(service_device_type.rsplit(".", 1)[-1].lower(), "")


def service_name(service: Service, *, fallback: str | None = None) -> str:
    """Return the entity name for a service."""
    label = as_mapping(service.config).get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    domain = service.domainType or ""
    tail = domain.removeprefix("cloud.smarthq.domain.")
    domain_name = " ".join(
        part.capitalize() for part in tail.replace("_", " ").split(".")
    )
    prefix = component_label(service.serviceDeviceType)
    if prefix and prefix.lower() not in domain_name.lower():
        return f"{prefix} {domain_name}".strip()
    if domain_name:
        return domain_name
    return fallback or "SmartHQ"


_BINARY_PAIR_LENGTH = 2


def binary_mode_pair(modes: list[str]) -> tuple[str, str] | None:
    """Return the on and off tokens when modes are a binary pair."""
    if len(modes) != _BINARY_PAIR_LENGTH:
        return None
    on_modes = [mode for mode in modes if mode.rsplit(".", 1)[-1] in BINARY_MODE_ON]
    off_modes = [mode for mode in modes if mode.rsplit(".", 1)[-1] in BINARY_MODE_OFF]
    if len(on_modes) == 1 and len(off_modes) == 1:
        return on_modes[0], off_modes[0]
    return None


def supported_modes(service: Service) -> list[str]:
    """Return the string modes listed on a service config."""
    modes = as_mapping(service.config).get("supportedModes")
    if not isinstance(modes, list):
        return []
    return [mode for mode in modes if isinstance(mode, str)]


def option_map(raw_values: list[str]) -> dict[str, str]:
    """Map display labels back to raw enum tokens."""
    mapping: dict[str, str] = {}
    for raw in raw_values:
        label = humanize(raw)
        if label in mapping and mapping[label] != raw:
            label = raw
        mapping[label] = raw
    return mapping


def choice_options(config: dict[str, Any], field: str) -> list[str] | None:
    """Return a string list in config that belongs to a command field."""
    field_key = field.lower()
    for key, value in config.items():
        if not isinstance(value, list) or not value:
            continue
        if not all(isinstance(item, str) for item in value):
            continue
        key_name = key.lower()
        if field_key in key_name or key_name in field_key:
            return [str(item) for item in value]
    return None


def parameter_supported(config: dict[str, Any], key: str) -> bool:
    """Return whether a cooking parameter is required, optional, or defaulted."""
    return config.get(key) in PARAMETER_SUPPORTED


def first_number(state: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    """Return the first finite number stored under the given keys."""
    for key in keys:
        value = state.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        return float(value)
    return None


def read_temperature(
    state: dict[str, Any],
    unit: str,
    *,
    prefix: str = "",
) -> tuple[float | None, str]:
    """
    Return a temperature and the unit it was reported in.

    Converted fields are only used when the device omitted the measured value.
    The unit follows Home Assistant when both scales are present.
    """
    fahrenheit_key = f"{prefix}Fahrenheit" if prefix else "fahrenheit"
    celsius_key = f"{prefix}Celsius" if prefix else "celsius"
    fahrenheit = first_number(state, (fahrenheit_key, f"{fahrenheit_key}Converted"))
    celsius = first_number(state, (celsius_key, f"{celsius_key}Converted"))
    if unit == UnitOfTemperature.CELSIUS and celsius is not None:
        return celsius, UnitOfTemperature.CELSIUS
    if unit == UnitOfTemperature.FAHRENHEIT and fahrenheit is not None:
        return fahrenheit, UnitOfTemperature.FAHRENHEIT
    if fahrenheit is not None:
        return fahrenheit, UnitOfTemperature.FAHRENHEIT
    if celsius is not None:
        return celsius, UnitOfTemperature.CELSIUS
    return None, unit


def temperature_bounds(
    config: dict[str, Any],
    unit: str,
    *,
    prefix: str = "",
) -> tuple[float | None, float | None]:
    """Return minimum and maximum temperatures from a service config."""
    if unit == UnitOfTemperature.CELSIUS:
        stem = f"{prefix}Celsius" if prefix else "celsius"
    else:
        stem = f"{prefix}Fahrenheit" if prefix else "fahrenheit"
    return (
        first_number(
            config, (f"{stem}Minimum", f"minimum{stem[:1].upper()}{stem[1:]}")
        ),
        first_number(
            config, (f"{stem}Maximum", f"maximum{stem[:1].upper()}{stem[1:]}")
        ),
    )


def device_services(device: Device | None) -> list[Service]:
    """Return services that have an id and a type."""
    if device is None:
        return []
    return [
        service
        for service in device.services or []
        if isinstance(service.serviceId, str) and isinstance(service.serviceType, str)
    ]


def find_service(device: Device | None, service_id: str) -> Service | None:
    """Return the live service with this id."""
    for service in device_services(device):
        if service.serviceId == service_id:
            return service
    return None


def cooking_command_fields(service: Service, unit: str) -> dict[str, Any]:
    """
    Copy supported cooking parameters from state into command fields.

    State uses ``cavityTemperatureFahrenheit``. The command uses ``cavityFahrenheit``.
    """
    state = as_mapping(service.state)
    config = as_mapping(service.config)
    fields: dict[str, Any] = {}
    if parameter_supported(config, "cavityTemperatureSupported"):
        _put_temperature(fields, state, unit, "cavityTemperature", "cavity")
    if parameter_supported(config, "probeTemperatureSupported"):
        _put_temperature(fields, state, unit, "probeTemperature", "probe")
    if parameter_supported(config, "cookTimeSupported"):
        cook_time = first_number(state, ("cookTimeInitial", "cookTimeSeconds"))
        if cook_time is not None:
            fields["cookTimeSeconds"] = int(cook_time)
    if parameter_supported(config, "numericOptionSupported"):
        numeric = first_number(state, ("numericOptionValue",))
        if numeric is not None:
            fields["numericOptionValue"] = numeric
    if parameter_supported(config, "optionsSupported"):
        option = state.get("option")
        if isinstance(option, str):
            fields["option"] = option
    for level in (
        "powerLevelConvection",
        "powerLevelLower",
        "powerLevelMicrowave",
        "powerLevelUpper",
    ):
        if parameter_supported(config, f"{level}Supported"):
            value = first_number(state, (level,))
            if value is not None:
                fields[level] = int(value)
    doneness = state.get("donenessLevel")
    if parameter_supported(config, "donenessLevelSupported") and isinstance(
        doneness, str
    ):
        fields["donenessLevel"] = doneness
    return fields


def _put_temperature(
    fields: dict[str, Any],
    state: dict[str, Any],
    unit: str,
    state_prefix: str,
    command_prefix: str,
) -> None:
    """Add the temperature command field that matches the Home Assistant unit."""
    value, reported = read_temperature(state, unit, prefix=state_prefix)
    if value is None:
        return
    if reported == UnitOfTemperature.CELSIUS:
        fields[f"{command_prefix}Celsius"] = value
        return
    fields[f"{command_prefix}Fahrenheit"] = value
