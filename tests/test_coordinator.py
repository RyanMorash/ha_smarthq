"""Coordinator reconcile and stream update tests."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pysmarthq.errors import SmartHQError
from pysmarthq.events import ServiceEvent

from custom_components.smarthq.const import DOMAIN

from .common import (
    DEVICE_ID,
    FakeApi,
    FakeStream,
    mock_config_entry,
    register_implementation,
)

OTHER_DEVICE_ID = "device-2"
TEMPERATURE = "cloud.smarthq.service.temperature"


def _device(device_id: str, nickname: str) -> dict:
    """Return an appliance with one temperature service."""
    return {
        "brand": "GE",
        "deviceId": device_id,
        "deviceType": "cloud.smarthq.device.oven",
        "nickname": nickname,
        "presence": "ONLINE",
        "services": [
            {
                "domainType": "cloud.smarthq.domain.temperature",
                "serviceId": "temp-1",
                "serviceType": TEMPERATURE,
                "state": {"celsius": 21, "fahrenheit": 70},
            }
        ],
    }


def _entity_id(hass: HomeAssistant, unique_id: str) -> str | None:
    """Return the entity id for a unique id, if it was created."""
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)


async def test_stream_event_does_not_postpone_reconcile(hass: HomeAssistant) -> None:
    """A push updates entities and leaves the reconcile timer where it was."""
    FakeApi.reset([_device(DEVICE_ID, "Oven")])
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
        coordinator = entry.runtime_data.coordinator
        scheduled = coordinator._unsub_refresh
        assert scheduled is not None

        await FakeStream.instances[-1].queue.put(
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
        await hass.async_block_till_done()

    entity_id = _entity_id(hass, f"{DEVICE_ID}_temp-1_temperature")
    assert entity_id is not None
    assert float(hass.states.get(entity_id).state) == 82
    assert coordinator._unsub_refresh is scheduled


async def test_failed_detail_is_added_after_the_next_reconcile(
    hass: HomeAssistant,
) -> None:
    """An appliance missing from the first detail fetch appears after it succeeds."""
    FakeApi.reset([_device(DEVICE_ID, "Oven"), _device(OTHER_DEVICE_ID, "Fridge")])
    FakeApi.detail_errors[OTHER_DEVICE_ID] = SmartHQError("detail down")
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
        assert _entity_id(hass, f"{DEVICE_ID}_temp-1_temperature") is not None
        assert _entity_id(hass, f"{OTHER_DEVICE_ID}_temp-1_temperature") is None

        FakeApi.detail_errors.clear()
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

    assert _entity_id(hass, f"{OTHER_DEVICE_ID}_temp-1_temperature") is not None


async def test_later_detail_failure_keeps_the_cached_device(
    hass: HomeAssistant,
) -> None:
    """A failed reconcile keeps the appliance that was already loaded."""
    FakeApi.reset([_device(DEVICE_ID, "Oven")])
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
        streams = len(FakeStream.instances)
        FakeApi.detail_errors[DEVICE_ID] = SmartHQError("later")
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

    entity_id = _entity_id(hass, f"{DEVICE_ID}_temp-1_temperature")
    assert entity_id is not None
    assert float(hass.states.get(entity_id).state) == 21
    assert len(FakeStream.instances) == streams
    assert DEVICE_ID in entry.runtime_data.coordinator.data


async def test_appliances_found_after_an_empty_setup_are_added(
    hass: HomeAssistant,
) -> None:
    """A reconcile after an empty setup creates entities for the new appliances."""
    FakeApi.reset([])
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
        assert _entity_id(hass, f"{DEVICE_ID}_temp-1_temperature") is None
        assert entry.runtime_data.coordinator.data == {}
        assert entry.runtime_data.coordinator._unsub_refresh is not None

        device = _device(DEVICE_ID, "Oven")
        FakeApi.devices = [device]
        FakeApi.details = {DEVICE_ID: device}
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

    assert _entity_id(hass, f"{DEVICE_ID}_temp-1_temperature") is not None


async def test_stream_event_restores_availability_after_failed_reconcile(
    hass: HomeAssistant,
) -> None:
    """A push makes entities available again without restarting reconciliation."""
    FakeApi.reset([_device(DEVICE_ID, "Oven")])
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
        coordinator = entry.runtime_data.coordinator
        FakeApi.error = SmartHQError("down")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        entity_id = _entity_id(hass, f"{DEVICE_ID}_temp-1_temperature")
        assert entity_id is not None
        assert hass.states.get(entity_id).state == "unavailable"
        assert coordinator.last_update_success is False
        scheduled = coordinator._unsub_refresh
        assert scheduled is not None

        await FakeStream.instances[-1].queue.put(
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
        await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert coordinator._unsub_refresh is scheduled
    assert float(hass.states.get(entity_id).state) == 82
