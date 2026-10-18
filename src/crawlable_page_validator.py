"""Validator for crawlable pages."""

import logging
import re
import urllib
import urllib.parse
import urllib.robotparser

import requests

import src.filters
import src.output
import src.urls
from config import Config, SiteData
from src.analytics import Analytics

logger = logging.getLogger('cwac')


class CrawlablePageValidator:
  """Validator for crawlable pages."""

  def __init__(self, config: Config, analytics: Analytics) -> None:
    """Initialise the validator."""
    self.config = config
    self.analytics = analytics
    self.url_filter = src.filters.URLFilter(config)

  def validate(self, site_data: SiteData, base_url: str, parent_url: str, url: str) -> str | None:
    """Validates that pages are crawlable.

    A page is considered crawlable if all of the following conditions are met:

    1. It passes URL filters
    2. Has not been scanned before
    3. Is allowed by robots.txt

    If `config.perform_header_check` is enabled, then the HTTP headers are fetched
    and validated.

    If a redirect is encountered during header validation, the new (final) URL
    will be re-checked.
    """
    match self._clean_and_fast_validate_url(base_url, url):
      case None:
        return None
      case clean_url:
        url = clean_url

    # If header checks are disabled then we are done so just return the
    # validated URL.
    if not self.config.perform_header_check:
      return url

    # Fetch the headers for the URL
    url_data = src.filters.process_url_headers(
      self.config,
      url,
      supports_head_requests=site_data['supports_head'],
    )

    # Now that we have the headers, verify that they are acceptable
    if not self._are_url_headers_acceptable(base_url=base_url, parent_url=parent_url, url_data=url_data):
      return None

    # If the URL has not changed after fetching headers (i.e. no redirects) then
    # we consider it valid and can return it as is.
    if url == url_data['final_url']:
      return url

    # Otherwise we need to re-validate the new (post redirects) URL
    match self._clean_and_fast_validate_url(base_url, url_data['final_url']):
      case None:
        return None
      case new_clean_url:
        url = new_clean_url

    return url

  def _clean_and_fast_validate_url(self, base_url: str, url: str) -> str | None:
    """Cleans the URL and then runs all the validations that happen before fetching headers.

    These are cheap checks, except for the robots.txt check which makes an HTTP
    request the first time a domain is checked (after which it is cached).

    Return the cleaned version of the URL if it is eligible to be crawled, otherwise None.
    """
    try:
      clean_url = src.urls.normalize_url(url)
    except ValueError:
      return None

    if not self.url_filter.run_url_filters(clean_url):
      return None

    if not self._owns_url(base_url, clean_url):
      return None

    # Check if URL has been scanned before
    if self.analytics.is_url_in_pages_scanned(base_url, clean_url):
      logger.info('URL has been scanned before %s for %s', clean_url, base_url)
      return None

    # Check if URL is allowed by robots.txt
    if not self._is_url_allowed_by_robots_txt(clean_url):
      logger.info('URL disallowed by robots.txt %s', clean_url)
      return None

    return clean_url

  def _are_url_headers_acceptable(self, base_url: str, parent_url: str, url_data: src.filters.UrlData) -> bool:
    """Check if the URL has acceptable headers.

    Args:
        base_url (str): base URL - homepage of website specified
        parent_url (str): parent URL of url
        url_data (src.filters.UrlData): url data

    Returns:
        bool: True if URL has acceptable headers, else False
    """
    ok_status_codes = [200, 202, 301, 302, 307, 308]
    if url_data['status_code'] not in ok_status_codes:
      logger.info(
        'URL filtered out due to bad http status_code: %s %i',
        url_data['final_url'],
        url_data['status_code'],
      )
      csv_writer = src.output.CSVWriter()
      csv_writer.append_rows(
        f'./results/{self.config.audit_name}/unexpected_response_codes.csv',
        {
          'base_url': base_url,
          'parent_url': parent_url,
          'url': url_data['final_url'],
          'status_code': url_data['status_code'],
        },
      )

      return False
    return src.filters.url_filter_by_header_content_type(url_data['final_url'], url_data['headers'])

  def _fetch_robots_txt(self, robots_txt_url: str) -> str:
    """Fetches a robots.txt file from a domain.

    This is a custom implementation as the standard library's
    urllib.robotparser.RobotFileParser does not appear to handle
    large file problems, non-UTF-8 chars, or Content-Type checks.

    Args:
        robots_txt_url (str): URL to fetch robots.txt from

    Returns:
        str: robots.txt file

    Performance:
        At least 1 HTTP request; redirects may cause additional requests.
    """
    # Fetch the robots.txt file
    logger.info('Fetching robots.txt %s', robots_txt_url)
    response = requests.get(robots_txt_url, headers={'User-Agent': self.config.user_agent}, timeout=10)
    response.raise_for_status()

    # Check Content-Type is text/plain (in a safe way)
    is_content_type_set = 'Content-Type' in response.headers
    if is_content_type_set and not re.search('^text/plain(?:;|$)', response.headers['Content-Type'], re.IGNORECASE):
      raise ValueError(f'robots.txt has invalid Content-Type {robots_txt_url} {response.headers["Content-Type"]}')

    logger.info('Fetched robots.txt %s', robots_txt_url)

    robots_txt_content = response.text

    # If the response is > 500 KB
    if len(robots_txt_content) > 1024 * 500:
      raise ValueError(f'robots.txt file is too large (>500 KB) on {robots_txt_url}')

    # Remove any non-UTF-8 characters
    file = robots_txt_content.encode('utf-8', errors='ignore').decode('utf-8')

    return file

  def _is_url_allowed_by_robots_txt(self, url: str) -> bool:
    """Checks if a URL's robots.txt allows CWAC.

    Args:
        url (str): URL to check

    Returns:
        bool: True if URL is allowed by robots.txt, else False (True if config disables robots.txt checks)

    Performance:
        1 HTTP request if robots.txt not yet cached for the domain.
    """
    if not self.config.follow_robots_txt:
      return True

    # Get the protocol/domain of the URL
    protocol, domain = urllib.parse.urlparse(url)[:2]

    # If the domain is in config.robots_txt_cache, use that
    if domain in self.config.robots_txt_cache:
      robot_parser = self.config.robots_txt_cache[domain]
      logger.info('Using cached robots.txt for %s', domain)
      result = robot_parser.can_fetch(self.config.user_agent_product_token, url)
      logger.info('robots.txt result for %s was %s', url, 'allow' if result else 'disallow')
      return result

    # Use urllib.robotparser to parse the robots.txt file
    robot_parser = urllib.robotparser.RobotFileParser()

    # Fetch the robots.txt file
    try:
      robots_txt = self._fetch_robots_txt(f'{protocol}://{domain}/robots.txt')
      robot_parser.parse(robots_txt.splitlines())
    except (requests.exceptions.RequestException, ValueError):
      robot_parser.parse('')
      self.config.robots_txt_cache[domain] = robot_parser
      logger.exception('Failed to fetch or parse robots.txt - default to allow! %s', domain)
      return True

    # Cache the robotparser object
    self.config.robots_txt_cache[domain] = robot_parser

    # Check if the URL is allowed by robots.txt
    result = robot_parser.can_fetch(self.config.user_agent_product_token, url)

    # Log the outcome
    logger.info('robots.txt result for %s was %s', url, 'allow' if result else 'disallow')

    return result

  def _split_scope(self, url: str) -> tuple[tuple[str, str], list[str]]:
    """Split a normalized url into its origin and its path segments, ignoring leading and trailing slashes."""
    parts = urllib.parse.urlsplit(url)

    path = parts.path.removeprefix('/').removesuffix('/')

    return (parts.scheme, parts.netloc), path.split('/') if path else []

  def _split_base_url_scope(self, base_url: str) -> tuple[tuple[str, str], list[str]]:
    """Split a normalized base url into its origin and its path segments, treating a url for a file as its directory."""
    origin, segments = self._split_scope(base_url)

    # base urls that point at a file (e.g. https://example.com/a/index.html) are
    # treated as being for the directory containing that file
    if segments and '.' in segments[-1] and not urllib.parse.urlsplit(base_url).path.endswith('/'):
      segments = segments[:-1]

    return origin, segments

  def _is_url_within_base_url(self, base_url: str, url: str) -> bool:
    """Return True if the url has the same origin as the base url, and its path starts with the base url's path.

    Paths are compared by segment, and both urls are expected to have already been normalized.
    """
    base_origin, base_segments = self._split_base_url_scope(base_url)
    url_origin, url_segments = self._split_scope(url)

    return base_origin == url_origin and url_segments[: len(base_segments)] == base_segments

  def _owns_url(self, current_base_url: str, current_url: str) -> bool:
    """Check if the base url is the most appropriate owner of the current url.

    A url is owned by a base url if it is within that base url and not also within
    another base url with more path segments, e.g. if both https://example.com/ and
    https://example.com/abc are base urls, then https://example.com/abc/def is owned
    by https://example.com/abc rather than https://example.com/

    Args:
        current_base_url (str): The base url currently being crawled
        current_url (str): The url to check

    Returns:
        bool: True if the current base url owns the url, else False
    """
    if not self._is_url_within_base_url(current_base_url, current_url):
      logger.info(
        'URL filtered out due to not being within base_url %s %s',
        current_base_url,
        current_url,
      )
      return False

    _, current_base_segments = self._split_base_url_scope(current_base_url)

    # iterate through all (other) base_urls to see if there's a deeper
    # base_url that owns this url
    for base_url in self.analytics.base_urls:
      if not self._is_url_within_base_url(base_url, current_url):
        continue

      _, base_url_segments = self._split_base_url_scope(base_url)

      # at this point the base url with the most path segments wins
      if len(base_url_segments) > len(current_base_segments):
        logger.info(
          'URL filtered out due to being within the scope of another base_url %s %s',
          base_url,
          current_url,
        )
        return False
    return True
