"""Coordinator for the Islamic prayer times integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, cast

from requests.exceptions import ConnectionError as ConnError
from praytimes import PrayTimes
import pytz

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_CALC_METHOD,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    CONF_TUNE,
    DEFAULT_CALC_METHOD,
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_MIDNIGHT_MODE,
    DEFAULT_SCHOOL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class IslamicPrayerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, datetime]]):
    """Islamic Prayer Client Object."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Islamic Prayer client."""
        self.event_unsub: CALLBACK_TYPE | None = None
        self.hijri_date: str | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.pray_times = PrayTimes()
        self.pray_times.setMethod('MWL')
        self.pray_times.adjust({'fajr': 19.5, 'isha': 17.5})
        self.pray_times.asrMethod = 0
        self.timezone = pytz.timezone('Africa/Cairo')
        self.latitude = 31.2156
        self.longitude = 29.9553

    @property
    def calc_method(self) -> str:
        """Return the calculation method."""
        return self.config_entry.options.get(
            CONF_CALC_METHOD, DEFAULT_CALC_METHOD
        ).lower()

    @property
    def lat_adj_method(self) -> str:
        """Return the latitude adjustment method."""
        return str(
            self.config_entry.options.get(
                CONF_LAT_ADJ_METHOD, DEFAULT_LAT_ADJ_METHOD
            ).replace("_", " ")
        )

    @property
    def midnight_mode(self) -> str:
        """Return the midnight mode."""
        return self.config_entry.options.get(CONF_MIDNIGHT_MODE, DEFAULT_MIDNIGHT_MODE)

    @property
    def school(self) -> str:
        """Return the school."""
        return self.config_entry.options.get(CONF_SCHOOL, DEFAULT_SCHOOL)

    def get_new_prayer_times(self) -> dict[str, str]:
        """Fetch prayer times for today."""
        current_date = datetime.now()
        current_date_list = [current_date.year, current_date.month, current_date.day]
        timezone_offset = self.timezone.utcoffset(current_date).total_seconds() / 3600
        times = self.pray_times.getTimes(current_date_list, (self.latitude, self.longitude), timezone_offset)
        maghrib_time = datetime.strptime(times['maghrib'], '%H:%M')
        earlier_maghrib_time = (maghrib_time - timedelta(minutes=15)).strftime('%H:%M')
        times['maghrib'] = earlier_maghrib_time
        return times

    async def async_request_update(self, *_) -> None:
        """Request update from coordinator."""
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, datetime]:
        """Update sensors with new prayer times."""
        try:
            prayer_times = await self.hass.async_add_executor_job(
                self.get_new_prayer_times
            )
        except Exception as err:
            async_call_later(self.hass, 60, self.async_request_update)
            raise UpdateFailed from err

        # The recommended update time is 02:00 am as per issue #68095
        self.event_unsub = async_track_point_in_time(
            self.hass,
            self.async_request_update,
            dt_util.start_of_local_day() + timedelta(days=1, hours=2, minutes=1),
        )

        if "date" in prayer_times:
            self.hijri_date = prayer_times.pop("date")["hijri"]["date"]
        prayer_times_info: dict[str, datetime] = {}
        for prayer, time in prayer_times.items():
            if prayer_time := dt_util.parse_datetime(time):
                prayer_times_info[prayer] = dt_util.as_utc(prayer_time)

        return prayer_times_info
