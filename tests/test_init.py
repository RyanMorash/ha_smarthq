"""Setup and unload tests for SmartHQ."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pysmarthq.errors import SmartHQAuthError, SmartHQError

from custom_components.smarthq.const import DOMAIN

from .common import (
    DEVICE_ID,
    FakeApi,
    FakeStream,
    mock_config_entry,
    register_implementation,
)


def _device() -> dict:
    """Return one online appliance with a read-only temperature."""
    return {
        "brand": "GE",
        "deviceId": DEVICE_ID,
        "deviceType": "cloud.smarthq.device.oven",
        "nickname": "Kitchen oven",
        "presence": "ONLINE",
        "services": [
            {
                "config": {},
                "domainType": "cloud.smarthq.domain.temperature",
                "serviceId": "temp-1",
                "serviceType": "cloud.smarthq.service.temperature",
                "state": {"celsius": 21, "fahrenheit": 70},
            }
        ],
    }


async def _setup(hass: HomeAssistant, *, error: Exception | None = None):
    """Set up one config entry against the fake API and stream."""
    FakeApi.reset([_device()])
    FakeApi.error = error
    FakeStream.reset()
    register_implementation(hass)
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch("custom_components.smarthq.SmartHQApi", FakeApi),
        patch("custom_components.smarthq.EventStream", FakeStream),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_auth_failure_starts_reauth(hass: HomeAssistant) -> None:
    """An authentication error during setup does not retry the entry."""
    entry = await _setup(hass, error=SmartHQAuthError("rejected"))
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_connection_failure_retries(hass: HomeAssistant) -> None:
    """A connection error during setup leaves the entry ready to retry."""
    entry = await _setup(hass, error=SmartHQError("down"))
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_cancels_the_stream(hass: HomeAssistant) -> None:
    """Unloading the entry closes the event stream."""
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert FakeStream.instances
    stream = FakeStream.instances[-1]
    assert stream.connects == 1
    assert stream.configured == {
        "alerts": True,
        "commands": True,
        "presence": True,
        "pubsub": True,
        "services": True,
    }
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert stream.closed
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
