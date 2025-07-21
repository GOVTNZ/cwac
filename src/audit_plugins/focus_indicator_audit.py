"""Focus indicator audit plugin.

This audit tests whether the focus indicator is visible
when you press the Tab key. It uses OpenCV to look
at screenshots to see if any pixels changed. If none
changed, then the focus indicator is invisible.
"""

import logging
import sys
import time
from typing import Any

import cv2
import numpy as np
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from config import config
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser


class FocusIndicatorAudit:
    """Focus indiactor audit."""

    audit_type = "FocusIndicatorAudit"

    def __init__(self, browser: Browser, **kwargs: Any) -> None:
        """Init variables."""
        self.pre_num_tab_presses = config.audit_plugins["focus_indicator_audit"]["pre_tab_key_presses"]
        self.max_num_tab_presses = config.audit_plugins["focus_indicator_audit"]["max_tab_key_presses"]
        self.browser = browser
        self.url = kwargs["url"]
        self.site_data = kwargs["site_data"]
        self.audit_id = kwargs["audit_id"]
        self.page_id = kwargs["page_id"]

    def wait_for_page_to_stop_animating(self) -> bool:
        """Wait for animations to finish on the page.

        Returns:
            bool: if the page is still animating after 3 seconds
        """
        logging.info("Waiting for page to stop animating...")
        initial_time = time.time()
        for i in range(5):
            try:
                # Take a screenshot
                logging.info("Taking initial screenshot %s #%i", self.url, i)
                img_a_data = self.screenshot()

                # Wait to see if anything animates
                time.sleep(0.5)

                # Take a second screenshot 0.5s later
                logging.info("Taking second screenshot %s #%i", self.url, i)
                img_b_data = self.screenshot()

            except Exception:  # pylint: disable=broad-except
                logging.exception("Failed to take screenshot")
                return False

            # If the two images are the same, the page is still
            if np.sum(img_a_data != img_b_data) == 0:
                # Pages are equal (0 differing pixels)
                logging.info("Page stopped animating %s #%i", self.url, i)
                return True
            logging.info("Page is still animating #%i", i)

            # If the time elapsed is greater than 15 seconds,
            # give up waiting
            if time.time() - initial_time > 15:
                break
        # If page is still animating, return False to indicate a failure
        logging.warning("Page didn't stop animating! %s", self.url)
        return False

    def expand_browser_to_page_height(self) -> None:
        """Set browser height to the height of the document.

        This is to prevent the page from scrolling
        when the Tab key is pressed.
        """
        try:
            scroll_height = self.browser.driver.execute_script("return document.documentElement.scrollHeight;")
            # Limit the scroll height to 10000px
            scroll_height = min(scroll_height, 10000)
            logging.info("Setting browser height to %i", scroll_height)
            self.browser.driver.set_window_size(
                self.browser.driver.get_window_size()["width"],
                scroll_height,
            )
        except Exception:  # pylint: disable=broad-except
            logging.exception("Failed to get scroll height")

    def check_if_page_has_focus(self) -> bool:
        """Check if the page has focus.

        Useful for detecting if the focusable elements
        have been exhausted on the page
        and the address bar has been focused.

        Returns:
            bool: if the page has focus
        """
        try:
            return bool(self.browser.driver.execute_script("return document.hasFocus()"))
        except Exception:  # pylint: disable=broad-except
            logging.exception("Failed to check if page has focus")
            return False

    def screenshot(self) -> Any:
        """Take a screenshot of the page that's loaded in the browser.

        Returns:
            Any: the screenshot
        """
        return cv2.imdecode(
            np.frombuffer(self.browser.driver.get_screenshot_as_png(), np.uint8),
            cv2.IMREAD_COLOR,
        )

    def run(self) -> list[dict[Any, Any]] | bool:
        """Run the audit.

        Returns:
            bool: if the audit fails
            list[dict[Any, Any]]: a list of audit result dicts
        """
        # Get page information from DefaultAudit
        default_audit_row = DefaultAudit(
            browser=self.browser,
            url=self.url,
            site_data=self.site_data,
            audit_id=self.audit_id,
            page_id=self.page_id,
        ).run()[0]

        result_template = {
            "audit_type": FocusIndicatorAudit.audit_type,
            "helpUrl": ("https://www.w3.org/WAI/WCAG22/" "Understanding/focus-visible.html"),
        }

        # If config.headless is False, log an error
        if not config.headless:
            logging.error("ERROR: FocusIndicatorAudit needs headless=True in config.json")
            print("ERROR: FocusIndicatorAudit needs headless=True in config.json")
            sys.exit(1)

        original_window_size = self.browser.driver.get_window_size()

        # Expand browser to prevent scrolling
        self.expand_browser_to_page_height()

        # Wait for animations to finish
        animation_result = self.wait_for_page_to_stop_animating()

        # If animations didn't finish, return failure data to
        # AuditManager
        if not animation_result:
            return [
                {
                    **default_audit_row,
                    **result_template,
                    "description": (
                        "Page never stopped animating. "
                        "FocusIndicatorAudit could not run as "
                        "a result. Potential WCAG SC Pause, Stop, "
                        "Hide failure (SC 2.2.2) (Level A)."
                    ),
                    "html": "",
                    "num_issues": 1,
                    "helpUrl": ("https://www.w3.org/WAI/WCAG21/" "Understanding/pause-stop-hide.html"),
                }
            ]

        # Take an initial page screenshot as the first 'reference' image
        try:
            reference_image = self.screenshot()
        except Exception:  # pylint: disable=broad-except
            logging.exception("Failed to take screenshot")
            return False

        # Find body element
        try:
            body = self.browser.driver.find_element(By.TAG_NAME, "body")
        except Exception:  # pylint: disable=broad-except
            logging.exception("Failed to find body element")
            return False

        # Store which # of tab key press has no focus indicator
        result_list = []

        plural = ""
        if self.pre_num_tab_presses != 1:
            plural = "s"
        logging.info("pre-tabbing %i time%s", self.pre_num_tab_presses, plural)

        # Press tab a number of times possibly before running the actual audit
        # to help ensure we're actually interacting with a meaningful element
        body.send_keys(*[Keys.TAB] * self.pre_num_tab_presses)

        # Repeatedly press the Tab key
        for i in range(self.max_num_tab_presses):
            body.send_keys(Keys.TAB)

            time.sleep(0.1)

            # If the page has lost focus, skip the test
            if not self.check_if_page_has_focus():
                break

            # Take a screenshot
            try:
                current_image = self.screenshot()
            except Exception:  # pylint: disable=broad-except
                logging.exception("Failed to take screenshot")
                continue

            # Get the difference between the reference image and the
            # current image. Measured as # of pixels that differ
            num_different_pixels = np.sum(reference_image != current_image)

            # Add result to the no_focus_indicator list
            if num_different_pixels == 0:
                # No focus indicator was seen
                # Get the html of the element that has focus
                try:
                    html = self.browser.driver.execute_script("return document.activeElement.outerHTML")
                except Exception:  # pylint: disable=broad-except
                    logging.exception("Failed to get html of focused element")
                    continue
                result_list.append({"html": html[:100], "tab_press": i + 1})

        final_results = []

        # If result_list is empty, return a success result
        if not result_list:
            return [
                {
                    **default_audit_row,
                    **result_template,
                    "description": "All tab presses had a focus indicator",
                    "html": "",
                    "num_issues": 0,
                    "helpUrl": ("https://www.w3.org/WAI/WCAG22/" "Understanding/focus-visible.html"),
                }
            ]

        # Iterate through results_list and add to final_results
        for result in result_list:
            final_results.append(
                {
                    **default_audit_row,
                    **result_template,
                    "description": (f"Tab key press #{result['tab_press']}" f" did not show a focus indicator"),
                    "html": result["html"],
                    "num_issues": 1,
                    "helpUrl": ("https://www.w3.org/WAI/WCAG22/" "Understanding/focus-visible.html"),
                }
            )

        # Reset browser size
        self.browser.driver.set_window_size(**original_window_size)

        return final_results
