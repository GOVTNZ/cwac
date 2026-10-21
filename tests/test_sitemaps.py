"""Tests for crawling sitemaps."""

import random
import typing

import pytest
from usp.web_client.abstract_client import (
  AbstractWebClient,
  AbstractWebClientResponse,
  LocalWebClientSuccessResponse,
  WebClientErrorResponse,
)

import src.sitemaps
from src.page_queue import DiscoveredPage
from tests.helpers.utils import normalized_url


class FakeWebClient(AbstractWebClient):
  """Serves canned responses for a test site, recording every url requested."""

  def __init__(self, responses: dict[str, str]) -> None:
    """Initialise the client with response bodies keyed by path."""
    self.responses = {f'https://example.com/{path}': body for path, body in responses.items()}
    self.requested: list[str] = []

  def set_max_response_data_length(self, max_response_data_length: int | None) -> None:
    """Ignore the max response length, since responses are canned."""

  def get(self, url: str) -> AbstractWebClientResponse:
    """Return the canned response for the url, or a 404 if there is none."""
    self.requested.append(url)

    if url in self.responses:
      return LocalWebClientSuccessResponse(url, self.responses[url])

    return WebClientErrorResponse('404 Not Found', retryable=False)

  def requested_paths(self) -> set[str]:
    """Return the paths of every url requested."""
    return {url.removeprefix('https://example.com/') for url in self.requested}


def robots_txt(*paths: str) -> str:
  """Build a robots.txt advertising sitemaps at the given paths."""
  return '\n'.join(['User-agent: *', *(f'Sitemap: https://example.com/{path}' for path in paths)])


def sitemap_index(*paths: str) -> str:
  """Build a sitemap index listing sitemaps at the given paths."""
  sitemaps = ''.join(f'<sitemap><loc>https://example.com/{path}</loc></sitemap>' for path in paths)
  return (
    '<?xml version="1.0" encoding="UTF-8"?>'
    f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemaps}</sitemapindex>'
  )


def url_set(*paths: str) -> str:
  """Build a sitemap listing pages at the given paths."""
  urls = ''.join(f'<url><loc>https://example.com/{path}</loc></url>' for path in paths)
  return (
    f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
  )


def crawl_site(web_client: FakeWebClient, limit: int = 100) -> list[DiscoveredPage]:
  """Crawl the test site's sitemaps."""
  return src.sitemaps.crawl(normalized_url('https://example.com/'), limit, web_client)


def crawled_urls(web_client: FakeWebClient) -> set[str]:
  """Crawl the test site's sitemaps, returning the page urls found."""
  return {page.url for page in crawl_site(web_client)}


def test_crawl_fetches_robots_txt_for_the_given_url() -> None:
  """Looks for sitemaps in the robots.txt of the given url."""
  web_client = FakeWebClient({})

  crawl_site(web_client)

  assert 'robots.txt' in web_client.requested_paths()


def test_crawl_returns_pages_with_their_sitemap_as_the_parent() -> None:
  """Returns every page when under the limit, with the sitemap it was found in as the parent."""
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('one.xml', 'two.xml'),
      'one.xml': url_set('a', 'b'),
      'two.xml': url_set('c'),
    }
  )

  assert sorted(crawl_site(web_client)) == sorted(
    [
      DiscoveredPage('https://example.com/one.xml', 'https://example.com/a'),
      DiscoveredPage('https://example.com/one.xml', 'https://example.com/b'),
      DiscoveredPage('https://example.com/two.xml', 'https://example.com/c'),
    ]
  )


def test_crawl_does_not_duplicate_pages_from_index_sitemaps() -> None:
  """Only takes pages from the leaf sitemaps, since index sitemaps yield the pages of their sub-sitemaps."""
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('index.xml', 'three.xml'),
      'index.xml': sitemap_index('one.xml', 'two.xml'),
      'one.xml': url_set('a'),
      'two.xml': url_set('b'),
      'three.xml': url_set('c'),
    }
  )

  assert sorted(crawl_site(web_client)) == sorted(
    [
      DiscoveredPage('https://example.com/one.xml', 'https://example.com/a'),
      DiscoveredPage('https://example.com/two.xml', 'https://example.com/b'),
      DiscoveredPage('https://example.com/three.xml', 'https://example.com/c'),
    ]
  )


def test_crawl_returns_nothing_when_fetching_sitemaps_raises(monkeypatch: pytest.MonkeyPatch) -> None:
  """Returns no pages if fetching the sitemaps raises, rather than letting the error escape."""

  def fake_sitemap_tree_for_homepage(_: str, **__: object) -> typing.NoReturn:
    raise RuntimeError('boom')

  monkeypatch.setattr(src.sitemaps, 'sitemap_tree_for_homepage', fake_sitemap_tree_for_homepage)

  assert crawl_site(FakeWebClient({})) == []


def test_crawl_does_not_count_robots_txt_as_an_index_level() -> None:
  """Follows the sitemaps listed in an index advertised by robots.txt."""
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('index.xml'),
      'index.xml': sitemap_index('pages.xml'),
      'pages.xml': url_set('a'),
    }
  )

  # expect we've fetched pages.xml, since index.xml is a top-level index:
  # robots.txt only advertises sitemaps, so isn't an index itself
  assert crawled_urls(web_client) == {'https://example.com/a'}


def test_crawl_treats_sitemaps_at_known_paths_as_top_level() -> None:
  """Follows an index at a known path, even when robots.txt advertises other sitemaps."""
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('advertised.xml'),
      'advertised.xml': url_set('a'),
      'sitemap.xml': sitemap_index('pages.xml'),
      'pages.xml': url_set('b'),
    }
  )

  # expect we've fetched both advertised.xml and pages.xml, since sitemap.xml
  # is a top-level index just like advertised.xml is a top-level sitemap
  assert crawled_urls(web_client) == {'https://example.com/a', 'https://example.com/b'}


@pytest.mark.parametrize(
  ('index_path', 'discovery'),
  [
    pytest.param('index.xml', {'robots.txt': robots_txt('index.xml')}, id='robots.txt'),
    pytest.param('sitemap.xml', {}, id='known path'),
  ],
)
def test_crawl_does_not_follow_nested_indexes(index_path: str, discovery: dict[str, str]) -> None:
  """Fetches the sitemaps listed in an index, but not those listed in an index nested within it."""
  web_client = FakeWebClient(
    {
      **discovery,
      index_path: sitemap_index('pages.xml', 'nested.xml'),
      'pages.xml': url_set('a'),
      'nested.xml': sitemap_index('deep.xml'),
      'deep.xml': url_set('b'),
    }
  )

  # expect we've fetched pages.xml but not deep.xml, since deep.xml is
  # listed by nested.xml, which is an index within the top-level index
  assert crawled_urls(web_client) == {'https://example.com/a'}
  assert 'deep.xml' not in web_client.requested_paths()


def test_crawl_fetches_every_sitemap_from_an_index_within_the_max(monkeypatch: pytest.MonkeyPatch) -> None:
  """Fetches every sitemap from an index that lists no more than the max number of sitemaps."""
  monkeypatch.setattr(src.sitemaps, 'MAX_SITEMAPS_PER_INDEX', 2)

  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('index.xml'),
      'index.xml': sitemap_index('one.xml', 'two.xml'),
      'one.xml': url_set('a'),
      'two.xml': url_set('b'),
    }
  )

  # expect we've fetched urls from both sitemaps, since that's within our max
  assert crawled_urls(web_client) == {'https://example.com/a', 'https://example.com/b'}


def test_crawl_fetches_at_most_the_max_sitemaps_from_an_index(monkeypatch: pytest.MonkeyPatch) -> None:
  """Fetches only the max number of sitemaps from an index that lists more than that."""
  monkeypatch.setattr(src.sitemaps, 'MAX_SITEMAPS_PER_INDEX', 2)

  sitemaps = {f'pages-{i}.xml': url_set(str(i)) for i in range(5)}
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('index.xml'),
      'index.xml': sitemap_index(*sitemaps),
      **sitemaps,
    }
  )

  urls = crawled_urls(web_client)
  fetched = web_client.requested_paths() & sitemaps.keys()

  # expect we've fetched only 2 of the 5 sitemaps, and only have urls from those
  assert len(fetched) == 2
  assert urls == {f'https://example.com/{path.removeprefix("pages-").removesuffix(".xml")}' for path in fetched}


def test_crawl_fetches_at_most_the_max_sitemaps_from_robots_txt(monkeypatch: pytest.MonkeyPatch) -> None:
  """Fetches only the max number of sitemaps advertised by a robots.txt that lists more than that."""
  monkeypatch.setattr(src.sitemaps, 'MAX_SITEMAPS_PER_INDEX', 2)

  sitemaps = {f'pages-{i}.xml': url_set(str(i)) for i in range(5)}
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt(*sitemaps),
      **sitemaps,
    }
  )

  urls = crawled_urls(web_client)
  fetched = web_client.requested_paths() & sitemaps.keys()

  # expect we've fetched only 2 of the 5 sitemaps, and only have urls from those
  assert len(fetched) == 2
  assert urls == {f'https://example.com/{path.removeprefix("pages-").removesuffix(".xml")}' for path in fetched}


def test_crawl_does_not_sample_pages_when_at_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
  """Returns every page without sampling when there are exactly as many as the limit."""
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('one.xml'),
      'one.xml': url_set('a', 'b', 'c'),
    }
  )

  def fail_randrange(_: int) -> int:
    pytest.fail('should not sample')

  monkeypatch.setattr(random, 'randrange', fail_randrange)

  assert len(crawl_site(web_client, 3)) == 3


def test_crawl_caps_the_number_of_pages_at_the_limit() -> None:
  """Returns no more than the limit, all of which come from the sitemaps."""
  paths = [str(i) for i in range(100)]
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('one.xml', 'two.xml'),
      'one.xml': url_set(*paths[:50]),
      'two.xml': url_set(*paths[50:]),
    }
  )

  pages = crawl_site(web_client, 10)

  assert len(pages) == 10
  assert len({page.url for page in pages}) == 10
  assert {page.url for page in pages} <= {f'https://example.com/{path}' for path in paths}


def test_crawl_reservoir_samples_pages_when_over_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
  """Replaces the page at the picked index when it is within the limit, otherwise discards the new page."""
  web_client = FakeWebClient(
    {
      'robots.txt': robots_txt('one.xml'),
      'one.xml': url_set('a', 'b', 'c', 'd', 'e'),
    }
  )

  calls: list[int] = []
  picks = iter([0, 3, 1])

  def fake_randrange(stop: int) -> int:
    calls.append(stop)
    return next(picks)

  monkeypatch.setattr(random, 'randrange', fake_randrange)

  # c replaces a, d is discarded, e replaces b
  assert crawl_site(web_client, 2) == [
    DiscoveredPage('https://example.com/one.xml', 'https://example.com/c'),
    DiscoveredPage('https://example.com/one.xml', 'https://example.com/e'),
  ]

  # each pick is from the number of pages found so far
  assert calls == [3, 4, 5]
