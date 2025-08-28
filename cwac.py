"""Centralised Web Accessibility Checker.

This is the main entry point script for CWAC.
Refer to the README for more information.
"""

import concurrent.futures
import logging
import random
from queue import SimpleQueue
from typing import Any
from urllib.parse import urlparse

import src.verify
from config import config
from src.analytics import Analytics
from src.browser import Browser
from src.crawler import Crawler, SiteData
from src.output import output_init_message


class CWAC:
    """Main CWAC class."""

    # Global queue of URLs to scan
    url_queue: SimpleQueue[SiteData]

    # Global anaytics for the scan
    analytics = Analytics()

    def thread(self, thread_id: int) -> None:
        """Start a browser, and start crawling.

        Args:
            thread_id (int): identifier for the thread
        """
        browser = Browser(thread_id)
        crawl = Crawler(browser=browser, url_queue=CWAC.url_queue, analytics=CWAC.analytics)
        crawl.iterate_through_base_urls()
        browser.close()

    def spawn_threads(self) -> None:
        """Create a number of threads to speed up execution.

        Number of threads defined by config.json.thread_count.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.thread_count) as executor:
            results = {executor.submit(self.thread, thread_id): thread_id for thread_id in range(config.thread_count)}
        for result in results:
            result.result()
        logging.info("All threads complete")

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
            current_netloc = urlparse(item["url"]).netloc

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

    def __queue_audit_subjects(self) -> SimpleQueue[Any]:
        audit_queue: SimpleQueue[SiteData] = SimpleQueue()

        for subject in config.audit_subjects:
            audit_queue.put(subject)
            CWAC.analytics.add_base_url(subject["url"])

        # If shuffle_queue is True, shuffle the queue
        if config.shuffle_base_urls:
            self.shuffle_queue(audit_queue)
        return audit_queue

    def __init__(self) -> None:
        """Set up CWAC and run the test.

        Imports target URLs, sets up Analytics, creates
        relevant folders, spawns a number of threads, then
        finally verifies the results of the test.
        """
        # Print the initial message
        output_init_message()

        # Import base_urls into global varaiable
        CWAC.url_queue = self.__queue_audit_subjects()

        things_to_scan = "websites"
        if config.max_links_per_domain == 1:
            things_to_scan = "pages"

        # Print the number of URLs to be scanned
        num_websites_msg = f"Number of {things_to_scan} to be scanned: {CWAC.url_queue.qsize()}"
        print(num_websites_msg)
        print("*" * 80)
        logging.info(num_websites_msg)

        # Set the estimated number of pages in the analytics object
        self.analytics.est_num_pages_in_test = CWAC.url_queue.qsize() * config.max_links_per_domain

        if config.thread_count == 1:
            # Run CWAC without threading (useful for profiling)
            self.thread(0)
        else:
            # Run CWAC with multithreading
            self.spawn_threads()

        # Verify results
        src.verify.verify_axe_results(pages_scanned=self.analytics.pages_scanned)

        print("\r\n")
        print("-" * 80)
        print("\r\nCWAC complete! Data can be found", "in the ./results folder.")

        logging.info("CWAC complete!")


if __name__ == "__main__":
    cwac: CWAC = CWAC()
