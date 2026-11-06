"""Constants of the Heating Circuit Advisor."""

import logging
from datetime import timedelta

DOMAIN = "heating_circuit_advisor"
LOGGER = logging.getLogger(__package__)

CONF_CIRCUIT = "circuit"
CONF_OUTDOOR = "outdoor_temperature"
CONF_AREAS = "areas"
CONF_LABEL = "loop_label"
CONF_OUTDOOR_LIMIT = "outdoor_limit"
CONF_WINDOW_HOURS = "window_hours"
CONF_LOW_SHARE = "low_share"
CONF_HIGH_SHARE = "high_share"

DEFAULT_OUTDOOR_LIMIT = 15.0
DEFAULT_WINDOW_HOURS = 24.0
DEFAULT_LOW_SHARE = 15.0
DEFAULT_HIGH_SHARE = 70.0

# Every 4 minutes: 15 samples an hour spread over every minute of a 15-minute valve cycle, so that
# time-proportioned valves (Homematic IP switching actuators: 15-minute PWM) are not always sampled at one phase
SAMPLE_INTERVAL = timedelta(minutes=4)

STORAGE_VERSION = 1
# The memory is written a minute after a sample at most, and when Home Assistant stops
SAVE_DELAY = 60
