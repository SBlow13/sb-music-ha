from __future__ import annotations

from datetime import timedelta
from typing import Any

import requests

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_DEVICE_ID,
    API_DEVICES,
    API_DEVICE_COMMAND,
    API_LOGIN,
)

import logging

_LOGGER = logging.getLogger(__name__)

SUPPORT_SB_MUSIC = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = SBMusicDataCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([SBMusicMediaPlayer(coordinator, config_entry)])


class SBMusicDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.config_entry = config_entry
        self._token: str | None = None
        self._device_id: str | None = config_entry.data.get(CONF_DEVICE_ID)
        self._device_data: dict[str, Any] | None = None

    @property
    def host(self) -> str:
        return self.config_entry.data[CONF_HOST]

    @property
    def email(self) -> str:
        return self.config_entry.data[CONF_EMAIL]

    @property
    def password(self) -> str:
        return self.config_entry.data[CONF_PASSWORD]

    def _ensure_token(self) -> str | None:
        if self._token:
            return self._token

        try:
            resp = requests.post(
                f"{self.host}{API_LOGIN}",
                json={"email": self.email, "password": self.password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("token")
                return self._token
        except requests.RequestException:
            pass
        return None

    def _api_get(self, path: str) -> tuple[int, Any]:
        token = self._ensure_token()
        if not token:
            return 401, None
        try:
            resp = requests.get(
                f"{self.host}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            return resp.status_code, resp.json() if resp.text else None
        except requests.RequestException:
            return 0, None

    def _api_post(self, path: str, json_data: dict | None = None) -> tuple[int, Any]:
        token = self._ensure_token()
        if not token:
            return 401, None
        try:
            resp = requests.post(
                f"{self.host}{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=json_data,
                timeout=10,
            )
            return resp.status_code, resp.json() if resp.text else None
        except requests.RequestException:
            return 0, None

    async def _async_update_data(self) -> dict[str, Any] | None:
        return await self.hass.async_add_executor_job(self._poll_state)

    def _poll_state(self) -> dict[str, Any] | None:
        code, data = self._api_get(API_DEVICES)
        if code != 200 or not data:
            self._token = None
            code, data = self._api_get(API_DEVICES)
            if code != 200:
                return None

        if self._device_id:
            for dev in data:
                if dev.get("deviceId") == self._device_id:
                    self._device_data = dev
                    return dev
        elif data:
            self._device_data = data[0]
            return data[0]

        self._device_data = None
        return None

    def send_command(self, command: str, args: dict | None = None) -> bool:
        if not self._device_id:
            devs = self._device_data
            if not devs:
                return False
            self._device_id = devs.get("deviceId")

        code, resp_data = self._api_post(
            API_DEVICE_COMMAND.format(self._device_id),
            {"command": command, "args": args or {}},
        )
        if code == 200 and resp_data:
            if "state" in resp_data:
                self._device_data = resp_data["state"]
            return True

        self._token = None
        code, resp_data = self._api_post(
            API_DEVICE_COMMAND.format(self._device_id),
            {"command": command, "args": args or {}},
        )
        return code == 200


class SBMusicMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_supported_features = SUPPORT_SB_MUSIC

    def __init__(
        self, coordinator: SBMusicDataCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_unique_id = f"sb_music_{config_entry.entry_id}"
        self._attr_name = "SB'Music"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="SB'Music",
            manufacturer="SB'Music",
            model="Self-Hosted",
            sw_version="1.0",
        )

    @property
    def state(self) -> MediaPlayerState:
        if not self.coordinator.data:
            return MediaPlayerState.OFF

        is_playing = self.coordinator.data.get("isPlaying")
        if is_playing is None:
            return MediaPlayerState.IDLE

        return MediaPlayerState.PLAYING if is_playing else MediaPlayerState.PAUSED

    @property
    def media_title(self) -> str | None:
        track = self.coordinator.data.get("track") if self.coordinator.data else None
        return track.get("title") if track else None

    @property
    def media_artist(self) -> str | None:
        track = self.coordinator.data.get("track") if self.coordinator.data else None
        return track.get("artist") if track else None

    @property
    def media_album_name(self) -> str | None:
        track = self.coordinator.data.get("track") if self.coordinator.data else None
        return track.get("album") if track else None

    @property
    def media_image_url(self) -> str | None:
        track = self.coordinator.data.get("track") if self.coordinator.data else None
        thumbnail = track.get("thumbnail") if track else None
        if thumbnail and thumbnail.startswith("//"):
            return "https:" + thumbnail
        return thumbnail

    @property
    def media_duration(self) -> int | None:
        return self.coordinator.data.get("duration") if self.coordinator.data else None

    @property
    def media_position(self) -> float | None:
        return (
            self.coordinator.data.get("currentTime")
            if self.coordinator.data
            else None
        )

    @property
    def media_position_updated_at(self) -> float | None:
        return (
            self.coordinator.data.get("updatedAt")
            if self.coordinator.data
            else None
        )

    @property
    def volume_level(self) -> float | None:
        vol = self.coordinator.data.get("volume") if self.coordinator.data else None
        return vol / 100 if vol is not None else None

    @property
    def shuffle(self) -> bool | None:
        return self.coordinator.data.get("shuffle") if self.coordinator.data else None

    @property
    def repeat(self) -> str | None:
        return self.coordinator.data.get("repeat") if self.coordinator.data else None

    async def async_media_play(self) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "play"
        )
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "pause"
        )
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "pause"
        )
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "next"
        )
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "previous"
        )
        await self.coordinator.async_request_refresh()

    async def async_media_seek(self, position: float) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "seek", {"position": position}
        )
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "volume", {"volume": round(volume * 100)}
        )
        await self.coordinator.async_request_refresh()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "shuffle", {"shuffle": shuffle}
        )
        await self.coordinator.async_request_refresh()

    async def async_set_repeat(self, repeat: str) -> None:
        await self.hass.async_add_executor_job(
            self._coordinator.send_command, "repeat", {"repeat": repeat}
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        await self.async_media_play()

    async def async_turn_off(self) -> None:
        await self.async_media_pause()
