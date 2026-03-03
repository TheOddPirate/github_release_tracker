"""Event entities for GitHub releases."""

from __future__ import annotations

import logging

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GitHubReleaseConfigEntry
from .const import (
    ATTR_ASSET_NAME,
    ATTR_ASSET_SIZE,
    ATTR_AUTHOR,
    ATTR_BODY,
    ATTR_DOWNLOAD_URL,
    ATTR_PRERELEASE,
    ATTR_PUBLISHED_AT,
    ATTR_RELEASE_NAME,
    ATTR_RELEASE_URL,
    ATTR_RELEASE_VERSION,
    ATTR_REPO_NAME,
    DOMAIN,
    EVENT_GITHUB_RELEASE,
)
from .coordinator import GitHubReleaseCoordinator

LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GitHubReleaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event entities for github_release_tracker."""
    coordinator = entry.runtime_data

    async_add_entities([GitHubReleaseEvent(coordinator)])


class GitHubReleaseEvent(CoordinatorEntity[GitHubReleaseCoordinator], EventEntity):
    """Representation of a github_release_tracker event."""

    _attr_event_types = [EVENT_GITHUB_RELEASE]
    _attr_name = None
    _attr_has_entity_name = True
    _attr_translation_key = "latest_release"
    _unrecorded_attributes = frozenset(
        {
            ATTR_REPO_NAME,
            ATTR_RELEASE_VERSION,
            ATTR_RELEASE_NAME,
            ATTR_DOWNLOAD_URL,
            ATTR_RELEASE_URL,
            ATTR_PUBLISHED_AT,
            ATTR_ASSET_NAME,
            ATTR_ASSET_SIZE,
            ATTR_AUTHOR,
            ATTR_PRERELEASE,
            ATTR_BODY,
        }
    )

    def __init__(self, coordinator: GitHubReleaseCoordinator) -> None:
        """Initialize the github_release_tracker event."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_latest_release"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            configuration_url=coordinator.repo_url,
            manufacturer="GitHub",
            sw_version=coordinator._last_tag_name or "Unknown",
            entry_type=DeviceEntryType.SERVICE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (data := self.coordinator.data) is None:
            return

        # Data contains the latest release information
        release_data = data

        # Prepare event data
        event_data = {
            ATTR_REPO_NAME: self.coordinator.repo_name,
            ATTR_RELEASE_VERSION: release_data.get("tag_name", ""),
            ATTR_RELEASE_NAME: release_data.get("name", ""),
            ATTR_RELEASE_URL: release_data.get("html_url", ""),
            ATTR_PUBLISHED_AT: release_data.get("published_at", ""),
            ATTR_AUTHOR: (
                release_data["author"].get("login", "")
                if "author" in release_data
                else ""
            ),
            ATTR_PRERELEASE: release_data.get("prerelease", False),
            ATTR_BODY: release_data.get("body", ""),
        }

        # Add asset information if available
        assets = release_data.get("assets", [])
        if assets:
            # Use first asset or find by filter
            asset = self.coordinator._find_asset()
            if asset:
                event_data[ATTR_DOWNLOAD_URL] = asset.get("browser_download_url", "")
                event_data[ATTR_ASSET_NAME] = asset.get("name", "")
                event_data[ATTR_ASSET_SIZE] = asset.get("size", 0)
            else:
                event_data[ATTR_DOWNLOAD_URL] = ""
                event_data[ATTR_ASSET_NAME] = ""
                event_data[ATTR_ASSET_SIZE] = 0
        else:
            event_data[ATTR_DOWNLOAD_URL] = ""
            event_data[ATTR_ASSET_NAME] = ""
            event_data[ATTR_ASSET_SIZE] = 0

        self._trigger_event(EVENT_GITHUB_RELEASE, event_data)
        self.async_write_ha_state()