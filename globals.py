"""Global Variable."""

import json

import logging

PROGRAMS = {}
ZONES = {}
QUEUEDPROGRAMS = []
RUNNINGPROGRAM = False
CURRENTSTATE = {}

_LOGGER = logging.getLogger(__name__)

# Program: Running, Queued, Paused, Stopped
# Zones: Running, Paused, Stopped
# progrma status as json object with program name, status, and list of zones with their status
#
# Programs: {
#   "program_name": {
#     "status": "Running",
#     "zones": {
#       "zone_name": "Running"
#     }
#   }
# }
#


def _program_status(program) -> str:
    """Return the human readable program status."""
    if getattr(program, "_paused", False):
        return "Paused"
    if getattr(program, "_state", False):
        return "Running"
    if program in QUEUEDPROGRAMS:
        return "Queued"
    return "Stopped"


def _zone_status(zone) -> str:
    """Return the human readable zone status."""
    status = getattr(zone, "_status", None)
    if status is None:
        status = getattr(zone, "status", None)
        if hasattr(status, "state"):
            status = status.state

    if status in {"on", "pending", "eco"}:
        return "Running"
    if status == "paused":
        return "Paused"
    return "Stopped"


def update_current_state() -> dict:
    """Build the program to zone status dictionary used by automations."""
    current_state: dict[str, dict[str, object]] = {}

    for program_name, program in PROGRAMS.items():
        zones: dict[str, str] = {}
        for zone_key, zone in ZONES.items():
            if getattr(zone, "_programdata", None).name is program_name:
                zone_name = (
                    zone_key.split(".", 1)[-1]
                    if "." in zone_key
                    else getattr(zone, "_name", zone_key)
                )
                zones[zone_name] = _zone_status(zone)

        current_state[program_name] = {
            "status": _program_status(program),
            "zones": zones,
        }

    CURRENTSTATE.clear()
    CURRENTSTATE.update(current_state)
    return CURRENTSTATE


def current_state_json() -> str:
    """Return the current state as a JSON string."""
    return json.dumps(update_current_state(), indent=2)
