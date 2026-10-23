"""Shared fakes for SmartHQ tests."""

from __future__ import annotations

import asyncio
import time
from typing import Any, ClassVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from pysmarthq.errors import SmartHQError, SmartHQStreamClosed
from pysmarthq.models import Device
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smarthq.auth import SmartHQOAuth2Implementation
from custom_components.smarthq.const import AUTHORIZE_URL, DOMAIN, TOKEN_URL

USER_ID = "user-1"
DEVICE_ID = "device-1"


def token(
    *, access: str = "access-token", refresh: str = "refresh-token"
) -> dict[str, Any]:
    """Return a token that is not yet expired."""
    return {
        "access_token": access,
        "expires_at": time.time() + 3600,
        "expires_in": 3600,
        "refresh_token": refresh,
        "token_type": "Bearer",
    }


def register_implementation(hass: HomeAssistant) -> SmartHQOAuth2Implementation:
    """Register the local SmartHQ OAuth implementation."""
    implementation = SmartHQOAuth2Implementation(
        hass,
        DOMAIN,
        "client-id",
        "client-secret",
        AUTHORIZE_URL,
        TOKEN_URL,
    )
    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, implementation)
    return implementation


def mock_config_entry(**data: Any) -> MockConfigEntry:
    """Return a config entry for the test account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_ID,
        data={"auth_implementation": DOMAIN, "token": token(), **data},
        version=1,
    )


class FakeApi:
    """SmartHQ API that serves fixtures and records calls."""

    devices: ClassVar[list[dict[str, Any]]] = []
    details: ClassVar[dict[str, dict[str, Any]]] = {}
    detail_errors: ClassVar[dict[str, Exception]] = {}
    calls = 0
    error: Exception | None = None

    def __init__(self, auth: Any) -> None:
        """Store the auth object passed by the integration."""
        self.auth = auth

    @classmethod
    def reset(cls, devices: list[dict[str, Any]]) -> None:
        """Replace the fixtures served by the next client."""
        cls.devices = devices
        cls.details = {device["deviceId"]: device for device in devices}
        cls.detail_errors = {}
        cls.calls = 0
        cls.error = None

    async def async_get_all_devices(self, **_kwargs: Any) -> list[Device]:
        """Return the listed devices, without their services."""
        self._raise()
        FakeApi.calls += 1
        return [
            Device({"deviceId": device["deviceId"]}, self.auth)
            for device in self.devices
        ]

    async def async_get_device(self, device_id: str) -> Device:
        """Return one device detail payload."""
        self._raise()
        FakeApi.calls += 1
        error = FakeApi.detail_errors.get(device_id)
        if error is not None:
            raise error
        return Device(self.details[device_id], self.auth)

    def _raise(self) -> None:
        """Raise the configured API error."""
        if self.error is not None:
            raise self.error


class FakeStream:
    """Event stream that queues events injected by a test."""

    instances: ClassVar[list[FakeStream]] = []

    def __init__(self, auth: Any, *, idle_ping_seconds: float | None = None) -> None:
        """Store auth and an empty event queue."""
        self.auth = auth
        self.idle_ping_seconds = idle_ping_seconds
        self.socket_expires_at: float | None = None
        self.configured: dict[str, Any] | None = None
        self.closed = False
        self.connects = 0
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        FakeStream.instances.append(self)

    @classmethod
    def reset(cls) -> None:
        """Forget streams created by earlier tests."""
        cls.instances = []

    async def async_connect(self) -> None:
        """Record a connection. No socket is opened."""
        self.connects += 1
        self.closed = False

    async def async_configure_account(self, **kwargs: Any) -> None:
        """Record the account subscription."""
        self.configured = kwargs

    async def async_close(self) -> None:
        """Mark the stream closed."""
        self.closed = True

    def __aiter__(self) -> FakeStream:
        """Return this stream as the async iterator."""
        return self

    async def __anext__(self) -> Any:
        """Return the next injected event."""
        if self.closed:
            message = "closed"
            raise SmartHQStreamClosed(message)
        return await self.queue.get()


class FlowApi:
    """API used by the config flow to read the user id."""

    user_id: str | None = USER_ID
    error: Exception | None = None

    def __init__(self, auth: Any) -> None:
        """Store auth. The flow only asks for the device list."""
        self.auth = auth

    async def async_get_devices(self) -> Any:
        """Return an object with the configured user id."""
        if self.error is not None:
            raise self.error
        return _DeviceList(self.user_id)


class _DeviceList:
    """Minimal device-list response."""

    def __init__(self, user_id: str | None) -> None:
        self.userId = user_id


def raise_api(error: Exception) -> None:
    """Make the next setup fail inside the API client."""
    FakeApi.error = error
    if not isinstance(error, SmartHQError):
        message = "expected a SmartHQ error"
        raise TypeError(message)
