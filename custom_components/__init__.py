"""Support for tracking GitHub releases."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import GitHubReleaseConfigEntry, GitHubReleaseCoordinator, StoredData

GITHUB_RELEASE_KEY: HassKey[StoredData] = HassKey(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant, entry: GitHubReleaseConfigEntry
) -> bool:
    """Set up GitHub Release Tracker from a config entry."""
    storage = hass.data.setdefault(GITHUB_RELEASE_KEY, StoredData(hass))
    if not storage.is_initialized:
        await storage.async_setup()

    coordinator = GitHubReleaseCoordinator(hass, entry, storage)

    await coordinator.async_setup()

    entry.runtime_data = coordinator

    # we need to setup event entities before the first coordinator data fetch
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.EVENT])

    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GitHubReleaseConfigEntry
) -> bool:
    """Unload a config entry."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    # if this is the last entry, remove the storage
    if len(entries) == 1:
        hass.data.pop(GITHUB_RELEASE_KEY)
    return await hass.config_entries.async_unload_platforms(entry, [Platform.EVENT])