"""Crawling sitemaps for urls to audit."""

import logging
import random

from usp.objects.sitemap import AbstractIndexSitemap
from usp.tree import sitemap_tree_for_homepage
from usp.web_client.abstract_client import AbstractWebClient

from src.page_queue import DiscoveredPage
from src.urls import NormalizedUrl

logger = logging.getLogger('cwac')


def crawl(url: NormalizedUrl, limit: int, web_client: AbstractWebClient | None = None) -> list[DiscoveredPage]:
  """Crawls the urls sitemap, if there is one.

  Performance:
      1+ HTTP requests depending on the sitemap structure and discovery path.
  """
  logger.info('Fetching sitemap for %s', url)

  try:
    tree = sitemap_tree_for_homepage(url, web_client=web_client)
  except Exception:
    logger.exception('Failed to get sitemap')
    return []

  discovered_pages: list[DiscoveredPage] = []
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
      if len(discovered_pages) < limit:
        discovered_pages.append(DiscoveredPage(sitemap.url, page.url))
      else:
        # these random numbers are not used for security or cryptographic
        # purposes so it is safe to use and 'nosec' suppresses bandit
        index = random.randrange(num_found)  # nosec # noqa: S311
        if index < limit:
          discovered_pages[index] = DiscoveredPage(sitemap.url, page.url)

  if num_found > limit:
    logger.info('Found %i urls from sitemaps for %s, randomly selected %i of them', num_found, url, limit)

  return discovered_pages
