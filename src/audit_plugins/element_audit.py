"""ElementAudit plugin.

This plugin can be used to detect certain HTML elements
on web pages. The element this plugin detects
can be customised in the config file using a CSS selector.
"""

import logging
from typing import Any

from bs4 import BeautifulSoup

from config import config

# from src.audit_manager import AuditManager
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser

# import selenium.common.exceptions as sel_exceptions


class ElementAudit(DefaultAudit):
    """element audit."""

    audit_type = "ElementAudit"

    def __init__(self, browser: Browser, **kwargs: Any) -> None:
        """Init variables."""
        super().__init__(browser, **kwargs)
        self.target_element = config.audit_plugins["element_audit"]["target_element_css_selector"]
        self.base_url = kwargs["site_data"]["url"]
        self.viewport_size = kwargs["viewport_size"]

    def run(self) -> list[Any] | bool:
        """Run an element detection on a specified URL.

        Returns:
            list[Any]: rows of test data
            bool: False if test fails, else a list of results
        """
        # Scrape the page source of the loaded browser
        try:
            page_source = self.browser.get_page_source()
        except Exception as exc:
            logging.error("Error getting page source: %s", exc)
            return False

        # Try to parse using BeautifulSoup
        try:
            soup = BeautifulSoup(page_source, "lxml")
        except Exception as exc:
            logging.error("Error parsing page source: %s", exc)
            return False

        # Find all elements of the target type (css selector)
        elements = soup.select(self.target_element)

        found_elements = []

        # For each element found, create a row of data
        for element in elements:
            # get element outer html
            element_data = {"element_html": element.prettify()}
            found_elements.append(element_data)

        # Get page information from DefaultAudit
        default_audit_row = super().run()[0]

        # Add default_test_row to all results
        final_output = []
        for found_element in found_elements:
            final_output.append({**default_audit_row, **found_element})

        return final_output
