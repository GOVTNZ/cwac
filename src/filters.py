"""URL filters."""

import logging
import urllib.parse
from typing import Any, TypedDict

import requests

from config import Config

logger = logging.getLogger('cwac')

DISALLOWED_FILE_TYPES = (
  '.xml',
  '.gif',
  '.csv',
  '.xls',
  '.xlsx',
  '.dmg',
  '.exe',
  '.wmv',
  '.wma',
  '.flv',
  '.ppt',
  '.py',
  '.pptx',
  '.jpg',
  '.jpeg',
  '.png',
  '.avi',
  '.mov',
  '.m4a',
  '.m4v',
  '.mp3',
  '.mp4',
  '.doc',
  '.docx',
  '.pdf',
  '.swf',
  '.jar',
  '.tar.gz',
  '.zip',
  '.iso',
  '.crt',
  '.crl',
  '.pem',
  '.key',
  '.pfx',
  '.p12',
  '.der',
  '.cer',
  '.psd',
  '.ai',
  '.eps',
  '.ttf',
  '.otf',
  '.woff',
  '.woff2',
  '.eot',
  '.svg',
  '.srt',
  '.wav',
  '.brf',
  '.txt',
)


def has_allowed_file_type(url: str) -> bool:
  """Check that the URL's path does not end with a disallowed file extension.

  Args:
      url (str): A URL to check

  Returns:
      bool: True if URL is allowed, else False
  """
  if urllib.parse.urlparse(url).path.lower().endswith(DISALLOWED_FILE_TYPES):
    logger.info('URL filtered out due to having a disallowed file extension %s', url)
    return False
  return True


def url_filter_by_header_content_type(url: str, headers: dict[Any, Any]) -> bool:
  """Filter out when invalid Content-Type is set.

  Args:
      url (str): url that headers were retrieved from
      headers (dict[Any, Any]): headers from a server

  Returns:
      bool: True if headers are ok, else False
  """
  try:
    headers = {k.lower(): v for k, v in headers.items()}
    if not headers['content-type'].startswith('text/html'):
      logger.info(
        'URL filtered due to a non-text/html response %s: %s',
        url,
        headers['content-type'],
      )
      return False
  except KeyError:
    logger.info(
      'URL filtered due to not being able to determine content type %s: %s',
      url,
      headers,
    )
    return False

  return True


class UrlData(TypedDict):
  """Data about a request made for a particular url."""

  status_code: int
  final_url: str
  headers: dict[str, str]


def process_url_headers(config: Config, url: str, supports_head_requests: bool = True) -> UrlData:
  """Process a URL by handling the headers.

  It does the following:
      - checks HTTP status code
      - Redirects and resolves to final_url

  Args:
      config (Config): configuration details
      url (str): A URL to filter
      supports_head_requests (bool): whether the URL supports HEAD requests

  Returns:
      UrlData: A dict of status_code, final_url, and headers from the final request

  Performance:
      Up to 3 request attempts; each attempt may follow redirects.
  """
  timeout = (10, 10)
  final_url = url
  method = 'head'

  if not supports_head_requests:
    method = 'get'
    logger.info(
      '%s is marked as not supporting HEAD requests, using GET instead to check headers',
      url,
    )

  # Try to get the headers 3 times
  for i in range(3):
    try:
      # Set the user agent string
      ua_string = {'User-Agent': config.user_agent}
      headers = requests.request(method, url, headers=ua_string, timeout=timeout, allow_redirects=True)

      # this response does not really make sense, but if it does happen we might as well skip remaining retries
      if headers.status_code == 405 and method != 'get':
        method = 'get'
        logger.warning(
          '%s does not support HEAD requests, retrying with GET (status code %i %s)',
          url,
          headers.status_code,
          headers.reason,
        )
        continue

      final_url = headers.url
      logger.info('%s has status code %i (%s)', url, headers.status_code, headers.reason)
      break
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception('Failed to get headers; attempt: %d, %s', i + 1, url)
      if i == 2:
        logger.warning('Giving up on headers check; attempt: %d, %s', i + 1, url)
        return {'status_code': -1, 'final_url': url, 'headers': {}}

  return {
    'status_code': headers.status_code,
    'final_url': final_url,
    'headers': dict(headers.headers),
  }
