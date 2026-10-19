"""Tests for crawlable page validation."""

import textwrap
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
import requests
import responses
from pyfakefs.fake_filesystem import FakeFilesystem
from responses import matchers

from config import Config, SiteData
from src.analytics import Analytics
from src.crawlable_page_validator import CrawlablePageValidator

BASE_URL = 'https://example.com/'
PARENT_URL = 'https://example.com/parent/'
SITE_DATA: SiteData = {'url': BASE_URL, 'supports_head': True, 'columns': {}}


@pytest.fixture(autouse=True)
def setup_filesystem(fs: FakeFilesystem) -> None:
  """Set up the filesystem."""
  fs.makedirs('results/test-audit')


@pytest.fixture(name='config')
def fixture_config() -> SimpleNamespace:
  """Return the minimum configuration used by the validator."""
  return SimpleNamespace(
    audit_name='test-audit',
    follow_robots_txt=False,
    perform_header_check=False,
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
  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/a/../page') == 'https://example.com/page'


def test_validate_does_not_double_encode_url(validator: CrawlablePageValidator) -> None:
  """Leaves already percent-encoded characters alone while encoding the rest."""
  assert (
    validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/a%20b/café') == 'https://example.com/a%20b/caf%C3%A9'
  )


@pytest.mark.parametrize(
  ('url', 'expected'),
  [
    ('https://example.com/caf%c3%a9', 'https://example.com/caf%C3%A9'),
    ('https://example.com/caf%C3%A9', 'https://example.com/caf%C3%A9'),
    ('https://example.com/100%', 'https://example.com/100%'),
    ('https://example.com/a%zzb', 'https://example.com/a%zzb'),
  ],
)
def test_validate_uppercases_percent_escapes(validator: CrawlablePageValidator, url: str, expected: str) -> None:
  """Uppercases valid percent-escapes, leaving a standalone percent sign alone."""
  assert validator.validate(SITE_DATA, PARENT_URL, url) == expected


@pytest.mark.parametrize(
  ('url', 'expected'),
  [
    ('https://example.com/a/%2e%2e/b', 'https://example.com/b'),
    ('https://example.com/a/%2E%2E/b', 'https://example.com/b'),
    ('https://example.com/a/.%2e/b', 'https://example.com/b'),
    ('https://example.com/a/%2e./b', 'https://example.com/b'),
    ('https://example.com/a/%2e/b', 'https://example.com/a/b'),
    ('https://example.com/a/file%2ehtml', 'https://example.com/a/file%2Ehtml'),
    ('https://example.com/a/b/%2e%2e', 'https://example.com/a/'),
    ('https://example.com/a/b/%2e', 'https://example.com/a/b/'),
    ('https://example.com/a/b/..', 'https://example.com/a/'),
  ],
)
def test_validate_normalises_encoded_dot_segments(validator: CrawlablePageValidator, url: str, expected: str) -> None:
  """Treats percent-encoded dot segments as dots, leaving other escapes alone."""
  assert validator.validate(SITE_DATA, PARENT_URL, url) == expected


def test_validate_rejects_encoded_traversal_outside_base_url(validator: CrawlablePageValidator) -> None:
  """Rejects URLs that use percent-encoded dot segments to leave the base URL."""
  base_url = 'https://example.com/allowed/'

  assert (
    validator.validate({**SITE_DATA, 'url': base_url}, PARENT_URL, 'https://example.com/allowed/%2e%2e/private') is None
  )


@pytest.mark.parametrize('perform_header_check', [False, True])
def test_validate_rejects_url_outside_base_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
  perform_header_check: bool,
) -> None:
  """Rejects URLs outside the configured crawl scope without making any requests."""
  config.perform_header_check = perform_header_check

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://other.example/page') is None
  assert len(mocked_responses.calls) == 0


@pytest.mark.parametrize(
  ('base_url', 'url'),
  [
    ('https://example.com/', 'https://example.com/'),
    ('https://example.com/', 'https://example.com/a'),
    ('https://example.com/', 'https://example.com/a/b/'),
    ('https://example.com/news', 'https://example.com/news'),
    ('https://example.com/news', 'https://example.com/news/'),
    ('https://example.com/news', 'https://example.com/news/a'),
    ('https://example.com/news/', 'https://example.com/news'),
    ('https://example.com/news/', 'https://example.com/news/a'),
    # query strings and fragments are not part of the path
    ('https://example.com/?page=1', 'https://example.com/a'),
    ('https://example.com/news?page=1', 'https://example.com/news'),
    ('https://example.com/news?page=1', 'https://example.com/news/a'),
    ('https://example.com/news?page=1', 'https://example.com/news?page=2'),
    ('https://example.com/news', 'https://example.com/news?page=1'),
    ('https://example.com/news', 'https://example.com/news/a?page=1'),
    ('https://example.com/news', 'https://example.com/news/?q=/other'),
    ('https://example.com/news#top', 'https://example.com/news'),
    ('https://example.com/news#top', 'https://example.com/news/a'),
    ('https://example.com/news?page=1#top', 'https://example.com/news/a?page=2'),
    # semicolons are part of the path segment they are in
    ('https://example.com/news', 'https://example.com/news/a;b=1'),
    ('https://example.com/news;a=1', 'https://example.com/news;a=1'),
    ('https://example.com/news;a=1', 'https://example.com/news;a=1/b'),
    ('https://example.com/a;b=1/c', 'https://example.com/a;b=1/c/d'),
    # base urls that point at a file are treated as being for its directory
    ('https://example.com/index.html', 'https://example.com/a'),
    ('https://example.com/a/Default.aspx', 'https://example.com/a/Default.aspx'),
    ('https://example.com/a/Default.aspx', 'https://example.com/a/b'),
    ('https://example.com/a/index.html?id=1', 'https://example.com/a/b'),
    ('https://example.com/a.b/', 'https://example.com/a.b/c'),
    ('https://example.com/v1.2/docs', 'https://example.com/v1.2/docs/a'),
  ],
)
def test_validate_accepts_url_within_base_url(validator: CrawlablePageValidator, base_url: str, url: str) -> None:
  """Accepts URLs on the same origin whose path segments start with those of the base URL."""
  assert validator.validate({**SITE_DATA, 'url': base_url}, PARENT_URL, url) == url


@pytest.mark.parametrize(
  ('base_url', 'url'),
  [
    ('https://example.com/news', 'https://example.com/newsletter'),
    ('https://example.com/news/', 'https://example.com/newsletter'),
    ('https://example.com/news', 'https://example.com/'),
    ('https://example.com/a/b', 'https://example.com/a'),
    ('https://example.com/a/b', 'https://example.com/a/bc/d'),
    # paths are case-sensitive
    ('https://example.com/news', 'https://example.com/News/a'),
    # an encoded slash does not separate path segments
    ('https://example.com/news', 'https://example.com/news%2Fa'),
    # query strings and fragments are not part of the path
    ('https://example.com/news', 'https://example.com/?q=/news/a'),
    ('https://example.com/news', 'https://example.com/newsletter?q=/news/a'),
    ('https://example.com/news?q=/a', 'https://example.com/a'),
    ('https://example.com/news#/a', 'https://example.com/a'),
    ('https://example.com/news', 'https://example.com/newsletter#/news/a'),
    # semicolons are part of the path segment they are in
    ('https://example.com/news', 'https://example.com/news;a=1'),
    ('https://example.com/news;a=1', 'https://example.com/news'),
    ('https://example.com/news;a=1', 'https://example.com/news/b'),
    ('https://example.com/news;a=1', 'https://example.com/news;a=2/b'),
    # base urls that point at a file are treated as being for its directory
    ('https://example.com/a/index.html', 'https://example.com/b'),
    ('https://example.com/a.b/', 'https://example.com/a.c'),
    ('https://example.com/v1.2/docs', 'https://example.com/v1.2/other'),
  ],
)
def test_validate_rejects_url_outside_base_url_path(
  validator: CrawlablePageValidator,
  base_url: str,
  url: str,
) -> None:
  """Rejects URLs whose path segments do not start with those of the base URL."""
  assert validator.validate({**SITE_DATA, 'url': base_url}, PARENT_URL, url) is None


@pytest.mark.parametrize(
  'url',
  [
    'http://example.com/a',
    'https://example.com.evil.org/a',
    'https://example.com:8443/a',
    'https://www.example.com/a',
  ],
)
def test_validate_rejects_url_on_different_origin(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  url: str,
) -> None:
  """Rejects URLs whose scheme, host, or port differ from those of the base URL."""
  config.url_lookup = {'example.com', 'example.com.evil.org', 'example.com:8443'}

  assert validator.validate(SITE_DATA, PARENT_URL, url) is None


@pytest.mark.parametrize(
  ('base_url', 'other_base_url', 'url'),
  [
    ('https://example.com/', 'https://example.com/news', 'https://example.com/news'),
    ('https://example.com/', 'https://example.com/news', 'https://example.com/news/'),
    ('https://example.com/', 'https://example.com/news', 'https://example.com/news/a'),
    ('https://example.com/', 'https://example.com/news/', 'https://example.com/news/a'),
    ('https://example.com/', 'https://example.com/news/a', 'https://example.com/news/a/b'),
    ('https://example.com/a', 'https://example.com/a/b', 'https://example.com/a/b/c'),
    ('https://example.com/', 'https://example.com/a/index.html', 'https://example.com/a/b'),
    ('https://example.com/', 'https://example.com/news?page=1', 'https://example.com/news/a'),
  ],
)
def test_validate_rejects_url_within_more_specific_base_url(
  validator: CrawlablePageValidator,
  analytics: SimpleNamespace,
  base_url: str,
  other_base_url: str,
  url: str,
) -> None:
  """Rejects URLs that are within another base URL which is more specific than the current one."""
  analytics.base_urls = {base_url, other_base_url}

  assert validator.validate({**SITE_DATA, 'url': base_url}, PARENT_URL, url) is None


@pytest.mark.parametrize(
  ('base_url', 'other_base_url', 'url'),
  [
    # the url is not within the other base url
    ('https://example.com/', 'https://example.com/news', 'https://example.com/'),
    ('https://example.com/', 'https://example.com/news', 'https://example.com/a'),
    ('https://example.com/', 'https://example.com/news', 'https://example.com/newsletter'),
    ('https://example.com/', 'https://example.com/news', 'https://example.com/News/a'),
    ('https://example.com/', 'https://example.com/news;a=1', 'https://example.com/news/a'),
    ('https://example.com/', 'https://other.example/news', 'https://example.com/news/a'),
    ('https://example.com/a', 'https://example.com/a/b', 'https://example.com/a/bc'),
    # the other base url is not more specific than the current one
    ('https://example.com/news', 'https://example.com/', 'https://example.com/news/a'),
    ('https://example.com/news', 'https://example.com/news/', 'https://example.com/news/a'),
    ('https://example.com/news/', 'https://example.com/news', 'https://example.com/news/a'),
    ('https://example.com/news', 'https://example.com/news?page=1', 'https://example.com/news/a'),
    ('https://example.com/a', 'https://example.com/a/index.html', 'https://example.com/a/b'),
  ],
)
def test_validate_accepts_url_not_within_more_specific_base_url(
  validator: CrawlablePageValidator,
  analytics: SimpleNamespace,
  base_url: str,
  other_base_url: str,
  url: str,
) -> None:
  """Accepts URLs that are not within another base URL which is more specific than the current one."""
  analytics.base_urls = {base_url, other_base_url}

  assert validator.validate({**SITE_DATA, 'url': base_url}, PARENT_URL, url) == url


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

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/page') is None
  assert len(mocked_responses.calls) == 0
  analytics.is_url_in_pages_scanned.assert_called_once_with(BASE_URL, 'https://example.com/page')


def test_validate_skips_header_processing_when_disabled(
  validator: CrawlablePageValidator,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Does not fetch headers when header checks are disabled."""
  validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/page')

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

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/page') == 'https://example.com/page'
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
  """Rejects a response with an unsupported status code, recording it in the process."""
  config.perform_header_check = True
  mocked_responses.head('https://example.com/page', status=status, content_type='text/html')

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/page') is None

  with open('results/test-audit/unexpected_response_codes.csv', encoding='utf-8-sig') as f:
    assert (
      f.read()
      == textwrap.dedent(f"""
        base_url,parent_url,url,status_code
        {BASE_URL},{PARENT_URL},https://example.com/page,{status}
      """).lstrip()
    )


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

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/page') is None


def test_validate_revalidates_redirected_url(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Revalidates the final URL after a redirect."""
  config.perform_header_check = True
  mocked_responses.head('https://example.com/start', status=301, headers={'Location': '/final'})
  mocked_responses.head('https://example.com/final', content_type='text/html')

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/start') == 'https://example.com/final'


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

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/start') is None


def test_validate_rejects_redirect_outside_scope(
  validator: CrawlablePageValidator,
  config: SimpleNamespace,
  mocked_responses: responses.RequestsMock,
) -> None:
  """Rejects a redirect whose final URL is outside the crawl scope."""
  config.perform_header_check = True
  mocked_responses.head('https://example.com/start', status=302, headers={'Location': 'https://other.example/final'})
  mocked_responses.head('https://other.example/final', content_type='text/html')

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/start') is None


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

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/page') == 'https://example.com/page'
  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/private/page') is None

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

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/private/page') is None


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
    validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/private/page') == 'https://example.com/private/page'
  )
  assert (
    validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/private/other')
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

  assert validator.validate(SITE_DATA, PARENT_URL, 'https://example.com/page') == 'https://example.com/page'
