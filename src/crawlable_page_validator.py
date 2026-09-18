"""Validator for crawlable pages."""

import logging
import posixpath
import re
import urllib
import urllib.parse
import urllib.robotparser

import requests

import src.filters
import src.output
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
    """
    match self._fast_validations(base_url, url):
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
    match self._fast_validations(base_url, url_data['final_url']):
      case None:
        return None
      case new_clean_url:
        url = new_clean_url

    return url

  def _fast_validations(self, base_url: str, url: str) -> str | None:
    """Run all the validations that do not require HTTP requests.

    Return the crawlable version of the URL if it is eligible, otherwise None.
    """
    try:
      clean_url = self._url_sanitise(url)
    except ValueError:
      return None

    if not self.url_filter.run_url_filters(clean_url):
      return None

    # Confines to URLs that are within the scope of the base_url
    # and prevents URLs that intersect with another base_url
    # (useful for multiple websites on the same domain)
    if not self._url_filter_prevent_intersections(base_url, clean_url):
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
      if self.config.record_unexpected_response_codes:
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
        1 HTTP request.
    """
    # Fetch the robots.txt file
    try:
      logger.info('Fetching robots.txt %s', robots_txt_url)
      response = requests.get(robots_txt_url, headers={'User-Agent': self.config.user_agent}, timeout=10)
      response.raise_for_status()

      # Check Content-Type is text/plain (in a safe way)
      is_content_type_set = 'Content-Type' in response.headers
      if is_content_type_set and not re.search('^text/plain(?:;|$)', response.headers['Content-Type'], re.IGNORECASE):
        raise ValueError(f'robots.txt has invalid Content-Type {robots_txt_url} {response.headers["Content-Type"]}')
    except requests.exceptions.RequestException:
      logger.error('Failed to fetch robots.txt %s', robots_txt_url)
      raise

    logger.info('Fetched robots.txt %s', robots_txt_url)

    robots_txt_content = response.text

    # If the response is > 500 KB
    if len(robots_txt_content) > 1024 * 500:
      logger.warning('robots.txt file is too large (>500 KB) on %s', robots_txt_url)
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

  def _url_filter_prevent_intersections(self, current_base_url: str, current_url: str) -> bool:
    """Filter out when a URL intersects with another base_url.

    Prevents, for instance, https://example.com/ from being scanned
    when https://example.com/abc/ is being scanned and
    prevents https://example.com/abc/ from being scanned when
    https://example.com/ is being scanned

    Args:
        url (str): A URL to filter

    Returns:
        bool: True if URL is valid, else False
    """
    # Prepares the base_url and url for the matching algorithm
    current_base_url = self._normalize_url(current_base_url)
    current_url = self._normalize_url(current_url)

    # If the current_url does not start with the current_base_url,
    # then the url should not be scanned as it is not within the
    # scope of the current_base_url
    if not current_url.startswith(current_base_url):
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
      base_url = self._normalize_url(base_url)  # noqa: PLW2901
      if current_url.startswith(base_url) and len(base_url) > len(current_base_url):
        # If the current_url starts with a base_url that is longer
        # this means that the current_url is within the scope of
        # another base_url that is more specific than current_base_url
        logger.info(
          'URL filtered out due to being within \
                            the scope of another base_url %s %s',
          base_url,
          current_url,
        )
        return False
    return True

  def _normalize_url(self, url: str) -> str:
    """Normalize a URL for comparison.

    This includes:
      - making the url protocol and domain lowercase
      - removing files from the path
      - removing trailing slashes

    E.g. HTTPS://MyCoolSite.com/abc/def.html -> https://mycoolsite.com/abc

    Args:
        url (str): URL to normalize

    Returns:
        str: normalized URL
    """
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

  def _url_sanitise(self, url: str) -> str:
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
