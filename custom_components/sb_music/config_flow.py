from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_HOST, CONF_EMAIL, CONF_PASSWORD, CONF_DEVICE_ID

import logging

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    host = data[CONF_HOST].rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host

    import requests

    try:
        resp = await hass.async_add_executor_job(
            lambda: requests.post(
                f"{host}/api/auth/token",
                json={"email": data[CONF_EMAIL], "password": data[CONF_PASSWORD]},
                timeout=10,
            )
        )
    except requests.exceptions.ConnectionError:
        raise CannotConnect("Cannot connect to server")
    except requests.exceptions.Timeout:
        raise CannotConnect("Connection timed out")

    if resp.status_code == 401:
        raise InvalidAuth("Invalid credentials")
    if resp.status_code == 403:
        raise InvalidAuth("Email not confirmed")
    if resp.status_code != 200:
        raise CannotConnect(f"Server returned {resp.status_code}")

    info = resp.json()
    token = info.get("token")

    try:
        dev_resp = await hass.async_add_executor_job(
            lambda: requests.get(
                f"{host}/api/devices",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
        )
    except requests.exceptions.RequestException:
        raise CannotConnect("Failed to list devices")

    devices = dev_resp.json() if dev_resp.status_code == 200 else []

    return {
        "title": f"SB'Music ({data[CONF_EMAIL]})",
        "host": host,
        "token": token,
        "devices": devices,
    }


class SBMusicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._host = None
        self._email = None
        self._password = None
        self._token = None
        self._devices = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._host = info["host"]
                self._email = user_input[CONF_EMAIL]
                self._password = user_input[CONF_PASSWORD]
                self._token = info["token"]
                self._devices = info["devices"]

                if not self._devices:
                    return self.async_create_entry(
                        title=info["title"],
                        data={
                            CONF_HOST: self._host,
                            CONF_EMAIL: self._email,
                            CONF_PASSWORD: self._password,
                            CONF_DEVICE_ID: None,
                        },
                    )

                return await self.async_step_device()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            device_id = user_input.get(CONF_DEVICE_ID)
            return self.async_create_entry(
                title=f"SB'Music ({self._email})",
                data={
                    CONF_HOST: self._host,
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_DEVICE_ID: device_id,
                },
            )

        devices = self._devices
        if not devices:
            return self.async_create_entry(
                title=f"SB'Music ({self._email})",
                data={
                    CONF_HOST: self._host,
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_DEVICE_ID: None,
                },
            )

        options = {
            dev["deviceId"]: f"{dev['name']} ({dev['kind']})"
            for dev in devices
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): vol.In(options),
            }
        )

        return self.async_show_form(
            step_id="device",
            data_schema=schema,
            description_placeholders={"devices": str(len(devices))},
        )


class CannotConnect(HomeAssistantError):
    pass


class InvalidAuth(HomeAssistantError):
    pass
