"""Entity tests for service-driven SmartHQ devices."""

import json
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pysmarthq.events import ServiceEvent

from custom_components.smarthq.const import DOMAIN
from custom_components.smarthq.diagnostics import async_get_config_entry_diagnostics

from .common import (
    DEVICE_ID,
    FakeApi,
    FakeStream,
    mock_config_entry,
    register_implementation,
)

TEMPERATURE = "cloud.smarthq.service.temperature"
TOGGLE = "cloud.smarthq.service.toggle"
MODE = "cloud.smarthq.service.mode"
DOOR = "cloud.smarthq.service.door"
THERMOSTAT = "cloud.smarthq.service.thermostat.v1"
UNKNOWN = "cloud.smarthq.service.barcode"


def _service(service_id: str, service_type: str, **extra):
    """Return one service payload."""
    payload = {
        "domainType": service_type.replace(".service.", ".domain."),
        "serviceId": service_id,
        "serviceType": service_type,
    }
    payload.update(extra)
    return payload


def _device() -> dict:
    """Return an appliance whose entities come from services, not its device type."""
    return {
        "brand": "GE",
        "deviceId": DEVICE_ID,
        "deviceType": "cloud.smarthq.device.something-unknown",
        "macAddress": "aa:bb:cc:dd:ee:ff",
        "nickname": "Kitchen oven",
        "presence": "ONLINE",
        "serial": "SECRET-SERIAL",
        "services": [
            _service(
                "temp-1",
                TEMPERATURE,
                state={"celsius": 21, "fahrenheit": 70},
            ),
            _service(
                "toggle-1",
                TOGGLE,
                state={"on": False},
                supportedCommands=["cloud.smarthq.command.toggle.set"],
            ),
            _service(
                "door-1",
                DOOR,
                state={"singleOpen": True},
            ),
            _service(
                "mode-1",
                MODE,
                config={
                    "supportedModes": [
                        "cloud.smarthq.type.mode.low",
                        "cloud.smarthq.type.mode.medium",
                        "cloud.smarthq.type.mode.high",
                    ]
                },
                state={"mode": "cloud.smarthq.type.mode.low"},
                supportedCommands=["cloud.smarthq.command.mode.set"],
            ),
            _service(
                "thermo-1",
                THERMOSTAT,
                state={
                    "coolCelsius": 22,
                    "coolFahrenheit": 72,
                    "fanSpeed": "cloud.smarthq.type.fanspeed.auto",
                    "mode": "cloud.smarthq.type.thermostatmode.cool",
                    "on": True,
                },
                supportedCommands=["cloud.smarthq.command.thermostat.v1.set"],
            ),
            _service("barcode-1", UNKNOWN, state={"value": "ignored"}),
        ],
    }


async def _setup(hass: HomeAssistant):
    """Set up the fixture appliance."""
    FakeApi.reset([_device()])
    FakeStream.reset()
    register_implementation(hass)
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch("custom_components.smarthq.SmartHQApi", FakeApi),
        patch("custom_components.smarthq.EventStream", FakeStream),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    """Return the entity id for a unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_push_updates_sensor_and_switch_without_rest(hass: HomeAssistant) -> None:
    """A service event updates entities without another device fetch."""
    await _setup(hass)
    calls_after_setup = FakeApi.calls
    temperature = _entity_id(hass, "sensor", f"{DEVICE_ID}_temp-1_temperature")
    toggle = _entity_id(hass, "switch", f"{DEVICE_ID}_toggle-1_toggle")
    assert float(hass.states.get(temperature).state) == 21
    assert hass.states.get(toggle).state == "off"

    stream = FakeStream.instances[-1]
    await stream.queue.put(
        ServiceEvent(
            {
                "deviceId": DEVICE_ID,
                "kind": "pubsub#service",
                "serviceId": "temp-1",
                "serviceType": TEMPERATURE,
                "state": {"celsius": 82, "fahrenheit": 180},
            }
        )
    )
    await stream.queue.put(
        ServiceEvent(
            {
                "deviceId": DEVICE_ID,
                "kind": "pubsub#service",
                "serviceId": "toggle-1",
                "serviceType": TOGGLE,
                "state": {"on": True},
            }
        )
    )
    await hass.async_block_till_done()

    assert float(hass.states.get(temperature).state) == 82
    assert hass.states.get(toggle).state == "on"
    assert FakeApi.calls == calls_after_setup


async def test_fixture_entities_and_unknown_service(hass: HomeAssistant) -> None:
    """Door, mode, and thermostat services create entities. Unknown services do not."""
    entry = await _setup(hass)
    door = _entity_id(hass, "binary_sensor", f"{DEVICE_ID}_door-1_singleOpen")
    mode = _entity_id(hass, "select", f"{DEVICE_ID}_mode-1_mode")
    climate = _entity_id(hass, "climate", f"{DEVICE_ID}_thermo-1_thermostat")
    assert hass.states.get(door).state == "on"
    assert hass.states.get(mode).state == "Low"
    assert hass.states.get(climate).state == "cool"

    unique_ids = [item.unique_id for item in er.async_get(hass).entities.values()]
    assert not any("barcode-1" in unique_id for unique_id in unique_ids)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    encoded = json.dumps(diagnostics)
    assert "SECRET-SERIAL" not in encoded
    assert "aa:bb:cc:dd:ee:ff" not in encoded
    assert "access-token" not in encoded
    assert diagnostics["devices"][0]["nickname"] == "Kitchen oven"
