"""Analytics for the scan."""

import time

import src.output
from config import Config


class Analytics:
  """Analytics that track scan statistics."""

  def __init__(self, config: Config) -> None:
    """Initialise variables."""
    self.config = config

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

    # todo: we should fill these out with actual values
    self.progress: src.output.ProgressUpdate = {
      'time': time.time(),
      'iteration': 0,
      'total': 0,
      'speed': f'{0:.2f}',
      'percent': '0',
      'elapsed': f'{0}',
      'remaining': f'{0}',
    }

  def add_base_url(self, base_url: str) -> None:
    """Add base url in preparation of it being scanned."""
    self.pages_scanned[base_url] = set()
    self.base_urls.add(base_url)

  def is_url_in_pages_scanned(self, base_url: str, url: str) -> bool:
    """Return True if the url has been scanned previously for the given base_url."""
    with self.config.lock:
      return url in self.pages_scanned[base_url]

  def add_page_scanned(self, base_url: str, url: str) -> None:
    """Log that a page has been scanned.

    Args:
        base_url (str): The base URL that the tested URL came from
        url (str): The specific URL that was tested
    """
    with self.config.lock:
      self.total_pages_scanned += 1
      self.pages_scanned.setdefault(base_url, set()).add(url)

      # Output a progress bar
      self.progress = src.output.print_progress_bar(
        config=self.config,
        iteration=self.total_pages_scanned,
        total=self.est_num_pages_in_test,
        start_time=self.start_time,
      )

  def record_test_failure(self, base_url: str) -> None:
    """Record a test failure.

    Used to adjust est_num_pages_in_test when tests fail.
    """
    with self.config.lock:
      # Get how many pages were successfully scanned
      self.est_num_pages_in_test -= max(0, self.config.max_links_per_domain - len(self.pages_scanned[base_url]))

      # Output a progress bar
      self.progress = src.output.print_progress_bar(
        config=self.config,
        iteration=self.total_pages_scanned,
        total=self.est_num_pages_in_test,
        start_time=self.start_time,
      )
