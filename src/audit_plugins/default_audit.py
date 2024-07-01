"""Default audit plugin.

This plugin returns basic page information.
"""

import urllib.parse
from typing import Any

from config import config
from src.browser import Browser

# Audit classes for use with AuditManager
# Audit classes are registered with register_test
# Audit classes MUST implement:
# def __init__(self, browser: Browser, **kwargs) -> None
#   - accepts a browser, and kwargs
# run(self) -> bool/list
#   - runs the actual audit
#   - if audit is successful, returns a list of dictionaries
#       which form CSV data rows
#   - if the audit fails, returns False


class DefaultAudit:
    """An audit that returns basic page info.

    It retrieves things such as the page title, viewport size, and base url.
    """

    def __init__(self, browser: Browser, **kwargs: Any):
        """Init variables."""
        self.browser = browser
        self.url = kwargs["url"]
        self.site_data = kwargs["site_data"]
        self.audit_id = kwargs["audit_id"]
        self.page_id = kwargs["page_id"]

    def run(self) -> list[dict[Any, Any]]:
        """Run the audit.

        Returns:
            list[dict[Any, Any]]: a list of audit result dicts
        """
        # If nocrawl mode is True, site_data does not contain
        # organisation, or sector so we will request it from the lookup
        # function in config.py

        # if organisation exists in site_data, use it
        # otherwise, use the lookup function
        org_data = config.lookup_organisation(self.site_data["url"])
        if "organisation" not in self.site_data:
            self.site_data["organisation"] = org_data["organisation"]

        if "sector" not in self.site_data:
            self.site_data["sector"] = org_data["sector"]

        # If config.json specifies nocrawl_mode is True, then
        # use the subdomain + domain as the base_url
        base_url = self.site_data["url"]
        if config.nocrawl_mode:
            # Parse the url to get the subdomain and domain using urlparse
            # and then rejoin them to get the base_url
            parsed_url = urllib.parse.urlparse(base_url)
            base_url = parsed_url.scheme + "://" + parsed_url.netloc

        return [
            {
                "organisation": self.site_data["organisation"],
                "sector": self.site_data["sector"],
                "page_title": self.browser.driver.title,
                "base_url": base_url,
                "url": self.url,
                "viewport_size": self.browser.driver.get_window_size(),
                "audit_id": self.audit_id,
                "page_id": self.page_id,
            }
        ]
