"""Analytics for the scan."""

import time
import urllib.parse

import src.output
from config import config


class Analytics:
    """Analytics that track scan statistics."""

    def __init__(self) -> None:
        """Initialise variables."""
        # Tracks how many pages have been scanned
        self.total_pages_scanned = 0

        # An estimate of how many pages are in the entire test
        self.est_num_pages_in_test = 0

        # A dict of every URL scanned
        self.pages_scanned: dict[str, set[str]] = {}

        # Time script started
        self.start_time = time.time()

        # Store the full set of base_urls
        self.base_urls: set[str] = set()

    def init_pages_scanned(self, url: str) -> None:
        """Init self.pages_scanned dict.

        With the list of base_urls with an empty set as its value.
        """
        domain = urllib.parse.urlparse(url).netloc
        self.pages_scanned[domain] = set()

    def is_url_in_pages_scanned(self, url: str) -> bool:
        """Return True if the url has been scanned previously."""
        with config.lock:
            domain = urllib.parse.urlparse(url).netloc
            return url in self.pages_scanned[domain]

    def add_page_scanned(self, url: str) -> None:
        """Log that a page has been scanned.

        Args:
            url (str): The speciifc URL that was tested
        """
        with config.lock:
            self.total_pages_scanned += 1
            domain = urllib.parse.urlparse(url).netloc
            if domain in self.pages_scanned:
                self.pages_scanned[domain].add(url)
            else:
                self.pages_scanned[domain] = {url}

            # Output a progress bar
            src.output.print_progress_bar(
                iteration=self.total_pages_scanned,
                total=self.est_num_pages_in_test,
                start_time=self.start_time,
            )

    def record_test_failure(self, url: str) -> None:
        """Record a test failure.

        Used to adjust est_num_pages_in_test when tests fail.
        """
        with config.lock:
            # Get how many pages were successfully scanned
            domain = urllib.parse.urlparse(url).netloc
            self.est_num_pages_in_test -= max(0, config.max_links_per_domain - len(self.pages_scanned[domain]))

            # Output a progress bar
            src.output.print_progress_bar(
                iteration=self.total_pages_scanned,
                total=self.est_num_pages_in_test,
                start_time=self.start_time,
            )
