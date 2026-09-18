"""Crawler.

Crawls specified websites and tests them using AuditManager
"""

import importlib
import logging
import random
import time
import urllib
import urllib.parse
from queue import SimpleQueue

import requests
import selenium.common.exceptions
from bs4 import BeautifulSoup
from usp.tree import sitemap_tree_for_homepage

import src.filters
import src.output
from config import Config
from config import SiteData as ConfigSiteData
from src.analytics import Analytics
from src.audit_manager import AuditManager
from src.browser import Browser
from src.crawlable_page_validator import CrawlablePageValidator
from src.output import CSVWriter

# pylint: disable=too-many-branches, too-many-statements, too-many-locals


logger = logging.getLogger('cwac')

type SiteData = ConfigSiteData


class Crawler:
  """Crawls URLs and initiates tests on the pages."""

  def __init__(
    self,
    config: Config,
    browser: Browser,
    url_queue: SimpleQueue[SiteData],
    analytics: Analytics,
  ) -> None:
    """Initialise various vars."""
    self.config = config
    self.browser = browser
    self.url_queue = url_queue
    self.analytics = analytics
    self.url_filter = src.filters.URLFilter(self.config)
    self.crawl_validator = CrawlablePageValidator(config=self.config, analytics=self.analytics)

  def iterate_through_base_urls(self) -> None:
    """Pick URLs from url_queue, and initiates a crawl on that URL.

    This is the entry point and main loop of the crawler.
    """
    # Count how many URls have been iterated through
    url_iteration = 0
    while not self.url_queue.empty():
      url_iteration += 1

      # Get a url off the shared queue
      with self.config.lock:
        site_data = self.url_queue.get()

      logger.info('Starting test %s', site_data['url'])

      # Crawl the url (the crawler also initiates tests)
      self.crawl(site_data, site_data['url'])

      # Restart the browser between each website
      self.browser.safe_restart()

  def resolve_final_url(self, url: str) -> str:
    """Resolve the final URL after redirects.

    Args:
        url (str): URL to resolve

    Returns:
        str: resolved URL

    Performance:
        1 HTTP request.
    """
    # Get the final URL after redirects
    try:
      ua_string = {'User-Agent': self.config.user_agent}
      response = requests.get(url, headers=ua_string, timeout=(10, 10))
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception('Failed to get final URL %s', url)

    if response.url != url:
      logger.info('URL %s resolved to %s', url, response.url)
    return str(response.url)

  def handle_base_element(self, url: str) -> str:
    """Compare given URL and `<base>` URL, returning the most suitable one for resolving relative URLs.

    If a URL from `<base>` is found and it has the same domain and protocol as
    the `url` provided, return that URL. Otherwise, we conclude that we can't do
    better than the given `url` so we return it.

    This function depends on browser state!. It does not navigate to the page.
    It assumes the appropriate page is already loaded in the browser.
    """
    base_element = url
    try:
      base_element = self.browser.get_base_uri()
    except Exception:
      logger.exception('Failed to get <base> element %s', url)
      return url

    # Check that the base_element has same domain as base_url
    if not src.filters.url_filter_not_same_domain(base_element, url):
      logger.info(
        'Found <base> element %s on page but rejecting it because it has a different domain than: %s',
        base_element,
        url,
      )
      return url

    # Check that the protocol is equal between base_element and url
    if not src.filters.url_filter_same_protocol(base_element, url):
      logger.info(
        'Found <base> element %s on page but rejecting it because it has a different protocol than: %s',
        base_element,
        url,
      )
      return url

    return base_element

  def get_links(self, base_url: str, url: str) -> list[str]:
    """Generate a list of viable links for crawling from the page currently loaded in the browser.

    This function depends on browser state! It does not navigate to the page. It
    assumes the page HTML is already loaded in the browser and that the page
    loaded in the browser is the same page as the one at `url`.

    Args:
        base_url (str): The base URL from the input CSV used for this crawl. Any
          URLs found outside the scope of this URL are rejected.
        url (str): The URL currently loaded in the browser

    Returns:
        list[str]: a list of links on the page which are within the scope of the
          base_url and pass all filters. If an error occurs, returns an empty
          list.
    """
    try:
      soup = BeautifulSoup(self.browser.driver.page_source, 'lxml')
    except selenium.common.exceptions.TimeoutException:
      logger.exception('Failed to get page source, TimeoutException%s', url)
      return []
    links = []

    all_a_elements = soup.find_all('a', href=True)

    # Handles if <base> element is manipulating relative URLs
    # otherwise, it is simply the 'url' value.
    base_uri = self.handle_base_element(url)

    for new_url in all_a_elements:
      # Compiles the full URL
      href = new_url.get('href').strip()
      try:
        href = urllib.parse.urljoin(base_uri, href)
      except ValueError:
        logger.exception('Failed to join URL %s %s', base_uri, href)
        continue

      # Run a range of filters on the URL
      if not self.url_filter.run_url_filters(href):
        continue

      # If URL is not on the same domain, skip it
      if not src.filters.url_filter_not_same_domain(href, base_url):
        continue

      # If URL has been scanned previously, skip it
      # if self.analytics.is_url_in_pages_scanned(href):
      #    continue

      if len(href) > 2 and base_url == href[:-1]:
        logger.info(
          'get_links skipped due to equality of: %s %s',
          base_url,
          href,
        )
        continue
      links.append(href)

    return links

  def register_audit_plugins(
    self,
    audit_manager: AuditManager,
    new_link: str,
    site_data: SiteData,
  ) -> None:
    """Register audit plugins with AuditManager.

    Args:
        audit_manager (AuditManager): AuditManager instance
        new_link (str): the link to be audited
        site_data (dict[Any, Any]): contains info about the site
    """
    for filename, audit_config in self.config.audit_plugins.items():
      # Use importlib to dynamically import audit plugins specified
      # inside config.json.
      # audit plugins must be placed inside src/audit_plugins

      # Unpack the config for the audit,
      # and skip the audit if the second arg
      # in config.json for the audit is False
      should_run: bool = audit_config['enabled']
      if not should_run:
        continue

      audit_module = importlib.import_module(f'src.audit_plugins.{filename}')
      audit_class = getattr(audit_module, self.config.audit_plugins[filename]['class_name'])
      audit_manager.register_audit(
        audit_name=filename,
        audit_class=audit_class,
        url=new_link,
        site_data=site_data,
        viewport_size=self.browser.get_window_size(),
      )

  def crawl(self, site_data: SiteData, base_url: str) -> None:  # noqa: PLR0912, PLR0915
    """Crawls a domain and executes the AuditManager.

    Sanitises the URL and checks if it should be crawled by checking:

    - Does the URL pass the URL filters?
    - Have we already scanned this URL?
    - Have we hit our maximum number of pages to scan for this domain?
    - Is the URL allowed by robots.txt?
    - Is the URL within the scope of the base_url?

    If the URL passes all checks, it is passed to `AuditManager` for testing.

    This function expects that AuditManager will exit with the URL's page fully
    loaded.

    After audits are complete, this function scrapes the page for new links and
    adds them to the queue for crawling.

    Args:
        site_data (SiteData): contains info about the site
        base_url (str): the first url to crawl
    """
    action = 'crawl'
    if self.config.max_links_per_domain == 1:
      action = 'visit'
    logger.info('Starting %s of %s', action, base_url)

    # Create an AuditManager instance
    audit_manager = AuditManager(config=self.config, browser=self.browser, analytics=self.analytics)

    # Counts number of test failures
    test_failures = 0

    # Counts number of pages scanned
    pages_scanned = 0

    # queue element: (parent_url, url)
    queue = RandomQueue[tuple[str, str]]()
    queue.push((base_url, base_url))

    # track visited urls
    visited = {base_url}

    # Filter and sanitise the initial URL
    if not self.url_filter.run_url_filters(base_url):
      self.record_pages_scanned(site_data, pages_scanned)
      logger.error('base_url was filtered out! %s', base_url)
      return

    has_crawled_sitemap = not self.config.crawl_sitemaps

    while queue:
      parent_url, url = queue.pop()

      if pages_scanned >= self.config.max_links_per_domain:
        logger.info('Max pages scanned reached %s', base_url)
        break

      # Delay
      time.sleep(self.config.delay_between_page_loads)

      match self.crawl_validator.validate(site_data=site_data, base_url=base_url, parent_url=parent_url, url=url):
        case None:
          continue
        case validated_url:
          url = validated_url

      # Write to audit_log.csv
      csv_writer = CSVWriter()
      csv_writer.append_rows(
        f'./results/{self.config.audit_name}/audit_log.csv',
        {
          **site_data['columns'],
          'base_url': site_data['url'],
          'url': url,
        },
      )

      self.register_audit_plugins(audit_manager, url, site_data)
      test_success = audit_manager.run_audits()

      if test_success:
        self.analytics.add_page_scanned(base_url, url)
        test_failures = 0
        pages_scanned += 1
      else:
        test_failures += 1
        if test_failures >= 3:
          self.analytics.record_test_failure(base_url)
          self.record_pages_scanned(site_data, pages_scanned)
          logger.error('Too many sequential test failures, skipping %s', url)
          return

      # don't bother getting links if we are only scanning one link per base url
      if self.config.max_links_per_domain == 1:
        break

      # we delay crawling the sitemap for urls until after the base_url has been
      # audited to ensure that has happened since the queue provides urls at random
      if len(queue) == 0 and not has_crawled_sitemap:
        urls_from_sitemap = self.__crawl_sitemap(base_url)

        logger.info('Found %i url%s from sitemaps', len(urls_from_sitemap), '' if len(urls_from_sitemap) == 1 else 's')

        for parent_and_url in urls_from_sitemap:
          queue.push(parent_and_url)
        has_crawled_sitemap = True

      links = self.get_links(base_url, url)

      # Add all links to the queue
      for new_link in links:
        if new_link not in visited:
          visited.add(new_link)
          queue.push((url, new_link))
      # End of queue processing loop

    self.analytics.record_test_failure(base_url)
    self.record_pages_scanned(site_data, pages_scanned)
    if self.config.max_links_per_domain != 1:
      logger.info('Crawl exhausted all links %s', base_url)

  def __crawl_sitemap(self, url: str) -> list[tuple[str, str]]:
    """Crawls the urls sitemap, if there is one.

    Performance:
        1+ HTTP requests depending on the sitemap structure and discovery path.
    """
    logger.info('Fetching sitemap for %s', url)

    try:
      tree = sitemap_tree_for_homepage(url)
    except Exception:
      logger.exception('Failed to get sitemap')
      return []

    parents_and_urls: list[tuple[str, str]] = []

    for sitemap in tree.all_sitemaps():
      parents_and_urls.extend((sitemap.url, page.url) for page in sitemap.all_pages())

    return parents_and_urls

  def record_pages_scanned(self, site_data: SiteData, pages_scanned: int) -> None:
    """Record the number of pages that were scanned for the site."""
    with self.config.lock:
      csv_writer = src.output.CSVWriter()
      csv_writer.append_rows(
        f'./results/{self.config.audit_name}/pages_scanned.csv',
        {
          **site_data['columns'],
          'base_url': site_data['url'],
          'number_of_pages': pages_scanned,
        },
      )


class RandomQueue[T]:
  """A queue that pops in random order, but biased toward 0."""

  def __init__(self) -> None:
    """Initialise the queue."""
    self.items: list[T] = []

  def __len__(self) -> int:
    """Return the length of the queue."""
    return len(self.items)

  def __str__(self) -> str:
    """Return the queue as a string."""
    return str(self.items)

  def push(self, item: T) -> None:
    """Push an item onto the queue.

    Args:
        item (T): item to push onto the queue
    """
    self.items.append(item)

  def pop(self) -> T:
    """Pop an item off the queue.

    Returns:
        T: item popped off the queue
    """
    index = self.biased_rand(len(self.items))
    return self.items.pop(index)

  def biased_rand(self, maximum: int) -> int:
    """Generate a random number with a bias towards 0.

    Args:
        maximum (int): maximum value

    Returns:
        int: random number
    """
    # these random numbers are not used for security
    # or cryptographic purposes so it is safe to use
    # and 'nosec' is added to suppress bandit warning.
    random_number = random.random()  # nosec # noqa: S311
    random_number *= random.random()  # nosec # noqa: S311
    return int(maximum * random_number)

  def clear(self) -> None:
    """Clear the queue."""
    self.items = []
