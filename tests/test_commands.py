"""Command selection for cooking modes and water heaters."""

from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.smarthq.const import (
    COMMAND_COOKING_MODE_SET,
    COMMAND_COOKING_MODE_START,
    COMMAND_WATER_HEATER_SET,
    DOMAIN,
)

from .common import (
    DEVICE_ID,
    FakeApi,
    FakeStream,
    mock_config_entry,
    register_implementation,
)

CAVITY = "cavity"
BAKE = "cloud.smarthq.domain.cooking.bake"
BROIL = "cloud.smarthq.domain.cooking.broil"
SET = "cloud.smarthq.command.cooking.mode.v1.set"
START = "cloud.smarthq.command.cooking.mode.v1.start"
HYBRID = "cloud.smarthq.type.waterheatermode.hybrid"
HEATPUMP = "cloud.smarthq.type.waterheatermode.heatpump"


def _cooking_device(commands: list[str]) -> dict[str, Any]:
    """Return an oven whose modes accept the given commands."""
    return {
        "brand": "GE",
        "deviceId": DEVICE_ID,
        "deviceType": "cloud.smarthq.device.oven",
        "nickname": "Oven",
        "presence": "ONLINE",
        "services": [
            {
                "domainType": BAKE,
                "serviceDeviceType": CAVITY,
                "serviceId": "mode-bake",
                "serviceType": "cloud.smarthq.service.cooking.mode.v1",
                "state": {},
                "supportedCommands": commands,
            },
            {
                "domainType": BROIL,
                "serviceDeviceType": CAVITY,
                "serviceId": "mode-broil",
                "serviceType": "cloud.smarthq.service.cooking.mode.v1",
                "state": {},
                "supportedCommands": commands,
            },
            {
                "domainType": "cloud.smarthq.domain.cooking.state",
                "serviceDeviceType": CAVITY,
                "serviceId": "state-1",
                "serviceType": "cloud.smarthq.service.cooking.state.v1",
                "state": {"mode": BAKE},
            },
        ],
    }


def _water_heater() -> dict[str, Any]:
    """Return a water heater that advertises a mode outside the built-in list."""
    return {
        "brand": "GE",
        "deviceId": DEVICE_ID,
        "deviceType": "cloud.smarthq.device.waterheater",
        "nickname": "Water heater",
        "presence": "ONLINE",
        "services": [
            {
                "config": {"supportedModes": [HYBRID, HEATPUMP]},
                "domainType": "cloud.smarthq.domain.waterheater",
                "serviceDeviceType": "waterheater",
                "serviceId": "heater-1",
                "serviceType": "cloud.smarthq.service.waterheater.v1",
                "state": {"mode": HYBRID},
                "supportedCommands": [COMMAND_WATER_HEATER_SET],
            }
        ],
    }


async def _setup(hass: HomeAssistant, device: dict[str, Any]):
    """Set up one appliance and record the commands its entities send."""
    FakeApi.reset([device])
    FakeStream.reset()
    register_implementation(hass)
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    commands: list[tuple[Any, ...]] = []

    async def _record(service, command_type, **fields):
        commands.append((service.serviceId, command_type, fields))

    with (
        patch("custom_components.smarthq.SmartHQApi", FakeApi),
        patch("custom_components.smarthq.EventStream", FakeStream),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entry.runtime_data.coordinator.async_send_command = _record
    return entry, commands


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    """Return the entity id for a unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_cook_mode_select_sets_the_mode_when_start_also_exists(
    hass: HomeAssistant,
) -> None:
    """Changing the cook mode uses set, leaving start to the Start button."""
    _entry, commands = await _setup(hass, _cooking_device([SET, START]))
    entity_id = _entity_id(hass, "select", f"{DEVICE_ID}_{CAVITY}_cook_mode")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Broil"},
        blocking=True,
    )

    assert commands == [("mode-broil", COMMAND_COOKING_MODE_SET, {})]


async def test_cook_mode_select_starts_when_that_is_the_only_command(
    hass: HomeAssistant,
) -> None:
    """A mode without a set command still uses start."""
    _entry, commands = await _setup(hass, _cooking_device([START]))
    entity_id = _entity_id(hass, "select", f"{DEVICE_ID}_{CAVITY}_cook_mode")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Broil"},
        blocking=True,
    )

    assert commands == [("mode-broil", COMMAND_COOKING_MODE_START, {})]


async def test_water_heater_sets_a_mode_advertised_by_the_device(
    hass: HomeAssistant,
) -> None:
    """Operation modes come from supportedModes, not only the built-in list."""
    _entry, commands = await _setup(hass, _water_heater())
    entity_id = _entity_id(hass, "water_heater", f"{DEVICE_ID}_heater-1_water_heater")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "Hybrid"
    assert state.attributes["operation_list"] == ["Hybrid", "Heatpump"]
    assert state.attributes["operation_mode"] == "Hybrid"

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": entity_id, "operation_mode": "Heatpump"},
        blocking=True,
    )

    assert commands == [("heater-1", COMMAND_WATER_HEATER_SET, {"mode": HEATPUMP})]
