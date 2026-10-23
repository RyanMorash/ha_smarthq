"""Data update coordinator and SmartHQ event stream."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pysmarthq.errors import SmartHQAuthError, SmartHQError
from pysmarthq.models import Device, Service

from .const import (
    DEVICE_DETAIL_CONCURRENCY,
    DOMAIN,
    KNOWN_SERVICE_TYPES,
    LOGGER,
    RECONCILE_INTERVAL,
    SOCKET_REFRESH_LEEWAY_SECONDS,
    STREAM_BACKOFF_MAX_SECONDS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pysmarthq import EventStream, SmartHQApi

    from .data import SmartHQConfigEntry


class SmartHQDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """
    Devices for one SmartHQ account.

    The WebSocket stream is the update path. The interval re-reads device
    details in case a push was missed.
    """

    config_entry: SmartHQConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SmartHQConfigEntry,
        api: SmartHQApi,
        stream: EventStream,
    ) -> None:
        """Store the API client and the event stream."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=RECONCILE_INTERVAL,
            config_entry=config_entry,
        )
        self.api = api
        self.stream = stream
        self._stream_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> dict[str, Device]:
        """Load every device, including the services omitted from the list."""
        try:
            listed = await self.api.async_get_all_devices()
            details, failed_ids = await self._async_device_details(listed)
        except SmartHQAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except SmartHQError as err:
            raise UpdateFailed(str(err)) from err
        self._keep_cached_devices(details, failed_ids)
        if not details and failed_ids:
            message = "SmartHQ device details failed"
            raise UpdateFailed(message)
        self._reload_if_devices_added(details)
        self._log_unknown(details)
        return details

    @callback
    def _async_refresh_finished(self) -> None:
        """Keep reconciliation scheduled when no entity is listening yet."""
        if self._shutdown_requested:
            return
        if self._unsub_refresh is None:
            self._schedule_refresh()

    async def _async_device_details(
        self, listed: list[Device]
    ) -> tuple[dict[str, Device], set[str]]:
        """Fetch device details a few at a time."""
        semaphore = asyncio.Semaphore(DEVICE_DETAIL_CONCURRENCY)
        device_ids = [
            device.deviceId
            for device in listed
            if isinstance(device.deviceId, str) and device.deviceId
        ]

        async def _load(device_id: str) -> Device:
            async with semaphore:
                return await self.api.async_get_device(device_id)

        results = await asyncio.gather(
            *(_load(device_id) for device_id in device_ids), return_exceptions=True
        )
        devices: dict[str, Device] = {}
        failed_ids: set[str] = set()
        for device_id, result in zip(device_ids, results, strict=True):
            if isinstance(result, SmartHQAuthError):
                raise result
            if isinstance(result, Exception):
                failed_ids.add(device_id)
                LOGGER.debug("SmartHQ device detail failed: %s", result)
                continue
            if isinstance(result.deviceId, str):
                devices[result.deviceId] = result
        return devices, failed_ids

    def _keep_cached_devices(
        self, details: dict[str, Device], failed_ids: set[str]
    ) -> None:
        """Keep the last good detail when a later fetch fails."""
        previous = self.data or {}
        for device_id in failed_ids:
            cached = previous.get(device_id)
            if cached is None:
                continue
            details[device_id] = cached

    def _reload_if_devices_added(self, details: dict[str, Device]) -> None:
        """Reload so platforms create entities for appliances that appeared."""
        previous = self.data
        # None means this is the first refresh, before platforms set up. An
        # empty dict is a finished setup that discovered no appliances.
        if previous is None:
            return
        added = set(details) - set(previous)
        if not added:
            return
        LOGGER.debug("Reloading SmartHQ for new devices: %s", ", ".join(sorted(added)))
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    def _log_unknown(self, devices: dict[str, Device]) -> None:
        """Log service types this integration does not turn into entities."""
        for device in devices.values():
            for service in device.services or []:
                if service.serviceType not in KNOWN_SERVICE_TYPES:
                    LOGGER.debug("Ignoring unsupported service %s", service.serviceType)

    def async_start_stream(self) -> None:
        """Start the background event stream."""
        if self._stream_task is not None:
            return
        self._stream_task = self.config_entry.async_create_background_task(
            self.hass,
            self._stream_loop(),
            name="SmartHQ event stream",
        )

    async def async_stop_stream(self) -> None:
        """Cancel the event stream and close its socket."""
        task = self._stream_task
        self._stream_task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self.stream.async_close()

    async def async_send_command(
        self, service: Service, command_type: str, **fields: Any
    ) -> None:
        """Send one service command and surface failure to the caller."""
        command = {
            "commandType": command_type,
            **{key: value for key, value in fields.items() if value is not None},
        }
        try:
            await service.async_send_command(command)
        except SmartHQAuthError as err:
            self.hass.config_entries.async_start_reauth(self.config_entry)
            message = "SmartHQ authentication expired"
            raise HomeAssistantError(message) from err
        except SmartHQError as err:
            raise HomeAssistantError(str(err)) from err

    async def _stream_loop(self) -> None:
        """Connect, apply events, and reconnect until the entry is unloaded."""
        try:
            await self._consume_stream()
        finally:
            await self.stream.async_close()

    async def _consume_stream(self) -> None:
        """Reconnect with backoff until auth fails or the task is cancelled."""
        backoff = 1
        while True:
            try:
                await self.stream.async_connect()
                await self.stream.async_configure_account(
                    pubsub=True,
                    services=True,
                    presence=True,
                    alerts=True,
                    commands=True,
                )
                backoff = 1
                await self._consume_until_expiry()
            except asyncio.CancelledError:
                raise
            except SmartHQAuthError:
                LOGGER.debug("SmartHQ authentication failed on the event stream")
                self.hass.config_entries.async_start_reauth(self.config_entry)
                return
            except SmartHQError as err:
                LOGGER.debug("SmartHQ event stream disconnected: %s", err)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, STREAM_BACKOFF_MAX_SECONDS)

    async def _consume_until_expiry(self) -> None:
        """Read events until the socket is due to be refreshed."""
        expiry: asyncio.Task[None] | None = None
        expires_at = self.stream.socket_expires_at
        if expires_at is not None:
            delay = max(0.0, expires_at - time.time() - SOCKET_REFRESH_LEEWAY_SECONDS)
            expiry = asyncio.create_task(self._close_when_due(delay))
        try:
            async for event in self.stream:
                self._handle_event(event)
        finally:
            if expiry is not None:
                expiry.cancel()
                with suppress(asyncio.CancelledError):
                    await expiry

    async def _close_when_due(self, delay: float) -> None:
        """Close the socket so the next loop fetches a new WebSocket URL."""
        await asyncio.sleep(delay)
        await self.stream.async_close()

    def _handle_event(self, event: Any) -> None:
        """Apply one stream event to the cached devices."""
        kind = getattr(event, "kind", None)
        raw = getattr(event, "raw_data", {})
        if not isinstance(raw, dict):
            raw = {}
        device_id = getattr(event, "deviceId", None) or raw.get("deviceId")
        if kind == "pubsub#device":
            self._handle_device_event(event, device_id, raw)
            return
        if kind == "pubsub#alert":
            self.hass.bus.async_fire(
                "smarthq_alert",
                {
                    "alert_id": raw.get("alertId"),
                    "alert_type": raw.get("alertType"),
                    "clear": raw.get("clear"),
                    "device_id": device_id,
                },
            )
        if kind not in {"pubsub#service", "pubsub#presence", "pubsub#alert"}:
            return
        if not isinstance(device_id, str):
            return
        device = self.data.get(device_id)
        if device is None:
            return
        device.apply_event(event)
        self._publish_stream_update()

    def _publish_stream_update(self) -> None:
        """
        Notify entities without postponing reconciliation.

        ``async_set_updated_data`` cancels the scheduled refresh and starts the
        interval over. Events can arrive continuously, which would keep the
        30-minute reconcile from running while the socket stays busy.

        A failed reconcile clears ``last_update_success``. The stream is still
        applying live state, so entities become available again without waiting
        for the next successful device fetch.
        """
        self.last_update_success = True
        self.async_update_listeners()

    def _handle_device_event(
        self, event: Any, device_id: str | None, raw: dict[str, Any]
    ) -> None:
        """Reload when an appliance is commissioned or removed."""
        change = getattr(event, "event", None) or raw.get("event")
        if change in {"created", "removed"}:
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            return
        if not isinstance(device_id, str):
            return
        device = self.data.get(device_id)
        if device is None:
            return
        device.apply_event(event)
        self._publish_stream_update()
