"""Diagnostics support for AccuWeather."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    if config_entry.options != {}:
        config = config_entry.options
    else:
        config = config_entry.data



    return {
        "irrigation_config": async_redact_data(config,()),
        "irrigation_data": async_redact_data(config_entry.runtime_data,()),
    }
