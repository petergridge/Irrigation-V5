"""Support for RESTful API."""
import logging

import httpx

from homeassistant.helpers.httpx_client import get_async_client

DEFAULT_TIMEOUT = 15

_LOGGER = logging.getLogger(__name__)

class RestData:
    """Class for handling the data retrieval."""

    def __init__(self):
        """Initialize the data object."""
        self._hass = None
        self._resource = None
        self._timeout = None
        self._verify_ssl = True
        self._async_client = None
        self.data = None
        self.last_exception = None

    async def set_resource(self, hass, url, timeout=DEFAULT_TIMEOUT):
        """Set url."""
        self._hass     = hass
        self._resource = url
        self._timeout  = timeout

    async def async_update(self, log_errors=True):
        """Get the latest data from REST service with provided method."""
        if not self._async_client:
            self._async_client = get_async_client(
                self._hass, verify_ssl=self._verify_ssl
            )

        _LOGGER.debug("Updating from %s", self._resource)
        try:
            response = await self._async_client.request(
                "GET",
                self._resource,
                headers=None,
                params=None,
                auth=None,
                data=None,
                timeout=self._timeout,
            )
            self.data = response.text
        except httpx.RequestError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching data: %s failed with %s", self._resource, ex
                )
            self.last_exception = ex
            self.data = None
