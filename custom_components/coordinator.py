"""Data update coordinator for GitHub releases."""

from __future__ import annotations

import json
from calendar import timegm
from datetime import datetime
import logging
from time import gmtime, struct_time
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ASSET_FILTER,
    CONF_REPO_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_GITHUB_RELEASE,
)

DELAY_SAVE = 30
STORAGE_VERSION = 1

_LOGGER = logging.getLogger(__name__)

type GitHubReleaseConfigEntry = ConfigEntry[GitHubReleaseCoordinator]


class GitHubReleaseCoordinator(
    DataUpdateCoordinator[dict[str, Any] | None]
):
    """Abstraction over GitHub Releases API."""

    config_entry: GitHubReleaseConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GitHubReleaseConfigEntry,
        storage: StoredData,
    ) -> None:
        """Initialize the GitHubReleaseCoordinator."""
        self.repo_url = config_entry.data[CONF_REPO_URL]
        self.asset_filter = config_entry.data.get(CONF_ASSET_FILTER, "").lower()
        self._storage = storage
        self._last_release_id: int | None = None
        self._last_tag_name: str | None = None
        self._event_type = EVENT_GITHUB_RELEASE
        self._release_data: dict[str, Any] | None = None
        self._feed_id = self.repo_url
        
        # Extract repo name from URL for logging
        self.repo_name = self._extract_repo_name()
        
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {self.repo_name}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
    
    def _extract_repo_name(self) -> str:
        """Extract repository name from GitHub API URL."""
        # Example: https://api.github.com/repos/knoop7/Ava/releases/latest
        parts = self.repo_url.strip("/").split("/")
        if len(parts) >= 2:
            return f"{parts[-3]}/{parts[-2]}"
        return self.repo_url

    async def _async_fetch_release(self) -> dict[str, Any]:
        """Fetch the latest release data from GitHub API."""
        _LOGGER.debug("Fetching latest release from %s", self.repo_url)
        
        session = async_get_clientsession(self.hass)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Home-Assistant-GitHub-Release-Tracker"
        }
        
        try:
            async with session.get(self.repo_url, headers=headers) as response:
                if response.status != 200:
                    raise UpdateFailed(
                        f"Error fetching GitHub release: {response.status}"
                    )
                
                data = await response.json()
                
                if not data or "id" not in data:
                    raise UpdateFailed("Invalid response from GitHub API")
                
                return data
                
        except Exception as err:
            raise UpdateFailed(f"Error fetching GitHub release: {err}") from err

    async def async_setup(self) -> None:
        """Set up the release tracker."""
        try:
            release_data = await self._async_fetch_release()
        except UpdateFailed as err:
            raise ConfigEntryNotReady from err

        self.logger.debug(
            "Release data fetched from %s: %s",
            self.repo_url,
            {"id": release_data["id"], "tag_name": release_data["tag_name"]},
        )
        
        self._release_data = release_data
        
        # Load last known release from storage
        stored_id = self._storage.get_release_id(self._feed_id)
        stored_tag = self._storage.get_tag_name(self._feed_id)
        
        if stored_id:
            self._last_release_id = stored_id
            self._last_tag_name = stored_tag

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Update the release data and publish new release to event bus."""
        assert self._release_data is not None
        
        # Always fetch new data
        self._release_data = await self._async_fetch_release()
        
        current_id = self._release_data["id"]
        current_tag = self._release_data["tag_name"]
        
        _LOGGER.debug(
            "Current release: id=%s, tag=%s, Last known: id=%s, tag=%s",
            current_id,
            current_tag,
            self._last_release_id,
            self._last_tag_name,
        )
        
        # Check if this is a new release
        if (
            self._last_release_id is None  # First run
            or current_id != self._last_release_id  # Different release ID
            or current_tag != self._last_tag_name  # Different tag name
        ):
            _LOGGER.info(
                "New release detected for %s: %s (id: %s)",
                self.repo_name,
                current_tag,
                current_id,
            )
            
            # Find the appropriate asset
            asset_data = self._find_asset()
            
            # Fire event with release data
            self._fire_release_event(asset_data)
            
            # Update storage
            self._last_release_id = current_id
            self._last_tag_name = current_tag
            self._storage.async_put_release(
                self._feed_id, current_id, current_tag
            )
            
            return self._release_data
        else:
            _LOGGER.debug("No new release for %s", self.repo_name)
            return None
    
    def _find_asset(self) -> dict[str, Any] | None:
        """Find the appropriate asset based on filter."""
        if not self._release_data or "assets" not in self._release_data:
            return None
        
        assets = self._release_data["assets"]
        
        if not assets:
            return None
        
        # If no filter, return first asset
        if not self.asset_filter:
            return assets[0]
        
        # Try to find asset matching filter
        for asset in assets:
            asset_name = asset.get("name", "").lower()
            if self.asset_filter in asset_name:
                return asset
        
        # If no match, return first asset
        _LOGGER.warning(
            "No asset matching filter '%s' found, using first asset",
            self.asset_filter,
        )
        return assets[0]
    
    @callback
    def _fire_release_event(self, asset_data: dict[str, Any] | None) -> None:
        """Fire event with release data."""
        assert self._release_data is not None
        
        event_data = {
            "repo_name": self.repo_name,
            "release_version": self._release_data["tag_name"],
            "release_name": self._release_data.get("name", ""),
            "release_url": self._release_data["html_url"],
            "published_at": self._release_data["published_at"],
            "author": self._release_data["author"].get("login", "") if "author" in self._release_data else "",
            "prerelease": self._release_data["prerelease"],
            "body": self._release_data.get("body", ""),
        }
        
        if asset_data:
            event_data.update({
                "download_url": asset_data["browser_download_url"],
                "asset_name": asset_data["name"],
                "asset_size": asset_data["size"],
            })
        else:
            event_data["download_url"] = ""
            event_data["asset_name"] = ""
            event_data["asset_size"] = 0
        
        self.hass.bus.async_fire(self._event_type, event_data)
        _LOGGER.debug("New release event fired for %s", self.repo_name)


class StoredData:
    """Represent a data storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize data storage."""
        self._release_ids: dict[str, int] = {}
        self._tag_names: dict[str, str] = {}
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, DOMAIN)
        self.is_initialized = False

    async def async_setup(self) -> None:
        """Set up storage."""
        if (store_data := await self._store.async_load()) is not None:
            self._release_ids = store_data.get("release_ids", {})
            self._tag_names = store_data.get("tag_names", {})
        self.is_initialized = True

    def get_release_id(self, feed_id: str) -> int | None:
        """Return stored release ID for given feed id."""
        return self._release_ids.get(feed_id)
    
    def get_tag_name(self, feed_id: str) -> str | None:
        """Return stored tag name for given feed id."""
        return self._tag_names.get(feed_id)

    @callback
    def async_put_release(self, feed_id: str, release_id: int, tag_name: str) -> None:
        """Update release data for given feed id."""
        self._release_ids[feed_id] = release_id
        self._tag_names[feed_id] = tag_name
        self._store.async_delay_save(self._async_save_data, DELAY_SAVE)

    @callback
    def _async_save_data(self) -> dict[str, Any]:
        """Save release data to storage."""
        return {
            "release_ids": self._release_ids,
            "tag_names": self._tag_names,
        }