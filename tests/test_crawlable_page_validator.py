"""Tests for crawlable page validation."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
import requests
import responses
from responses import matchers

from config import Config, SiteData
from src.analytics import Analytics
from src.crawlable_page_validator import CrawlablePageValidator

BASE_URL = 'https://example.com/'
PARENT_URL = 'https://example.com/parent/'
SITE_DATA: SiteData = {'url': BASE_URL, 'supports_head': True, 'columns': {}}


@pytest.fixture(name='config')
def fixture_config() -> SimpleNamespace:
  """Return the minimum configuration used by the validator."""
  return SimpleNamespace(
    audit_name='test-audit',
    follow_robots_txt=False,
    only_allow_https=True,
    perform_header_check=False,
    record_unexpected_response_codes=False,
    robots_txt_cache={},
    url_lookup={'example.com'},
    user_agent='cwac-test',
    user_agent_product_token='cwac-test',  # noqa: S106
  )


@pytest.fixture(name='analytics')
def fixture_analytics() -> SimpleNamespace:
  """Return analytics with no previously scanned URLs."""
  return SimpleNamespace(
    base_urls={BASE_URL},
    is_url_in_pages_scanned=Mock(return_value=False),
  )


@pytest.fixture(name='validator')
def fixture_validator(config: SimpleNamespace, analytics: SimpleNamespace) -> CrawlablePageValidator:
  """Build a validator with lightweight collaborators."""
  return CrawlablePageValidator(cast(Config, config), cast(Analytics, analytics))


@pytest.fixture(name='mocked_responses', autouse=True)
def fixture_mocked_responses() -> Iterator[responses.RequestsMock]:
  """Intercept HTTP requests, failing on any that have not been registered."""
  with responses.RequestsMock() as rsps:
    yield rsps


def test_validate_returns_sanitised_url_without_header_check(validator: CrawlablePageValidator) -> None:
  """Returns a crawlable URL when header checks are disabled."""
  assert (
    validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/a/../page') == 'https://example.com/page'
  )


@pytest.mark.parametrize('perform_header_check', [False, True])
def test_validate_rejects_invalid_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  perform_header_check: bool,
) -> None:
  """Rejects URLs with an unsupported scheme without making any requests."""
  config.perform_header_check = perform_header_check

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'ftp://example.com/file') is None
  assert len(mocked_responses.calls) == 0


@pytest.mark.parametrize('perform_header_check', [False, True])
def test_validate_rejects_url_outside_base_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  perform_header_check: bool,
) -> None:
  """Rejects URLs outside the configured crawl scope without making any requests."""
  config.perform_header_check = perform_header_check

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://other.example/page') is None
  assert len(mocked_responses.calls) == 0


@pytest.mark.parametrize('perform_header_check', [False, True])
def test_validate_rejects_previously_scanned_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  analytics: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  perform_header_check: bool,
) -> None:
  """Rejects URLs already recorded as scanned without making any requests."""
  config.perform_header_check = perform_header_check
  analytics.is_url_in_pages_scanned.return_value = True

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') is None
  assert len(mocked_responses.calls) == 0


def test_validate_skips_header_processing_when_disabled(
  validator: CrawlablePageValidator,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Does not fetch headers when header checks are disabled."""
  validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page')

  assert len(mocked_responses.calls) == 0


def test_validate_returns_url_with_acceptable_headers(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Returns the URL when the response status and content type are acceptable."""
  config.perform_header_check = True
  mocked_responses.head(
    'https://example.com/page',
    content_type='text/html; charset=utf-8',
    match=[matchers.header_matcher({'User-Agent': 'cwac-test'})],
  )

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') == 'https://example.com/page'
  assert len(mocked_responses.calls) == 1


def test_validate_uses_get_when_site_does_not_support_head(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Fetches headers with a GET request when the site does not support HEAD."""
  config.perform_header_check = True
  mocked_responses.get('https://example.com/page', content_type='text/html')

  result = validator.validate(
    {**SITE_DATA, 'supports_head': False},
    BASE_URL,
    PARENT_URL,
    'https://example.com/page',
  )

  assert result == 'https://example.com/page'


@pytest.mark.parametrize('status', [404, 500])
def test_validate_rejects_unacceptable_status_code(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  status: int,
) -> None:
  """Rejects a response with an unsupported status code."""
  config.perform_header_check = True
  mocked_responses.head('https://example.com/page', status=status, content_type='text/html')

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') is None


@pytest.mark.parametrize(
  'content_type',
  [
    pytest.param('application/pdf', id='non-html'),
    pytest.param(None, id='missing'),
  ],
)
def test_validate_rejects_unacceptable_content_type(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  content_type: str | None,
) -> None:
  """Rejects a response that is not HTML."""
  config.perform_header_check = True
  mocked_responses.head('https://example.com/page', content_type=content_type)

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') is None


def test_validate_revalidates_redirected_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Revalidates the final URL after a redirect."""
  config.perform_header_check = True
  mocked_responses.head('https://example.com/start', status=301, headers={'Location': '/final'})
  mocked_responses.head('https://example.com/final', content_type='text/html')

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/start') == 'https://example.com/final'


def test_validate_rejects_redirect_to_previously_scanned_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  analytics: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Rejects a redirect whose final URL has already been scanned."""
  config.perform_header_check = True
  analytics.is_url_in_pages_scanned.side_effect = lambda _base_url, url: url == 'https://example.com/final'
  mocked_responses.head('https://example.com/start', status=302, headers={'Location': '/final'})
  mocked_responses.head('https://example.com/final', content_type='text/html')

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/start') is None


def test_validate_rejects_redirect_outside_scope(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Rejects a redirect whose final URL is outside the crawl scope."""
  config.perform_header_check = True
  mocked_responses.head('https://example.com/start', status=302, headers={'Location': 'https://other.example/final'})
  mocked_responses.head('https://other.example/final', content_type='text/html')

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/start') is None


def test_robots_txt_is_cached_and_reused(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Fetches robots.txt once per domain and reuses it for subsequent checks."""
  config.follow_robots_txt = True
  robots_txt = mocked_responses.get(
    'https://example.com/robots.txt',
    body='User-agent: *\nDisallow: /private',
    content_type='text/plain',
    match=[matchers.header_matcher({'User-Agent': 'cwac-test'})],
  )

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') == 'https://example.com/page'
  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/private/page') is None

  assert robots_txt.call_count == 1


@pytest.mark.parametrize(
  'content_type',
  [
    pytest.param(None, id='missing'),
    pytest.param('text/plain', id='plain'),
    pytest.param('TEXT/PLAIN; charset=utf-8', id='with-charset'),
  ],
)
def test_robots_txt_disallows_matching_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  content_type: str | None,
) -> None:
  """Honors a robots.txt disallow rule when the Content-Type is plain text or not set."""
  config.follow_robots_txt = True
  mocked_responses.get(
    'https://example.com/robots.txt',
    body='User-agent: *\nDisallow: /private',
    content_type=content_type,
  )

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/private/page') is None


@pytest.mark.parametrize(
  ('content_type', 'status', 'padding'),
  [
    pytest.param('text/html', 200, 0, id='invalid-content-type'),
    pytest.param('text/plainish', 200, 0, id='similar-content-type'),
    pytest.param('text/plain', 500, 0, id='http-error'),
    pytest.param('text/plain', 200, 1024 * 500, id='too-large'),
  ],
)
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_robots_txt_defaults_to_allow_when_unusable(  # noqa: PLR0913, PLR0917
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  content_type: str,
  status: int,
  padding: int,
) -> None:
  """Allows all URLs, and caches that result, when robots.txt cannot be used."""
  config.follow_robots_txt = True
  robots_txt = mocked_responses.get(
    'https://example.com/robots.txt',
    body='User-agent: *\nDisallow: /private\n' + '#' * padding,
    content_type=content_type,
    status=status,
  )

  assert (
    validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/private/page')
    == 'https://example.com/private/page'
  )
  assert (
    validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/private/other')
    == 'https://example.com/private/other'
  )

  assert robots_txt.call_count == 1


def test_robots_txt_defaults_to_allow_when_request_fails(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Allows URLs when robots.txt cannot be fetched."""
  config.follow_robots_txt = True
  mocked_responses.get(
    'https://example.com/robots.txt',
    body=requests.exceptions.ConnectionError('connection refused'),
  )

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') == 'https://example.com/page'
