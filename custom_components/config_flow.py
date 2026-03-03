"""Config flow for GitHub Release Tracker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ASSET_FILTER, CONF_REPO_URL, DOMAIN


async def validate_repo_url(hass: HomeAssistant, repo_url: str) -> dict[str, Any]:
    """Validate the GitHub repository URL."""
    # Check if URL ends with /releases/latest
    if not repo_url.endswith("/releases/latest"):
        # Try to construct the correct URL
        repo_url = repo_url.rstrip("/")
        if not repo_url.endswith("/releases"):
            repo_url = f"{repo_url}/releases"
        repo_url = f"{repo_url}/latest"
    
    # Validate by making a request
    session = async_get_clientsession(hass)
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Home-Assistant-GitHub-Release-Tracker",
    }
    
    async with session.get(repo_url, headers=headers) as response:
        if response.status != 200:
            raise ValueError("Invalid GitHub repository or releases not found")
        
        data = await response.json()
        if "id" not in data:
            raise ValueError("Invalid response from GitHub API")
        
        # Extract repo name
        parts = repo_url.strip("/").split("/")
        repo_name = f"{parts[-3]}/{parts[-2]}" if len(parts) >= 2 else "Unknown"
        
        return {
            "title": f"GitHub Releases: {repo_name}",
            "repo_name": repo_name,
            "validated_url": repo_url,
        }


class GitHubReleaseTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GitHub Release Tracker."""

    VERSION = 1
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                validation_result = await validate_repo_url(
                    self.hass, user_input[CONF_REPO_URL]
                )
                
                # Check if already configured
                await self.async_set_unique_id(validation_result["validated_url"])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=validation_result["title"],
                    data={
                        CONF_REPO_URL: validation_result["validated_url"],
                        CONF_ASSET_FILTER: user_input.get(CONF_ASSET_FILTER, ""),
                    },
                )
                
            except ValueError as err:
                errors["base"] = "invalid_repo_url"
                _LOGGER.error("Invalid GitHub repository URL: %s", err)
            except Exception as err:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected exception: %s", err)
        
        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REPO_URL): str,
                    vol.Optional(CONF_ASSET_FILTER, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "example_url": "https://api.github.com/repos/owner/repo/releases/latest",
            },
        )


# Import logger
import logging
_LOGGER = logging.getLogger(__name__)