"""Crawling sitemaps for urls to audit."""

import logging
import random

from usp.objects.sitemap import AbstractIndexSitemap
from usp.tree import sitemap_tree_for_homepage
from usp.web_client.abstract_client import AbstractWebClient

from src.page_queue import DiscoveredPage
from src.urls import NormalizedUrl

logger = logging.getLogger('cwac')


# the most sitemaps to fetch from any one index (including robots.txt), as some
# sites have thousands of them, which makes fetching very slow and disk hungry
MAX_SITEMAPS_PER_INDEX = 25


def crawl(url: NormalizedUrl, limit: int, web_client: AbstractWebClient | None = None) -> list[DiscoveredPage]:
  """Crawls the url's sitemaps, if there are any, returning a random sample of up to `limit` of their pages.

  Only one level of sitemap index is followed: the sitemaps listed by an index
  advertised in robots.txt or found at a known path are fetched, but those listed
  by any index nested within them are not. At most MAX_SITEMAPS_PER_INDEX
  sitemaps are fetched from each index, chosen at random.

  Performance:
      1+ HTTP requests depending on the sitemap structure and discovery path,
      bounded by MAX_SITEMAPS_PER_INDEX per index.
  """
  logger.info('Fetching sitemap for %s', url)

  def limit_sitemaps(urls: list[str], recursion_level: int, parent_urls: set[str]) -> list[str]:
    # adjust the level to start at 0 if we're coming from a robots.txt
    # as usp treats that as an index even though it's not a sitemap
    if any(u.endswith('/robots.txt') for u in parent_urls):
      recursion_level -= 1

    # don't fetch the sitemaps listed by an index nested within a top-level index
    if recursion_level >= 1:
      if urls:
        logger.info(
          'Ignoring %i sitemap%s listed by a nested index for %s', len(urls), '' if len(urls) == 1 else 's', url
        )
      return []

    if len(urls) > MAX_SITEMAPS_PER_INDEX:
      logger.info(
        'Found %i sitemaps listed by an index for %s, randomly selected %i of them',
        len(urls),
        url,
        MAX_SITEMAPS_PER_INDEX,
      )

    # fetch a random selection of at most the max sitemaps from this index
    return random.sample(urls, k=min(len(urls), MAX_SITEMAPS_PER_INDEX))

  try:
    tree = sitemap_tree_for_homepage(
      url,
      web_client=web_client,
      recurse_list_callback=limit_sitemaps,
    )
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
