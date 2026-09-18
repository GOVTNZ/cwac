"""Tests for crawlable page validation."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from src.crawlable_page_validator import CrawlablePageValidator

BASE_URL = 'https://example.com/'
PARENT_URL = 'https://example.com/parent/'
SITE_DATA = {'url': BASE_URL, 'supports_head': True, 'columns': {}}


@pytest.fixture
def config() -> SimpleNamespace:
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


@pytest.fixture
def analytics() -> SimpleNamespace:
  """Return analytics with no previously scanned URLs."""
  return SimpleNamespace(
    base_urls={BASE_URL},
    is_url_in_pages_scanned=Mock(return_value=False),
  )


@pytest.fixture
def validator(config: SimpleNamespace, analytics: SimpleNamespace) -> CrawlablePageValidator:
  """Build a validator with lightweight collaborators."""
  return CrawlablePageValidator(config, analytics)


def test_validate_returns_sanitised_url_without_header_check(validator: CrawlablePageValidator) -> None:
  """Returns a crawlable URL when header checks are disabled."""
  assert (
    validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/a/../page') == 'https://example.com/page'
  )


def test_validate_rejects_invalid_url(validator: CrawlablePageValidator) -> None:
  """Rejects URLs with an unsupported scheme."""
  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'ftp://example.com/file') is None


def test_validate_rejects_url_outside_base_url(validator: CrawlablePageValidator) -> None:
  """Rejects URLs outside the configured crawl scope."""
  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://other.example/page') is None


def test_validate_rejects_previously_scanned_url(
  validator: CrawlablePageValidator,
  analytics: SimpleNamespace,
) -> None:
  """Rejects URLs already recorded as scanned."""
  analytics.is_url_in_pages_scanned.return_value = True

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') is None


def test_validate_skips_header_processing_when_disabled(
  validator: CrawlablePageValidator,
  mocker: MockerFixture,
) -> None:
  """Does not fetch headers when header checks are disabled."""
  process_headers = mocker.patch('src.crawlable_page_validator.src.filters.process_url_headers')

  validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page')

  process_headers.assert_not_called()


def test_validate_returns_url_with_acceptable_headers(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocker: MockerFixture,
) -> None:
  """Returns the URL when the response status and content type are acceptable."""
  config.perform_header_check = True
  process_headers = mocker.patch(
    'src.crawlable_page_validator.src.filters.process_url_headers',
    return_value={
      'status_code': 200,
      'final_url': 'https://example.com/page',
      'headers': {'Content-Type': 'text/html'},
    },
  )

  result = validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page')

  assert result == 'https://example.com/page'
  process_headers.assert_called_once_with(config, 'https://example.com/page', supports_head_requests=True)


def test_validate_rejects_unacceptable_headers(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocker: MockerFixture,
) -> None:
  """Rejects a response with an unsupported status code."""
  config.perform_header_check = True
  mocker.patch(
    'src.crawlable_page_validator.src.filters.process_url_headers',
    return_value={
      'status_code': 404,
      'final_url': 'https://example.com/page',
      'headers': {'Content-Type': 'text/html'},
    },
  )

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/page') is None


def test_validate_revalidates_redirected_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocker: MockerFixture,
) -> None:
  """Revalidates the final URL after a redirect."""
  config.perform_header_check = True
  mocker.patch(
    'src.crawlable_page_validator.src.filters.process_url_headers',
    return_value={
      'status_code': 301,
      'final_url': 'https://example.com/final',
      'headers': {'Content-Type': 'text/html'},
    },
  )

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/start') == 'https://example.com/final'


def test_validate_rejects_redirect_outside_scope(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocker: MockerFixture,
) -> None:
  """Rejects a redirect whose final URL is outside the crawl scope."""
  config.perform_header_check = True
  mocker.patch(
    'src.crawlable_page_validator.src.filters.process_url_headers',
    return_value={
      'status_code': 302,
      'final_url': 'https://other.example/final',
      'headers': {'Content-Type': 'text/html'},
    },
  )

  assert validator.validate(SITE_DATA, BASE_URL, PARENT_URL, 'https://example.com/start') is None


def test_robots_txt_is_cached_and_reused(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocker: MockerFixture,
) -> None:
  """Caches a parsed robots.txt response for subsequent checks."""
  config.follow_robots_txt = True
  fetch = mocker.patch.object(validator, '_fetch_robots_txt', return_value='User-agent: *\nAllow: /')

  assert validator._is_url_allowed_by_robots_txt('https://example.com/page') is True
  assert validator._is_url_allowed_by_robots_txt('https://example.com/other') is True

  fetch.assert_called_once_with('https://example.com/robots.txt')
  assert 'example.com' in config.robots_txt_cache


def test_robots_txt_disallows_matching_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocker: MockerFixture,
) -> None:
  """Honors a robots.txt disallow rule."""
  config.follow_robots_txt = True
  mocker.patch.object(validator, '_fetch_robots_txt', return_value='User-agent: *\nDisallow: /private')

  assert validator._is_url_allowed_by_robots_txt('https://example.com/private/page') is False
