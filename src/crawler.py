"""Crawler.

Crawls specified websites and tests them using AuditManager
"""

import importlib
import logging
import posixpath
import random
import re
import time
import urllib
import urllib.robotparser
from collections import defaultdict
from queue import SimpleQueue
from typing import Any

import requests
import selenium.common.exceptions
from bs4 import BeautifulSoup

import src.audit_manager
import src.audit_plugins
import src.filters
import src.output
from config import Config
from config import SiteData as ConfigSiteData
from src.analytics import Analytics
from src.audit_manager import AuditManager
from src.browser import Browser
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
    self.drop_reasons: dict[str, int] = defaultdict(int)

  def iterate_through_base_urls(self) -> None:
    """Pick URLs from url_queue, and initiates a crawl on that URL."""
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
    """
    # Get the final URL after redirects
    try:
      ua_string = {'User-Agent': self.config.user_agent}
      response = requests.get(url, headers=ua_string, timeout=(10, 10))
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception('Failed to get final URL %s', url)
      return url

    if response.url != url:
      logger.info('URL %s resolved to %s', url, response.url)
    return str(response.url)

  def url_sanitise(self, url: str) -> str:
    """Sanitise URLs.

    Args:
        url (str): URL to be sanitised
    Returns:
        str: sanitised URL
    """
    # Parse URL with urllib.parse
    try:
      parsed_url = urllib.parse.urlparse(url)
    except ValueError as exc:
      raise ValueError('Invalid URL') from exc

    # Ensure scheme is either http or https
    if parsed_url.scheme not in ['http', 'https']:
      raise ValueError('Invalid URL scheme')

    # Save if it was trailing slash
    was_trailing_slash = url.endswith('/')

    # Encode the URL path to handle special characters
    parsed_url = parsed_url._replace(path=urllib.parse.quote(parsed_url.path, safe='/'))

    # Prevent path traversal using posixpath.normpath
    parsed_url = parsed_url._replace(path=posixpath.normpath(parsed_url.path))

    # Add trailing slash if it was there
    if was_trailing_slash and not parsed_url.path.endswith('/'):
      parsed_url = parsed_url._replace(path=parsed_url.path + '/')

    # Rebuild URL
    url = urllib.parse.urlunparse(parsed_url)

    return url

  def url_filter_prevent_intersections(self, current_base_url: str, current_url: str) -> bool:
    """Filter out when a URL intersects with another base_url.

    Prevents, for instance, https://example.com/ from being scanned
    when https://example.com/abc/ is being scanned and
    prevents https://example.com/abc/ from being scanned when
    https://example.com/ is being scanned
    """

    def normalize_url(url: str) -> str:
      """Normalize the URL for comparing."""
      parsed_url = urllib.parse.urlparse(url)

      # lowercase the protocol and domain
      scheme = parsed_url.scheme.lower()
      netloc = parsed_url.netloc.lower()

      path = parsed_url.path

      # if the path ends with a file, remove it
      if '.' in path:
        path = path[: path.rfind('/') + 1]

      # remove trailing slash
      path = path.rstrip('/')

      return f'{scheme}://{netloc}{path}'

    def is_within_scope(parent: str, candidate: str) -> bool:
      """Return True when candidate is parent or below parent path boundary."""
      if candidate == parent:
        return True
      return candidate.startswith(f'{parent}/')

    # Prepares the base_url and url for the matching algorithm
    current_base_url = normalize_url(current_base_url)
    current_url = normalize_url(current_url)

    # If the current_url does not start with the current_base_url,
    # then the url should not be scanned as it is not within the
    # scope of the current_base_url
    if not is_within_scope(current_base_url, current_url):
      logger.info(
        'URL filtered out due to not starting with base_url %s %s',
        current_base_url,
        current_url,
      )
      return False

    # Iterate through all (other) base_urls and check if the current_url
    # starts with any of them. If it does, then the current_url
    # should not be scanned as it is within the scope of another
    # base_url
    for base_url in self.analytics.base_urls:
      base_url = normalize_url(base_url)  # noqa: PLW2901
      if is_within_scope(base_url, current_url) and len(base_url) > len(current_base_url):
        logger.info(
          'URL filtered out due to being within the scope of another base_url %s %s',
          base_url,
          current_url,
        )
        return False
    return True

  def handle_base_element(self, url: str) -> str:
    """Handle the base element for relative URLs."""
    base_element = url
    try:
      base_element = self.browser.get_base_uri()
    except Exception:
      logger.exception('Failed to get base element %s', url)
      return url

    # Check that the base_element has same domain as base_url
    if not src.filters.url_filter_not_same_domain(base_element, url):
      logger.info('get_links skipped due to equality of: %s %s', base_element, url)
      return url

    # Check that the protocol is equal between base_element and url
    if not src.filters.url_filter_same_protocol(base_element, url):
      logger.info('get_links skipped due to different protocol of: %s %s', base_element, url)
      return url

    return base_element

  def get_links(self, base_url: str, url: str) -> list[str]:
    """Get a list of (viable) links on a page."""
    try:
      soup = BeautifulSoup(self.browser.driver.page_source, 'lxml')
    except selenium.common.exceptions.TimeoutException:
      logger.exception('Failed to get page source, TimeoutException%s', url)
      return []
    links = []

    all_a_elements = soup.find_all('a', href=True)

    # Handles if <base> element is manipulating relative URLs
    base_uri = self.handle_base_element(url)

    for new_url in all_a_elements:
      href = new_url.get('href').strip()
      try:
        href = urllib.parse.urljoin(base_uri, href)
      except ValueError as exc:
        logger.exception('Failed to join URL %s %s %s', base_uri, href, exc)
        continue

      # Run a range of filters on the URL
      if not self.url_filter.run_url_filters(href):
        self.drop_reasons['get_links_url_filter_reject'] += 1
        continue

      # If URL is not on the same domain, skip it
      if not src.filters.url_filter_not_same_domain(href, base_url):
        self.drop_reasons['get_links_cross_domain'] += 1
        continue

      if len(href) > 2 and base_url == href[:-1]:
        logger.info('get_links skipped due to equality of: %s %s', base_url, href)
        self.drop_reasons['get_links_base_url_equality'] += 1
        continue

      links.append(href)

    return links

  def register_audit_plugins(
    self,
    audit_manager: AuditManager,
    new_link: str,
    site_data: SiteData,
  ) -> None:
    """Register audit plugins with AuditManager."""
    for filename, audit_config in self.config.audit_plugins.items():
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

  def are_url_headers_acceptable(self, base_url: str, parent_url: str, url_data: src.filters.UrlData) -> bool:
    """Check if the URL has acceptable headers."""
    ok_status_codes = [200, 202, 301, 302, 307, 308]
    if url_data['status_code'] not in ok_status_codes:
      logger.info(
        'URL filtered out due to bad http status_code: %s %i',
        url_data['final_url'],
        url_data['status_code'],
      )
      csv_writer = src.output.CSVWriter()
      csv_writer.add_row(
        {
          'base_url': base_url,
          'parent_url': parent_url,
          'url': url_data['final_url'],
          'status_code': url_data['status_code'],
        }
      )
      if self.config.record_unexpected_response_codes:
        csv_writer.write_csv_file(f'./results/{self.config.audit_name}/unexpected_response_codes.csv')

      return False
    return src.filters.url_filter_by_header_content_type(url_data['final_url'], url_data['headers'])

  def fetch_robots_txt(self, robots_txt_url: str) -> str:
    """Fetches a robots.txt file from a domain."""
    try:
      logger.info('Fetching robots.txt %s', robots_txt_url)
      response = requests.get(robots_txt_url, headers={'User-Agent': self.config.user_agent}, timeout=10)
      response.raise_for_status()

      is_content_type_set = 'Content-Type' in response.headers
      if is_content_type_set and not re.search('^text/plain(?:;|$)', response.headers['Content-Type'], re.IGNORECASE):
        raise ValueError(f'robots.txt has invalid Content-Type {robots_txt_url} {response.headers["Content-Type"]}')
    except requests.exceptions.RequestException as exc:
      logger.error('Failed to fetch robots.txt %s', robots_txt_url)
      raise exc

    logger.info('Fetched robots.txt %s', robots_txt_url)

    robots_txt_content = response.text

    if len(robots_txt_content) > 1024 * 500:
      logger.warning('robots.txt file is too large (>500 KB) on %s', robots_txt_url)
      raise ValueError(f'robots.txt file is too large (>500 KB) on {robots_txt_url}')

    file = robots_txt_content.encode('utf-8', errors='ignore').decode('utf-8')
    return file

  def is_url_allowed_by_robots_txt(self, url: str) -> bool:
    """Checks if a URL's robots.txt allows CWAC."""
    if not self.config.follow_robots_txt:
      return True

    protocol, domain = urllib.parse.urlparse(url)[:2]

    if domain in self.config.robots_txt_cache:
      robot_parser = self.config.robots_txt_cache[domain]
      logger.info('Using cached robots.txt for %s', domain)
      result = robot_parser.can_fetch(self.config.user_agent_product_token, url)
      logger.info('robots.txt result for %s was %s', url, 'allow' if result else 'disallow')
      return result

    robot_parser = urllib.robotparser.RobotFileParser()

    try:
      robots_txt = self.fetch_robots_txt(f'{protocol}://{domain}/robots.txt')
      robot_parser.parse(robots_txt.splitlines())
    except (requests.exceptions.RequestException, ValueError):
      robot_parser.parse('')
      self.config.robots_txt_cache[domain] = robot_parser
      logger.exception('Failed to fetch or parse robots.txt - default to allow! %s', domain)
      return True

    self.config.robots_txt_cache[domain] = robot_parser
    result = robot_parser.can_fetch(self.config.user_agent_product_token, url)
    logger.info('robots.txt result for %s was %s', url, 'allow' if result else 'disallow')
    return result

  def discovery_key(self, url: str) -> str:
    """Conservative dedupe key for crawl frontier."""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or '/'
    query = parsed.query
    return urllib.parse.urlunparse((scheme, netloc, path, '', query, ''))

  def crawl(self, site_data: SiteData, base_url: str) -> None:  # noqa: PLR0912, PLR0915
    """Crawls a domain and executes the AuditManager."""
    action = 'crawl'
    if self.config.max_links_per_domain == 1:
      action = 'visit'
    logger.info('Starting %s of %s', action, base_url)

    audit_manager = AuditManager(config=self.config, browser=self.browser, analytics=self.analytics)

    # Coverage metrics
    urls_visited = 0
    audits_passed = 0
    audits_failed = 0

    # queue element: (parent_url, url, depth)
    queue = RandomQueue()
    queue.push((base_url, base_url, 0))

    # track visited urls using conservative discovery key
    visited = {self.discovery_key(base_url)}
    self.drop_reasons = defaultdict(int)

    # Filter and sanitise the initial URL
    if not self.url_filter.run_url_filters(base_url):
      self.drop_reasons['base_url_filtered'] += 1
      self.record_pages_scanned(site_data, audits_passed)
      self.record_crawl_metrics(site_data, urls_visited, audits_passed, audits_failed)
      logger.error('base_url was filtered out! %s', base_url)
      return

    while queue:
      parent_url, url, depth = queue.pop()

      # Keep cap semantics tied to successful audit count
      if audits_passed >= self.config.max_links_per_domain:
        logger.info('Max pages scanned reached %s', base_url)
        break

      # Delay
      time.sleep(self.config.delay_between_page_loads)

      # Filter/sanitise the URL
      try:
        url = self.url_sanitise(url)
      except ValueError:
        self.drop_reasons['sanitize_error'] += 1
        continue

      # Check if URL is allowed by robots.txt
      if not self.is_url_allowed_by_robots_txt(url):
        self.drop_reasons['robots_disallow'] += 1
        logger.info('URL disallowed by robots.txt %s', url)
        continue

      # process_url_headers returns a dict with status_code/final_url
      if self.config.perform_header_check:
        url_data = src.filters.process_url_headers(
          self.config,
          url,
          supports_head_requests=site_data['supports_head'],
        )
        url = url_data['final_url']
        if not self.are_url_headers_acceptable(base_url=base_url, parent_url=parent_url, url_data=url_data):
          self.drop_reasons['header_reject'] += 1
          continue

      if not self.url_filter.run_url_filters(url):
        self.drop_reasons['url_filter_reject'] += 1
        continue

      if not self.url_filter_prevent_intersections(base_url, url):
        self.drop_reasons['intersection_reject'] += 1
        continue

      if self.analytics.is_url_in_pages_scanned(base_url, url):
        self.drop_reasons['already_scanned'] += 1
        logger.info('URL has been scanned before %s for %s', url, base_url)
        continue

      # Count coverage once page passes crawl gates
      urls_visited += 1

      # Write to audit_log.csv
      csv_writer = CSVWriter()
      csv_writer.add_rows(
        [
          {
            'organisation': site_data['organisation'],
            'base_url': site_data['url'],
            'url': url,
            'sector': site_data['sector'],
          }
        ]
      )
      csv_writer.write_csv_file(f'./results/{self.config.audit_name}/audit_log.csv')

      self.register_audit_plugins(audit_manager, url, site_data)
      test_success = audit_manager.run_audits()

      if test_success:
        self.analytics.add_page_scanned(base_url, url)
        audits_passed += 1
      else:
        audits_failed += 1
        # keep crawling even if audits fail
        logger.warning('Audit failed for %s (continuing crawl)', url)

      # don't bother getting links if we are only scanning one link per base url
      if self.config.max_links_per_domain == 1:
        break

      links = self.get_links(base_url, url)

      # Add all links to the queue
      for new_link in links:
        link_key = self.discovery_key(new_link)
        if link_key not in visited:
          visited.add(link_key)
          queue.push((url, new_link, depth + 1))
        else:
          self.drop_reasons['frontier_duplicate'] += 1

    self.analytics.record_test_failure(base_url)
    self.record_pages_scanned(site_data, audits_passed)
    self.record_crawl_metrics(site_data, urls_visited, audits_passed, audits_failed)

    logger.info(
      'Crawl metrics for %s: visited=%d passed=%d failed=%d',
      base_url,
      urls_visited,
      audits_passed,
      audits_failed,
    )
    logger.info('Crawl drop reasons for %s: %s', base_url, dict(self.drop_reasons))

    if self.config.max_links_per_domain != 1:
      logger.info('Crawl exhausted all links %s', base_url)

  def record_pages_scanned(self, site_data: SiteData, pages_scanned: int) -> None:
    """Record successful audits for the site."""
    with self.config.lock:
      csv_writer = src.output.CSVWriter()
      csv_writer.add_rows(
        [
          {
            'organisation': site_data['organisation'],
            'base_url': site_data['url'],
            'number_of_pages': pages_scanned,
            'sector': site_data['sector'],
          }
        ]
      )
      csv_writer.write_csv_file(f'./results/{self.config.audit_name}/pages_scanned.csv')

  def record_crawl_metrics(self, site_data: SiteData, urls_visited: int, audits_passed: int, audits_failed: int) -> None:
    """Record coverage metrics separate from audit success."""
    with self.config.lock:
      csv_writer = src.output.CSVWriter()
      csv_writer.add_rows(
        [
          {
            'organisation': site_data['organisation'],
            'base_url': site_data['url'],
            'urls_visited': urls_visited,
            'audits_passed': audits_passed,
            'audits_failed': audits_failed,
            'sector': site_data['sector'],
          }
        ]
      )
      csv_writer.write_csv_file(f'./results/{self.config.audit_name}/crawl_metrics.csv')


class RandomQueue:
  """A queue that pops in random order, but biased toward 0."""

  def __init__(self) -> None:
    """Initialise the queue."""
    self.items: list[Any] = []

  def __len__(self) -> int:
    """Return the length of the queue."""
    return len(self.items)

  def __str__(self) -> str:
    """Return the queue as a string."""
    return str(self.items)

  def push(self, item: Any) -> None:
    """Push an item onto the queue."""
    self.items.append(item)

  def pop(self) -> Any:
    """Pop an item off the queue."""
    index = self.biased_rand(len(self.items))
    return self.items.pop(index)

  def biased_rand(self, maximum: int) -> int:
    """Generate a random number with a bias towards 0."""
    # these random numbers are not used for security
    random_number = random.random()  # nosec # noqa: S311
    random_number *= random.random()  # nosec # noqa: S311
    return int(maximum * random_number)

  def clear(self) -> None:
    """Clear the queue."""
    self.items = []
