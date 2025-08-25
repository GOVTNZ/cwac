"""Centralised Web Accessibility Checker.

This is the main entry point script for CWAC.
Refer to the README for more information.
"""

import concurrent.futures
import csv
import logging
import os
import random
from queue import SimpleQueue
from typing import cast
from urllib.parse import urlparse, urlunparse

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

    def should_skip_row(self, row: SiteData) -> bool:
        """Check if a row being imported should be skipped.

        Checks if a URL/Organisation should be included
        in the audit according to config_default.json's
        filter_to_organisations and
        filter_to_urls.

        Args:
            row (SiteData): a row from a CSV

        Returns:
            bool: True if the row should be skipped, False otherwise
        """
        found_org = False
        if config.filter_to_organisations:
            for org in config.filter_to_organisations:
                if org in row["organisation"]:
                    found_org = True
                    break

        found_url = False
        if config.filter_to_urls:
            for url in config.filter_to_urls:
                if url in row["url"]:
                    found_url = True
                    break

        if config.filter_to_organisations and config.filter_to_urls:
            return not (found_org and found_url)
        if config.filter_to_organisations:
            return not found_org
        if config.filter_to_urls:
            return not found_url

        return False

    def lowercase_url(self, url: str) -> str:
        """Make URL protocl/netloc lowercase.

        Args:
            url (str): URL to make lowercase

        Returns:
            str: lowercase URL
        """
        parsed = urlparse(url)
        modified = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
        return urlunparse(modified)

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

    def import_base_urls_without_head_support(self) -> set[str]:
        """Import base urls that don't support HEAD requests.

        Returns:
            set[str]: a list of base urls that don't support HEAD requests
        """
        folder_path = config.base_urls_nohead_path
        base_urls = set()

        for filename in os.listdir(folder_path):
            if filename.endswith(".csv"):
                with open(
                    os.path.join(folder_path, filename),
                    encoding="utf-8-sig",
                    newline="",
                ) as file:
                    reader = csv.reader(file)
                    header = next(reader)
                    for row in reader:
                        dict_row = cast(dict[str, str], dict(zip(header, row)))

                        # Strip whitespace from URL
                        dict_row["url"] = dict_row["url"].strip()

                        # Make the URL lowercase
                        dict_row["url"] = self.lowercase_url(dict_row["url"])

                        base_urls.add(dict_row["url"])
        return base_urls

    def import_base_urls(self) -> SimpleQueue[SiteData]:
        """Import target URLs to visit and potentially crawl.

        This function reads all CSVs in config.base_urls_visit_path
        and returns a SimpleQueue of each row

        Returns:
            SimpleQueue: a SimpleQueue of URLs
        """
        folder_path = config.base_urls_visit_path

        headless_base_urls = self.import_base_urls_without_head_support()

        url_queue: SimpleQueue[SiteData] = SimpleQueue()

        for filename in os.listdir(folder_path):
            if filename.endswith(".csv"):
                with open(
                    os.path.join(folder_path, filename),
                    encoding="utf-8-sig",
                    newline="",
                ) as file:
                    reader = csv.reader(file)
                    header = next(reader)
                    for row in reader:
                        dict_row = cast(SiteData, dict(zip(header, row)))
                        if self.should_skip_row(dict_row):
                            continue

                        # Strip whitespace from URL
                        dict_row["url"] = dict_row["url"].strip()

                        # Make the URL lowercase
                        dict_row["url"] = self.lowercase_url(dict_row["url"])

                        dict_row["supports_head"] = dict_row["url"] not in headless_base_urls

                        CWAC.analytics.add_base_url(dict_row["url"])

                        url_queue.put(dict_row)

        # If shuffle_queue is True, shuffle the queue
        if config.shuffle_base_urls:
            self.shuffle_queue(url_queue)
        return url_queue

    def __init__(self) -> None:
        """Set up CWAC and run the test.

        Imports target URLs, sets up Analytics, creates
        relevant folders, spawns a number of threads, then
        finally verifies the results of the test.
        """
        # Print the initial message
        output_init_message()

        # Import base_urls into global varaiable
        CWAC.url_queue = self.import_base_urls()

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
