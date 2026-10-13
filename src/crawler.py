"""Crawler.

Crawls specified websites and tests them using AuditManager
"""

import importlib
import logging
import random
from queue import SimpleQueue
from typing import cast

import selenium.common.exceptions
import urllib3
from usp.objects.sitemap import AbstractIndexSitemap
from usp.tree import sitemap_tree_for_homepage

import src.filters
import src.output
from config import Config
from config import SiteData as ConfigSiteData
from src.analytics import Analytics
from src.audit_manager import AuditManager
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser
from src.crawlable_page_validator import CrawlablePageValidator
from src.output import CSVWriter
from src.page_queue import PageQueue, QueuedPage

# pylint: disable=too-many-branches, too-many-locals


logger = logging.getLogger('cwac')

type SiteData = ConfigSiteData

# the most urls to take from a site's sitemaps, as a multiple of max_links_per_domain
SITEMAP_URLS_PER_MAX_LINK = 10


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
    self.page_validator = CrawlablePageValidator(config=self.config, analytics=self.analytics)

  def iterate_through_base_urls(self) -> None:
    """Pick URLs from url_queue, and initiates a crawl on that URL.

    This is the entry point and main loop of the crawler.
    """
    while not self.url_queue.empty():
      # Get a url off the shared queue
      with self.config.lock:
        site_data = self.url_queue.get()

      logger.info('Starting test %s', site_data['url'])

      # Crawl the url (the crawler also initiates tests)
      self.crawl(site_data, site_data['url'])

      # Restart the browser between each website
      self.browser.safe_restart()

  def get_links(self, url: str) -> list[str]:
    """Generate a list of the links on the page currently loaded in the browser.

    This function depends on browser state! It does not navigate to the page. It
    assumes the page HTML is already loaded in the browser and that the page
    loaded in the browser is the same page as the one at `url`.

    Args:
        url (str): The URL currently loaded in the browser

    Returns:
        list[str]: a list of the links on the page, which are yet to be filtered
          and validated for crawling. If an error occurs, returns an empty list.
    """
    try:
      return cast(
        list[str],
        self.browser.driver.execute_script('return [...new Set(Array.from(document.links, a => a.href))]'),
      )
    except (
      selenium.common.exceptions.WebDriverException,
      urllib3.exceptions.HTTPError,
    ) as e:
      logger.error('%s when getting links on %s', type(e).__name__, url)
      return []

  def register_audit_plugins(
    self,
    audit_manager: AuditManager,
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

      if not issubclass(audit_class, DefaultAudit):
        raise TypeError(f'Audit plugin {filename} is not a subclass of DefaultAudit')

      audit_manager.register_audit(
        audit_name=filename,
        audit_class=audit_class,
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
    audit_manager = AuditManager(config=self.config, browser=self.browser)

    # Counts number of test failures
    test_failures = 0

    # Counts number of pages scanned
    pages_scanned = 0

    queue = PageQueue()
    queue.push(QueuedPage(base_url, base_url))

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

      match self.page_validator.validate(site_data=site_data, base_url=base_url, parent_url=parent_url, url=url):
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

      self.register_audit_plugins(audit_manager)
      test_success = audit_manager.run_audits(url, site_data)

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

        for queued_page in urls_from_sitemap:
          queue.push(queued_page)
        has_crawled_sitemap = True

      links = self.get_links(url)

      for new_link in links:
        queue.push(QueuedPage(url, new_link))

    self.analytics.record_test_failure(base_url)
    self.record_pages_scanned(site_data, pages_scanned)
    if self.config.max_links_per_domain != 1:
      logger.info('Crawl exhausted all links %s', base_url)

  def __crawl_sitemap(self, url: str) -> list[QueuedPage]:
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

    # cap how many urls we take from the sitemap, as some sites have millions of
    # them, which makes the crawl queue very slow and memory hungry
    limit = self.config.max_links_per_domain * SITEMAP_URLS_PER_MAX_LINK

    queued_pages: list[QueuedPage] = []
    num_found = 0

    # use reservoir sampling so that if there are more urls than the limit, we
    # keep a uniformly random selection of them rather than whichever come first
    for sitemap in tree.all_sitemaps():
      # skip index sitemaps since they yield the pages of their sub-sitemaps,
      # which are already included as part of "all sitemaps"
      if isinstance(sitemap, AbstractIndexSitemap):
        continue

      for page in sitemap.all_pages():
        num_found += 1
        if len(queued_pages) < limit:
          queued_pages.append(QueuedPage(sitemap.url, page.url))
        else:
          # these random numbers are not used for security or cryptographic
          # purposes so it is safe to use and 'nosec' suppresses bandit
          index = random.randrange(num_found)  # nosec # noqa: S311
          if index < limit:
            queued_pages[index] = QueuedPage(sitemap.url, page.url)

    if num_found > limit:
      logger.info('Found %i urls from sitemaps for %s, randomly selected %i of them', num_found, url, limit)

    return queued_pages

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
