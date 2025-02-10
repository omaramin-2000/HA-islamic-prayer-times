"""The islamic_prayer_times component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import IslamicPrayerDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Islamic Prayer Component."""

    @callback
    def update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if not entity_entry.unique_id.startswith(f"{config_entry.entry_id}-"):
            new_unique_id = f"{config_entry.entry_id}-{entity_entry.unique_id}"
            return {"new_unique_id": new_unique_id}
        return None

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    # add lat and lon to entry data if not present
    if not config_entry.data:
        data = {
            CONF_LOCATION: {
                CONF_LATITUDE: hass.config.latitude,
                CONF_LONGITUDE: hass.config.longitude,
            }
        }
        hass.config_entries.async_update_entry(config_entry, data=data)

    coordinator = IslamicPrayerDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_options_updated)
    )
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Islamic Prayer entry from config_entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        coordinator: IslamicPrayerDataUpdateCoordinator = hass.data[DOMAIN].pop(
            config_entry.entry_id
        )
        if coordinator.event_unsub:
            coordinator.event_unsub()
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Triggered by config entry options updates."""
    coordinator: IslamicPrayerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.event_unsub:
        coordinator.event_unsub()
    await coordinator.async_request_refresh()
