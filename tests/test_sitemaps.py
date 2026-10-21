"""Tests for crawling sitemaps."""

import random

import pytest
from usp.objects.page import SitemapPage
from usp.objects.sitemap import AbstractSitemap, IndexWebsiteSitemap, IndexXMLSitemap, PagesXMLSitemap

import src.sitemaps
from src.page_queue import DiscoveredPage
from tests.helpers.utils import normalized_url


def pages_sitemap(name: str, paths: list[str]) -> PagesXMLSitemap:
  """Build a sitemap with pages for the given paths on a test site."""
  return PagesXMLSitemap(
    url=f'https://example.com/{name}.xml',
    pages=[SitemapPage(url=f'https://example.com/{path}') for path in paths],
  )


def stub_tree(monkeypatch: pytest.MonkeyPatch, sub_sitemaps: list[AbstractSitemap]) -> list[str]:
  """Stub fetching the sitemap tree, returning the urls it was fetched for."""
  calls: list[str] = []

  def fake_sitemap_tree_for_homepage(url: str) -> IndexWebsiteSitemap:
    calls.append(url)
    return IndexWebsiteSitemap(url=url, sub_sitemaps=sub_sitemaps)

  monkeypatch.setattr(src.sitemaps, 'sitemap_tree_for_homepage', fake_sitemap_tree_for_homepage)

  return calls


def test_crawl_fetches_the_tree_for_the_given_url(monkeypatch: pytest.MonkeyPatch) -> None:
  """Fetches the sitemap tree for the given url."""
  calls = stub_tree(monkeypatch, [])

  src.sitemaps.crawl(normalized_url('https://example.com/'), 10)

  assert calls == [normalized_url('https://example.com/')]


def test_crawl_returns_pages_with_their_sitemap_as_the_parent(monkeypatch: pytest.MonkeyPatch) -> None:
  """Returns every page when under the limit, with the sitemap it was found in as the parent."""
  stub_tree(monkeypatch, [pages_sitemap('one', ['a', 'b']), pages_sitemap('two', ['c'])])

  assert src.sitemaps.crawl(normalized_url('https://example.com/'), 10) == [
    DiscoveredPage('https://example.com/one.xml', 'https://example.com/a'),
    DiscoveredPage('https://example.com/one.xml', 'https://example.com/b'),
    DiscoveredPage('https://example.com/two.xml', 'https://example.com/c'),
  ]


def test_crawl_does_not_sample_pages_when_at_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
  """Returns every page without sampling when there are exactly as many as the limit."""
  stub_tree(monkeypatch, [pages_sitemap('one', ['a', 'b', 'c'])])

  def fail_randrange(_: int) -> int:
    pytest.fail('should not sample')

  monkeypatch.setattr(random, 'randrange', fail_randrange)

  assert len(src.sitemaps.crawl(normalized_url('https://example.com/'), 3)) == 3


def test_crawl_does_not_duplicate_pages_from_index_sitemaps(monkeypatch: pytest.MonkeyPatch) -> None:
  """Only takes pages from the leaf sitemaps, since index sitemaps yield the pages of their sub-sitemaps."""
  stub_tree(
    monkeypatch,
    [
      IndexXMLSitemap(
        url='https://example.com/index.xml',
        sub_sitemaps=[pages_sitemap('one', ['a']), pages_sitemap('two', ['b'])],
      ),
      pages_sitemap('three', ['c']),
    ],
  )

  assert src.sitemaps.crawl(normalized_url('https://example.com/'), 10) == [
    DiscoveredPage('https://example.com/one.xml', 'https://example.com/a'),
    DiscoveredPage('https://example.com/two.xml', 'https://example.com/b'),
    DiscoveredPage('https://example.com/three.xml', 'https://example.com/c'),
  ]


def test_crawl_returns_nothing_when_fetching_sitemaps_raises(monkeypatch: pytest.MonkeyPatch) -> None:
  """Returns no pages if fetching the sitemaps raises, rather than letting the error escape."""

  def fake_sitemap_tree_for_homepage(_: str) -> IndexWebsiteSitemap:
    raise RuntimeError('boom')

  monkeypatch.setattr(src.sitemaps, 'sitemap_tree_for_homepage', fake_sitemap_tree_for_homepage)

  assert src.sitemaps.crawl(normalized_url('https://example.com/'), 10) == []


def test_crawl_caps_the_number_of_pages_at_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
  """Returns no more than the limit, all of which come from the sitemaps."""
  paths = [str(i) for i in range(100)]
  stub_tree(monkeypatch, [pages_sitemap('one', paths[:50]), pages_sitemap('two', paths[50:])])

  pages = src.sitemaps.crawl(normalized_url('https://example.com/'), 10)

  assert len(pages) == 10
  assert len({page.url for page in pages}) == 10
  assert {page.url for page in pages} <= {f'https://example.com/{path}' for path in paths}


def test_crawl_reservoir_samples_pages_when_over_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
  """Replaces the page at the picked index when it is within the limit, otherwise discards the new page."""
  stub_tree(monkeypatch, [pages_sitemap('one', ['a', 'b', 'c', 'd', 'e'])])

  calls: list[int] = []
  picks = iter([0, 3, 1])

  def fake_randrange(stop: int) -> int:
    calls.append(stop)
    return next(picks)

  monkeypatch.setattr(random, 'randrange', fake_randrange)

  # c replaces a, d is discarded, e replaces b
  assert src.sitemaps.crawl(normalized_url('https://example.com/'), 2) == [
    DiscoveredPage('https://example.com/one.xml', 'https://example.com/c'),
    DiscoveredPage('https://example.com/one.xml', 'https://example.com/e'),
  ]

  # each pick is from the number of pages found so far
  assert calls == [3, 4, 5]
