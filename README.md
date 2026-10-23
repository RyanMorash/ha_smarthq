# SmartHQ for Home Assistant

Custom integration for GE Appliances, Café, Profile, and other SmartHQ appliances. It uses the SmartHQ v2 Digital Twin API through [`pysmarthq`](https://github.com/RyanMorash/pysmarthq) and creates entities from each appliance's services. Device type strings are not used to decide which entities exist.

This integration uses the domain `smarthq`. It cannot be installed beside the [official GE Appliances integration](https://github.com/geappliances/geappliances-smarthq-integration), which uses the same domain.

## Install

### HACS

1. In HACS, choose **Custom repositories** and add `https://github.com/RyanMorash/ha_smarthq` as an integration.
2. Install **SmartHQ** and restart Home Assistant.

### Manual

Copy `custom_components/smarthq` into `<config>/custom_components/smarthq` and restart Home Assistant.

## Application credentials

SmartHQ uses OAuth with an application you create. Home Assistant stores the client ID and secret as application credentials. The login does not use PKCE, and the authorize request asks for offline access so a refresh token is issued.

1. Open the [SmartHQ Developer Portal](https://developer.smarthq.com/) and create an application.
2. Set the OAuth callback URL to `https://my.home-assistant.io/redirect/oauth`.
3. In Home Assistant, open **Settings → Devices & services → Application credentials** and add a credential for SmartHQ using that client ID and secret.
4. Add the SmartHQ integration and sign in. One config entry is created per SmartHQ user id. Signing in with an account that is already configured aborts the flow.

If the stored refresh token is rejected, Home Assistant starts a reauthentication flow for that entry.

## What it creates

Each appliance is one device. Entities come from the services on that device:

| Service | Entity |
| --- | --- |
| Read-only temperature, integer, double, meter, environmental sensor, string, cycle timer, stopwatch | Sensor |
| Firmware version | Diagnostic sensor |
| Presence, door, filter attention | Binary sensor |
| Toggle, or a mode whose only values are a binary pair | Switch |
| Other writable modes, including one cook-mode select per cooking cavity | Select |
| Writable temperature, integer, double, and supported cooking parameters | Number |
| Trigger, firmware upgrade, and start, stop, pause, or resume commands | Button |
| `thermostat.v1` | Climate |
| `waterheater.v1` | Water heater |

A coffee brewer with listed choices and commands becomes a select and a brew button. Without those, it is a status sensor.

Alerts are published on the Home Assistant event bus as `smarthq_alert`. The integration does not create persistent notifications.

Updates arrive on the SmartHQ WebSocket. A reconciliation runs every 30 minutes in case a push was missed.

## v2 API limits

The v2 API does not expose every feature of every appliance. Oven cooking controls, and some Fisher & Paykel or Haier models, may only publish the common services (temperature, mode, toggle, and similar). Services this integration does not recognize are ignored.

Settings-notification switches, demand response, time-of-use, favorites, history metrics, and batch commands are not implemented.

## Development

```bash
python3 -m pip install -r requirements_dev.txt
scripts/lint
python3 -m pytest
```

`scripts/develop` starts a Home Assistant instance with the included `config/configuration.yaml`.
