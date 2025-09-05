"""Centralised Web Accessibility Checker.

This is the main entry point script for CWAC.
Refer to the README for more information.
"""

import concurrent.futures
import logging
import random
import re
import sys
from queue import SimpleQueue
from urllib.parse import urlparse

import src.verify
from config import Config
from src.analytics import Analytics
from src.browser import Browser
from src.crawler import Crawler, SiteData
from src.output import output_init_message

logger = logging.getLogger('cwac')


class CWAC:
  """Main CWAC class."""

  def thread(self, thread_id: int) -> None:
    """Start a browser, and start crawling.

    Args:
        thread_id (int): identifier for the thread
    """
    browser = Browser(self.config, thread_id)
    crawl = Crawler(config=self.config, browser=browser, url_queue=self.url_queue, analytics=self.analytics)
    crawl.iterate_through_base_urls()
    browser.close()

  def spawn_threads(self) -> None:
    """Create a number of threads to speed up execution.

    Number of threads defined by config.json.thread_count.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.thread_count) as executor:
      results = {executor.submit(self.thread, thread_id): thread_id for thread_id in range(self.config.thread_count)}
    for result in results:
      result.result()
    logger.info('All threads complete')

  def shuffle_queue(self, queue: SimpleQueue[SiteData]) -> None:
    """Shuffle a SimpleQueue.

    As part of the shuffling, a basic effort is made to avoid having sites
    with the same network location be placed consecutively, though this is
    not guaranteed to be the same avoided as that could be impossible.

    Args:
        queue (SimpleQueue[SiteData]): the queue to shuffle
    """
    # Convert queue to list
    queue_list = []
    while not queue.empty():
      queue_list.append(queue.get())

    # Shuffle the list
    random.shuffle(queue_list)

    last_netloc = None
    skipped_item = None

    # Iterate through the list and add back to queue
    for item in queue_list:
      current_netloc = urlparse(item['url']).netloc

      # If it looks like the net location of the last item we saw is
      # the same as the net location of the current item, skip adding
      # it to the queue until after the next item in the hopes that
      # that will have a different net location
      if skipped_item is None and last_netloc == current_netloc:
        skipped_item = item
        continue

      queue.put(item)
      last_netloc = current_netloc

      # add the skipped item to the queue
      if skipped_item is not None:
        queue.put(skipped_item)
        skipped_item = None

    # ensure that the last item is added, even if its consecutive
    if skipped_item is not None:
      queue.put(skipped_item)

  def import_base_urls(self) -> SimpleQueue[SiteData]:
    """Import target URLs to visit and potentially crawl.

    This function reads all CSVs in config.base_urls_visit_path
    and returns a SimpleQueue of each row

    Returns:
        SimpleQueue: a SimpleQueue of URLs
    """
    url_queue: SimpleQueue[SiteData] = SimpleQueue()

    for url in self.config.audit_subjects:
      url_queue.put(url)
      self.analytics.add_base_url(url['url'])

    # If shuffle_queue is True, shuffle the queue
    if self.config.shuffle_base_urls:
      self.shuffle_queue(url_queue)
    return url_queue

  def __init__(self, config_file: str) -> None:
    """Set up CWAC in preparing of a run."""
    self.config = Config(config_file)
    self.analytics = Analytics(self.config)
    self.url_queue = self.import_base_urls()

  def run(self) -> None:
    """Run the checker."""
    # Print the initial message
    output_init_message(self.config)

    things_to_scan = 'websites'
    if self.config.max_links_per_domain == 1:
      things_to_scan = 'pages'

    # Print the number of URLs to be scanned
    num_websites_msg = f'Number of {things_to_scan} to be scanned: {self.url_queue.qsize()}'
    print(num_websites_msg)
    print('*' * 80)
    logger.info(num_websites_msg)

    # Set the estimated number of pages in the analytics object
    self.analytics.est_num_pages_in_test = self.url_queue.qsize() * self.config.max_links_per_domain

    if self.config.thread_count == 1:
      # Run CWAC without threading (useful for profiling)
      self.thread(0)
    else:
      # Run CWAC with multithreading
      self.spawn_threads()

    # Verify results
    src.verify.verify_axe_results(
      max_links_per_domain=self.config.max_links_per_domain,
      pages_scanned=self.analytics.pages_scanned,
    )

    print('\r\n')
    print('-' * 80)
    print('\r\nCWAC complete! Data can be found', 'in the ./results folder.')

    logger.info('CWAC complete!')


if __name__ == '__main__':

  def resolve_config_filename() -> str:
    """Resolve the config filename when being invoked directly."""
    config_filename = 'config_default.json'
    # First arg passed to CWAC is the config filename
    if len(sys.argv) > 1:
      config_filename = sys.argv[1]
      # Only accept alphanumeric, underscores, dots, and hyphens
      if not re.match(r'^[a-zA-Z0-9_.-]+$', config_filename):
        raise ValueError('config_filename must be alphanumeric, underscores, and hyphens')
    return config_filename

  cwac: CWAC = CWAC(resolve_config_filename())
  cwac.run()
