"""Constants for GitHub Release Tracker."""

from datetime import timedelta
from typing import Final

DOMAIN: Final[str] = "github_release_tracker"

CONF_REPO_URL: Final[str] = "repo_url"
CONF_ASSET_FILTER: Final[str] = "asset_filter"
DEFAULT_SCAN_INTERVAL: Final[timedelta] = timedelta(hours=24)

EVENT_GITHUB_RELEASE: Final[str] = "github_release"

# Event attributes
ATTR_REPO_NAME: Final[str] = "repo_name"
ATTR_RELEASE_VERSION: Final[str] = "release_version"
ATTR_RELEASE_NAME: Final[str] = "release_name"
ATTR_DOWNLOAD_URL: Final[str] = "download_url"
ATTR_RELEASE_URL: Final[str] = "release_url"
ATTR_PUBLISHED_AT: Final[str] = "published_at"
ATTR_ASSET_NAME: Final[str] = "asset_name"
ATTR_ASSET_SIZE: Final[str] = "asset_size"
ATTR_AUTHOR: Final[str] = "author"
ATTR_PRERELEASE: Final[str] = "prerelease"
ATTR_BODY: Final[str] = "body"