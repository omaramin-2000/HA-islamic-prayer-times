"""Platform to retrieve Islamic prayer times information for Home Assistant."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import CONF_HIJRI_DATE, DOMAIN
from .coordinator import IslamicPrayerDataUpdateCoordinator

from praytimes import PrayTimes
import pytz

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Fajr",
        translation_key="fajr",
    ),
    SensorEntityDescription(
        key="Sunrise",
        translation_key="sunrise",
    ),
    SensorEntityDescription(
        key="Dhuhr",
        translation_key="dhuhr",
    ),
    SensorEntityDescription(
        key="Asr",
        translation_key="asr",
    ),
    SensorEntityDescription(
        key="Maghrib",
        translation_key="maghrib",
    ),
    SensorEntityDescription(
        key="Isha",
        translation_key="isha",
    ),
    SensorEntityDescription(
        key="Imsak",
        translation_key="imsak",
    ),
    SensorEntityDescription(
        key="Midnight",
        translation_key="midnight",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Islamic prayer times sensor platform."""
    coordinator: IslamicPrayerDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        IslamicPrayerTimeSensor(coordinator, description)
        for description in SENSOR_TYPES
    )


class IslamicPrayerTimeSensor(
    CoordinatorEntity[IslamicPrayerDataUpdateCoordinator], SensorEntity
):
    """Representation of an Islamic prayer time sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IslamicPrayerDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Islamic prayer time sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self.pray_times = PrayTimes()
        # Instead of setMethod('MWL'), directly set the parameters
        self.pray_times.adjust({
            'fajr': 19.5,
            'isha': 17.5,
            'dhuhr': '0 min',
            'asr': 'Standard',
            'maghrib': '0 min',
        })
        self.pray_times.asrMethod = 0  # Standard (Shafi'i, Maliki, Ja'fari, Hanbali)
        self.timezone = pytz.timezone('Africa/Cairo')
        self.latitude = 31.2156
        self.longitude = 29.9553

    @property
    def native_value(self) -> datetime:
        """Return the state of the sensor."""
        current_date = datetime.now()
        current_date_list = [current_date.year, current_date.month, current_date.day]
        timezone_offset = self.timezone.utcoffset(current_date).total_seconds() / 3600
        times = self.pray_times.getTimes(current_date_list, (self.latitude, self.longitude), timezone_offset)
        maghrib_time = datetime.strptime(times['maghrib'], '%H:%M')
        earlier_maghrib_time = (maghrib_time - timedelta(minutes=15)).strftime('%H:%M')
        times['maghrib'] = earlier_maghrib_time
        return times[self.entity_description.key.lower()]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return Hijri date as attribute."""
        return {CONF_HIJRI_DATE: self.coordinator.hijri_date}
