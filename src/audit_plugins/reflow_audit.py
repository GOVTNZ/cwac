"""Reflow Audit plugin.

Tests WCAG 1.4.10 Reflow by resizing the browser window to 320px

Unforuntately there's no API to set the zoom level in Selenium,
so we have to restart the browser in headless mode to test it.
If the browser's already headless, we just resize the window.

Disclaimer:
    This test does not properly test the normative requirement of
    WCAG 1.4.10. But, it does provide a good indication of whether
    the page is responsive. Manual testing is still required to
    ensure WCAG 1.4.10 is met.

"""

import logging
import sys
import time
from typing import Any

from config import Config
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser


class ReflowAudit(DefaultAudit):
    """Audit WCAG 1.4.10 Reflow."""

    audit_type = "ReflowAudit"

    def __init__(self, config: Config, browser: Browser, **kwargs: Any) -> None:
        """Init variables."""
        super().__init__(config, browser, **kwargs)

        # Provide warning if headless mode is not enabled
        if not self.config.headless:
            logging.warning(
                "Headless mode is not enabled."
                "ReflowAudit performance will be reduced."
                "To enable headless mode, set headless to true in config.json."
            )

    def run(self) -> list[dict[str, Any]] | bool:
        """Run the test.

        WCAG 1.4.10 Reflow is partially tested by zooming
        to 400% and checking if the page overflows. This requires
        a viewport_size to be specified in config.json that has a
        width of exactly 1280px. If no such viewport_size is
        specified, the test will instead default to a simple
        check for overflow of the page.

        Returns:
            bool: if the audit fails
            list[dict[Any, Any]]: a list of audit result dicts
        """
        if not self.config.headless:
            # Log an error and quit
            logging.error("Headless mode must be enabled for ReflowAudit.")
            print("Headless mode must be enabled for ReflowAudit.")
            sys.exit(1)

        # If browser is not 320px wide
        if self.browser.driver.get_window_size()["width"] != 320:
            logging.error("ReflowAudit must only run at 320px wide")
            print("ReflowAudit must only run at 320px wide")
            print("Width was " + str(self.browser.driver.get_window_size()["width"]))
            sys.exit(1)

        # Only load the page if it's not already loaded
        self.browser.get_if_necessary(self.url)

        # Wait for the page to render
        time.sleep(0.3)

        # Determine if there is a horisontal overflow
        try:
            self.browser.driver.execute_script("window.scrollTo(100, 0);")
            overflow_amount = self.browser.driver.execute_script("return window.scrollX;")
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("Failed to scroll to 100px %s", self.url, exc_info=True)
            return False

        # Run a ScreenshotAudit if the page overflows
        if self.config.audit_plugins["reflow_audit"]["screenshot_failures"] and overflow_amount > 0:
            # pylint: disable=import-outside-toplevel
            from src.audit_plugins.screenshot_audit import ScreenshotAudit

            screenshot_audit = ScreenshotAudit(
                config=self.config,
                browser=self.browser,
                url=self.url,
                site_data=self.site_data,
                audit_id=self.audit_id,
                page_id=self.page_id,
            )
            screenshot_audit.run()

        # Reset scroll position
        try:
            self.browser.driver.execute_script("window.scrollTo(0, 0);")
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception(
                "Failed to reset scroll position after test %s",
                self.url,
                exc_info=True,
            )

        return [
            {
                **self._default_audit_row,
                "audit_type": ReflowAudit.audit_type,
                "url": self.url,
                "overflows": overflow_amount > 0,
                "num_issues": 1 if overflow_amount > 0 else 0,
                "overflow_amount_px": overflow_amount,
            }
        ]
