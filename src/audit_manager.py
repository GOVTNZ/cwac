"""AuditManager - runs tests on a Browser."""

import logging
import os
import time
import urllib.parse
from typing import Any, Type

import selenium
from selenium.webdriver.common.by import By

import src.output
from config import config
from src.analytics import Analytics
from src.browser import Browser
from src.output import CSVWriter

# pylint: disable=too-many-branches, too-many-statements


class AuditManager:
    """Runs tests on browsers."""

    # Stores axe.min.js to prevent re-reading the file
    axe_core_js = ""

    def __init__(self, browser: Browser, analytics: Analytics) -> None:
        """Init variables."""
        self.browser = browser
        self.analytics = analytics
        self.audits: dict[Any, dict[Any, Any]] = {}
        self.filter = src.filters.URLFilter()

        # Stores URLs discarded as a key-value pair
        # of URL (str): reason (str). URLs are discarded
        # if they are blocked by anti-bot measures.
        self.discarded_urls: dict[str, str] = {}

    def register_audit(self, audit_name: str, audit_class: Type[Any], **kwargs: Any) -> None:
        """Register audits to be run by run_audits().

        This can also be used to re-run a test with updated kwargs.

        Args:
            audit_name (str): Human-readable name for audit
            audit_class (Type[Any]): Reference to a class that runs the audit
            kwargs (Any): Arbitrary args to be passed to audit_class
        """
        # Register the audit (or update its kwargs)
        self.audits[audit_name] = {
            "audit_class": audit_class,
            "kwargs": kwargs,
        }

    def test_for_anti_bot(self) -> str:
        """Inspect the page for anti-bot blocking.

        Write the result to an 'anti_bot' CSV file.

        Returns:
            str: 'Pass' if no anti-bot blocking detected,
            'Imperva' if Incapsula detected, 'Cloudflare'
            if Cloudflare detected. 'Blocked' if the URL
            has already been discarded. 'Azure Front Door'
            if Azure Front Door detected.
        """
        # Get the current URL
        try:
            url = self.browser.driver.current_url
        except selenium.common.exceptions.TimeoutException:
            logging.error("TimeoutException when getting current URL")
            return "Pass"
        except selenium.common.exceptions.WebDriverException:
            logging.error("WebDriverException when getting current URL")
            return "Pass"

        # If the URL is already discarded return its result
        if url in self.discarded_urls:
            return self.discarded_urls[url]

        # Get the page source
        try:
            page_source = self.browser.driver.page_source
        except selenium.common.exceptions.TimeoutException:
            logging.error("TimeoutException when getting page source")
            return "Pass"
        except selenium.common.exceptions.WebDriverException:
            logging.error("WebDriverException when getting page source")
            return "Pass"

        status = "Pass"

        # Check for 'Incapsula' in the page source
        if "Incapsula incident ID" in page_source:
            logging.error("Incapsula detected on %s", url)
            status = "Imperva"

        # Check for 'Cloudflare' in the page source
        if "Cloudflare Ray ID" in page_source:
            logging.error("Cloudflare detected on %s", url)
            status = "Cloudflare"

        # Check for 'Azure Front Door' in the page source
        afd_sig = """The request is blocked.</h2></div><div id="errorref">"""
        if afd_sig in page_source:
            logging.error("Azure Front Door detected on %s", url)
            status = "Azure Front Door"

        if status != "Pass":
            # Get the URL's organisation
            org = config.lookup_organisation(url)

            # Get URL's netloc
            netloc = urllib.parse.urlparse(url).netloc

            # Save screenshot
            # Make screenshot directory if it doesn't exist
            os.makedirs(
                f"./results/{config.audit_name}/anti_bot_ss",
                exist_ok=True,
            )
            self.browser.driver.save_screenshot(f"./results/{config.audit_name}/anti_bot_ss/{netloc}.png")

            # Write to anti-bot.csv
            csv_writer = CSVWriter()
            csv_writer.add_rows(
                [
                    {
                        "organisation": org["organisation"],
                        "domain": netloc,
                        "url": url,
                        "anti_bot_check": status,
                        "viewport_size": self.browser.viewport_size,
                    }
                ]
            )
            csv_writer.write_csv_file(f"./results/{config.audit_name}/anti_bot.csv")
            self.discarded_urls[url] = status

        return status

    def check_for_details_elements(self) -> None:
        """Check if there are <details> elements that should be opened so their contents are audited."""
        details = self.browser.driver.find_elements(By.TAG_NAME, "details")

        if len(details) == 0:
            return

        plural = ""
        if len(details) != 1:
            plural = "s"

        if not config.force_open_details_elements:
            logging.info("ignoring %i <details> element%s", len(details), plural)
            return

        logging.info("opening %i <details> element%s", len(details), plural)

        # Open all <details> elements
        for detail in details:
            if not detail.get_attribute("open"):
                try:
                    self.browser.driver.execute_script("arguments[0].setAttribute('open', '')", detail)
                except Exception:  # pylint: disable=broad-except
                    logging.warning("Could not open <details> element titled '%s'", detail.text)
                    continue

    def run_audits(self) -> bool:
        """Iterate through registered audits and runs them.

        Returns:
            bool: True if all audits successful, else False
        """
        logging.info("run_audits called")

        # Unique UUID string
        page_id = config.get_unique_id()

        # Tracks if all tests successfully ran
        all_tests_successful = True

        # Re-run tests for each viewport size in config.json
        for index, viewport in enumerate(config.viewport_sizes):
            # Generate a unique audit ID
            audit_id = page_id + "_" + viewport

            self.browser.set_window_size(
                config.viewport_sizes[viewport]["width"],
                config.viewport_sizes[viewport]["height"],
            )

            for audit_name, audit in self.audits.items():
                # if viewport_to_test is set
                if (
                    "viewport_to_test" in config.audit_plugins[audit_name]
                    and config.audit_plugins[audit_name]["viewport_to_test"] != viewport
                ):
                    # If the viewport is not the one we want to test, skip
                    continue

                # Log the start of this audit
                logging.info(
                    "Starting audit %s on %s",
                    audit_name,
                    audit["kwargs"]["url"],
                )

                # Only load the page if it's not already loaded
                browser_status = self.browser.get_if_necessary(audit["kwargs"]["url"])

                # Test for anti-bot measures
                if self.test_for_anti_bot() != "Pass":
                    # If URL is blocked, skip this URL
                    logging.warning(
                        "Skipping test %s on %s due to anti-bot",
                        audit_name,
                        audit["kwargs"]["url"],
                    )
                    return False

                # If the browser fails to load the page, skip test
                if browser_status is False:
                    logging.warning(
                        "Skipping test %s on %s due to .get failure",
                        audit_name,
                        audit["kwargs"]["url"],
                    )
                    continue

                self.check_for_details_elements()

                # Inject the audit ID
                audit["kwargs"]["audit_id"] = audit_id

                # Inject the page ID
                audit["kwargs"]["page_id"] = page_id

                # Inject the viewport size dict
                audit["kwargs"]["viewport_size"] = config.viewport_sizes[viewport]

                start_time = time.perf_counter()

                # Run the tests
                test_instance = audit["audit_class"](browser=self.browser, **audit["kwargs"])

                try:
                    audit_result = test_instance.run()
                except selenium.common.exceptions.WebDriverException:
                    logging.exception(
                        "Due to WebDriverException, test %s skipped on viewport %s for website %s",
                        audit_name,
                        viewport,
                        audit["kwargs"]["url"],
                        exc_info=True,
                    )
                    # If the browser crashes, skip this test
                    # and restart the browser
                    self.browser.safe_restart()

                    # Set window size
                    self.browser.set_window_size(
                        config.viewport_sizes[viewport]["width"],
                        config.viewport_sizes[viewport]["height"],
                    )

                    # Reload the page
                    browser_status = self.browser.get_if_necessary(audit["kwargs"]["url"])
                    if browser_status is False:
                        logging.error(
                            "After a WebDriverException .get failed on %s %s",
                            audit_name,
                            audit["kwargs"]["url"],
                        )
                    continue

                except Exception:  # pylint: disable=broad-except
                    logging.exception(
                        "Unhandled exception %s %s",
                        audit_name,
                        audit["kwargs"]["url"],
                        exc_info=True,
                    )
                    all_tests_successful = False
                    continue

                logging.info("Test finished %s, %s", audit_name, audit["kwargs"]["url"])

                # If audit_result is the boolean value True
                # a 'True' from the audit means to skip the audit
                # because it is not applicable to the current page,
                # but the audit did not fail to execute
                if audit_result is True:
                    logging.info(
                        "Skipping audit %s, %s",
                        audit_name,
                        audit["kwargs"]["url"],
                    )
                    continue

                # If a test fails, .run() returns False
                if audit_result is False:
                    all_tests_successful = False
                    logging.error(
                        "Test failed %s, %s",
                        audit_name,
                        audit["kwargs"]["url"],
                    )
                    continue

                # If a test returns an empty result, log an error
                if audit_result == []:
                    logging.error(
                        "Test gave empty response %s, %s",
                        audit_name,
                        audit["kwargs"]["url"],
                    )
                    continue

                # Performance measurement
                end_time = time.perf_counter()
                elapsed_time = end_time - start_time
                logging.info(
                    "Test time %s %s %.5f",
                    audit_name,
                    audit["kwargs"]["url"],
                    elapsed_time,
                )

                # Write results
                csv_writer = CSVWriter()
                csv_writer.add_rows(audit_result)
                csv_writer.write_csv_file(f"./results/{config.audit_name}/{audit_name}.csv")

            # If we're not on the last viewport size
            if index < len(config.viewport_sizes) - 1:
                # Refresh the page
                try:
                    self.browser.driver.refresh()
                    # Give browser time to adjust to viewport size
                    time.sleep(config.delay_between_viewports)
                except Exception:  # pylint: disable=broad-except
                    logging.exception("Failed to refresh page")
                    self.browser.safe_restart()
                    break

        return all_tests_successful
