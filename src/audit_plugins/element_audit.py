"""ElementAudit plugin.

This plugin can be used to detect certain HTML elements
on web pages. The element this plugin detects
can be customised in the config file using a CSS selector.
"""

import logging
#import selenium.common.exceptions as sel_exceptions

from typing import Any, Union, List
from bs4 import BeautifulSoup

from config import config
#from src.audit_manager import AuditManager
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser


class ElementAudit:
    """element audit."""
 # pylint: disable=too-many-instance-attributes

    audit_type = "ElementAudit"

    def __init__(self, browser: Browser, **kwargs: Any) -> None:
        """Init variables."""
        self.target_element = config.audit_plugins["element_audit"]["target_element_css_selector"]
        self.site_data = kwargs["site_data"]
        self.base_url = kwargs["site_data"]["url"]
        self.url = kwargs["url"]
        self.viewport_size = kwargs["viewport_size"]
        self.browser = browser
        self.audit_id = kwargs["audit_id"]
        self.page_id = kwargs["page_id"]

    def run(self) -> Union[list[Any], bool]:
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
        default_audit = DefaultAudit(
            browser=self.browser,
            url=self.url,
            site_data=self.site_data,
            audit_id=self.audit_id,
            page_id=self.page_id,
        )
        default_audit_row = default_audit.run()[0]

        # Add default_test_row to all results
        final_output = []
        for found_element in found_elements:
            final_output.append({**default_audit_row, **found_element})

        return final_output
