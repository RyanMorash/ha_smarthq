"""Constants for the SmartHQ integration."""

from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger

from pysmarthq.const import IAM_HOST

LOGGER: Logger = getLogger(__package__)

DOMAIN = "smarthq"
MANUFACTURER = "GE Appliances"
DEFAULT_NAME = "SmartHQ"

AUTHORIZE_URL = f"{IAM_HOST}/oauth2/auth"
TOKEN_URL = f"{IAM_HOST}/oauth2/token"

RECONCILE_INTERVAL = timedelta(minutes=30)
SOCKET_REFRESH_LEEWAY_SECONDS = 60
STREAM_BACKOFF_MAX_SECONDS = 60
DEVICE_DETAIL_CONCURRENCY = 4

PRESENCE_ONLINE = "ONLINE"
PRESENCE_OFFLINE = "OFFLINE"

SERVICE_BATTERY = "cloud.smarthq.service.battery"
SERVICE_BREW_MODE = "cloud.smarthq.service.brew.mode.v1"
SERVICE_COFFEE_V1 = "cloud.smarthq.service.coffeebrewer.v1"
SERVICE_COFFEE_V2 = "cloud.smarthq.service.coffeebrewer.v2"
SERVICE_COOKING_MODE = "cloud.smarthq.service.cooking.mode.v1"
SERVICE_COOKING_STATE = "cloud.smarthq.service.cooking.state.v1"
SERVICE_CYCLE_TIMER = "cloud.smarthq.service.cycletimer"
SERVICE_DISHWASHER_MODE = "cloud.smarthq.service.dishwasher.mode.v1"
SERVICE_DISHWASHER_STATE = "cloud.smarthq.service.dishwasher.state.v1"
SERVICE_DOOR = "cloud.smarthq.service.door"
SERVICE_DOUBLE = "cloud.smarthq.service.double"
SERVICE_ENVIRONMENTAL = "cloud.smarthq.service.environmental.sensor"
SERVICE_FILTER = "cloud.smarthq.service.filter.v1"
SERVICE_FIRMWARE = "cloud.smarthq.service.firmware.v1"
SERVICE_INTEGER = "cloud.smarthq.service.integer"
SERVICE_LAUNDRY_MODE = "cloud.smarthq.service.laundry.mode.v1"
SERVICE_LAUNDRY_STATE = "cloud.smarthq.service.laundry.state.v1"
SERVICE_LAUNDRY_TOGGLE = "cloud.smarthq.service.laundry.toggle.v2"
SERVICE_METER = "cloud.smarthq.service.meter"
SERVICE_MODE = "cloud.smarthq.service.mode"
SERVICE_STOPWATCH = "cloud.smarthq.service.stopwatch"
SERVICE_STRING = "cloud.smarthq.service.string"
SERVICE_TEMPERATURE = "cloud.smarthq.service.temperature"
SERVICE_THERMOSTAT = "cloud.smarthq.service.thermostat.v1"
SERVICE_TOGGLE = "cloud.smarthq.service.toggle"
SERVICE_TRIGGER = "cloud.smarthq.service.trigger"
SERVICE_WATER_HEATER = "cloud.smarthq.service.waterheater.v1"

COMMAND_BREW_RESET = "cloud.smarthq.command.brew.mode.v1.reset"
COMMAND_BREW_SET = "cloud.smarthq.command.brew.mode.v1.set"
COMMAND_COFFEE_V1_START = "cloud.smarthq.command.coffeebrewer.v1.start"
COMMAND_COFFEE_V1_STOP = "cloud.smarthq.command.coffeebrewer.v1.stop"
COMMAND_COFFEE_V2_SET = "cloud.smarthq.command.coffeebrewer.v2.set"
COMMAND_COFFEE_V2_START = "cloud.smarthq.command.coffeebrewer.v2.start"
COMMAND_COFFEE_V2_STOP = "cloud.smarthq.command.coffeebrewer.v2.stop"
COMMAND_COOKING_MODE_SET = "cloud.smarthq.command.cooking.mode.v1.set"
COMMAND_COOKING_MODE_START = "cloud.smarthq.command.cooking.mode.v1.start"
COMMAND_COOKING_PAUSE = "cloud.smarthq.command.cooking.state.v1.pause"
COMMAND_COOKING_RESTORE = "cloud.smarthq.command.cooking.mode.v1.default.restore"
COMMAND_COOKING_RESUME = "cloud.smarthq.command.cooking.state.v1.resume"
COMMAND_COOKING_STOP = "cloud.smarthq.command.cooking.state.v1.stop"
COMMAND_DISHWASHER_PAUSE = "cloud.smarthq.command.dishwasher.state.v1.pause"
COMMAND_DISHWASHER_SET = "cloud.smarthq.command.dishwasher.mode.v1.set"
COMMAND_DISHWASHER_START = "cloud.smarthq.command.dishwasher.state.v1.start"
COMMAND_DISHWASHER_STOP = "cloud.smarthq.command.dishwasher.state.v1.stop"
COMMAND_DOUBLE_SET = "cloud.smarthq.command.double.set"
COMMAND_FILTER_SET = "cloud.smarthq.command.filter.v1.set"
COMMAND_FIRMWARE_UPGRADE = "cloud.smarthq.command.firmware.v1.upgrade"
COMMAND_INTEGER_SET = "cloud.smarthq.command.integer.set"
COMMAND_LAUNDRY_SET = "cloud.smarthq.command.laundry.mode.v1.set"
COMMAND_LAUNDRY_TOGGLE_SET = "cloud.smarthq.command.laundry.toggle.v2.set"
COMMAND_MODE_SET = "cloud.smarthq.command.mode.set"
COMMAND_STOPWATCH_PAUSE = "cloud.smarthq.command.stopwatch.pause"
COMMAND_STOPWATCH_RESET = "cloud.smarthq.command.stopwatch.reset"
COMMAND_STOPWATCH_START = "cloud.smarthq.command.stopwatch.start"
COMMAND_TEMPERATURE_SET = "cloud.smarthq.command.temperature.set"
COMMAND_THERMOSTAT_SET = "cloud.smarthq.command.thermostat.v1.set"
COMMAND_TOGGLE_SET = "cloud.smarthq.command.toggle.set"
COMMAND_TRIGGER = "cloud.smarthq.command.trigger.do"
COMMAND_WATER_HEATER_SET = "cloud.smarthq.command.waterheater.v1.set"

PARAMETER_SUPPORTED = frozenset(
    {
        "cloud.smarthq.type.parameter.required",
        "cloud.smarthq.type.parameter.optional",
        "cloud.smarthq.type.parameter.defaulted",
    }
)

# Last path segment of a binary mode pair. The first set is the on value.
BINARY_MODE_ON = frozenset({"on", "true", "unlocked", "enabled", "active"})
BINARY_MODE_OFF = frozenset({"off", "false", "locked", "disabled", "inactive"})

COMPONENT_LABELS: dict[str, str] = {
    "cavity": "Cavity",
    "dispenser": "Dispenser",
    "door": "Door",
    "drawer": "Drawer",
    "freezer": "Freezer",
    "freshfood": "Fresh food",
    "hotwater": "Hot water",
    "icedispenser": "Ice dispenser",
    "icemaker": "Ice maker",
    "icemaker0": "Ice maker",
    "icemaker1": "Ice maker 2",
    "pantry": "Pantry",
    "probe": "Probe",
}

WATER_HEATER_MODES = (
    "cloud.smarthq.type.waterheatermode.electric",
    "cloud.smarthq.type.waterheatermode.eheat",
    "cloud.smarthq.type.waterheatermode.hybrid",
    "cloud.smarthq.type.waterheatermode.highdemand",
    "cloud.smarthq.type.waterheatermode.vacation",
)

THERMOSTAT_MODES = {
    "cloud.smarthq.type.thermostatmode.auto": "auto",
    "cloud.smarthq.type.thermostatmode.auto.twotemperature": "heat_cool",
    "cloud.smarthq.type.thermostatmode.cool": "cool",
    "cloud.smarthq.type.thermostatmode.cool.energysaver": "cool",
    "cloud.smarthq.type.thermostatmode.cool.quiet": "cool",
    "cloud.smarthq.type.thermostatmode.cool.turbo": "cool",
    "cloud.smarthq.type.thermostatmode.dry": "dry",
    "cloud.smarthq.type.thermostatmode.fanonly": "fan_only",
    "cloud.smarthq.type.thermostatmode.heat": "heat",
    "cloud.smarthq.type.thermostatmode.off": "off",
}

THERMOSTAT_MODE_BY_HVAC = {
    "auto": "cloud.smarthq.type.thermostatmode.auto",
    "cool": "cloud.smarthq.type.thermostatmode.cool",
    "dry": "cloud.smarthq.type.thermostatmode.dry",
    "fan_only": "cloud.smarthq.type.thermostatmode.fanonly",
    "heat": "cloud.smarthq.type.thermostatmode.heat",
    "heat_cool": "cloud.smarthq.type.thermostatmode.auto.twotemperature",
    "off": "cloud.smarthq.type.thermostatmode.off",
}

FAN_SPEEDS = (
    "cloud.smarthq.type.fanspeed.auto",
    "cloud.smarthq.type.fanspeed.low",
    "cloud.smarthq.type.fanspeed.medium",
    "cloud.smarthq.type.fanspeed.high",
    "cloud.smarthq.type.fanspeed.circulate",
    "cloud.smarthq.type.fanspeed.on",
    "cloud.smarthq.type.fanspeed.off",
)

STATUS_FIELDS = (
    ("cookingStatus", "Cooking status"),
    ("cycle", "Cycle"),
    ("mode", "Mode"),
    ("runStatus", "Run status"),
    ("status", "Status"),
    ("subCycle", "Sub cycle"),
)

DISHWASHER_BOOL_FIELDS = (
    "bottleWash",
    "cycleModifierDryPlus",
    "cycleModifierFast",
    "cycleModifierGentle",
    "cycleModifierIntensive",
    "cycleModifierSanitize",
    "silverwareWash",
    "steam",
)
DISHWASHER_STRING_FIELDS = ("heatedDry", "washTemp", "washZone")
LAUNDRY_STRING_FIELDS = ("laundryDrynessLevel", "laundryTemperature", "stain")
BREW_NUMBER_FIELDS = ("brewTemperature", "grindTime", "volume")
COFFEE_SERVICES = frozenset({SERVICE_COFFEE_V1, SERVICE_COFFEE_V2})

DOOR_FIELDS = (
    "singleOpen",
    "topOpen",
    "bottomOpen",
    "leftOpen",
    "rightOpen",
    "middleOpen",
    "topLeftOpen",
    "topRightOpen",
    "bottomLeftOpen",
    "bottomRightOpen",
    "topRightDoorInDoorOpen",
)

KNOWN_SERVICE_TYPES = frozenset(
    {
        SERVICE_BATTERY,
        SERVICE_BREW_MODE,
        SERVICE_COFFEE_V1,
        SERVICE_COFFEE_V2,
        SERVICE_COOKING_MODE,
        SERVICE_COOKING_STATE,
        SERVICE_CYCLE_TIMER,
        SERVICE_DISHWASHER_MODE,
        SERVICE_DISHWASHER_STATE,
        SERVICE_DOOR,
        SERVICE_DOUBLE,
        SERVICE_ENVIRONMENTAL,
        SERVICE_FILTER,
        SERVICE_FIRMWARE,
        SERVICE_INTEGER,
        SERVICE_LAUNDRY_MODE,
        SERVICE_LAUNDRY_STATE,
        SERVICE_LAUNDRY_TOGGLE,
        SERVICE_METER,
        SERVICE_MODE,
        SERVICE_STOPWATCH,
        SERVICE_STRING,
        SERVICE_TEMPERATURE,
        SERVICE_THERMOSTAT,
        SERVICE_TOGGLE,
        SERVICE_TRIGGER,
        SERVICE_WATER_HEATER,
    }
)

TO_REDACT = {
    "access_token",
    "authorization",
    "client_secret",
    "endpoint",
    "macAddress",
    "refresh_token",
    "serial",
}
