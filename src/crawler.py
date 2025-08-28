"""Crawler.

Crawls specified websites and tests them using AuditManager
"""

import importlib
import logging
import posixpath
import random
import re
import time
import urllib
import urllib.robotparser
from queue import SimpleQueue
from typing import Any

import requests
import selenium.common.exceptions
from bs4 import BeautifulSoup

import src.audit_manager
import src.audit_plugins
import src.filters
import src.output
from config import AuditSubject, config
from src.analytics import Analytics
from src.audit_manager import AuditManager
from src.browser import Browser
from src.output import CSVWriter

# pylint: disable=too-many-branches, too-many-statements, too-many-locals


type SiteData = AuditSubject


class Crawler:
    """Crawls URLs and initiates tests on the pages."""

    def __init__(
        self,
        browser: Browser,
        url_queue: SimpleQueue[SiteData],
        analytics: Analytics,
    ) -> None:
        """Initialise various vars."""
        self.browser = browser
        self.url_queue = url_queue
        self.analytics = analytics
        self.url_filter = src.filters.URLFilter()

    def iterate_through_base_urls(self) -> None:
        """Pick URLs from url_queue, and initiates a crawl on that URL."""
        # Count how many URls have been iterated through
        url_iteration = 0
        while not self.url_queue.empty():
            url_iteration += 1

            # Get a url off the shared queue
            with config.lock:
                site_data = self.url_queue.get()

            logging.info("Starting test %s", site_data["url"])

            # Crawl the url (the crawler also initiates tests)
            self.crawl(site_data, site_data["url"])

            # Restart the browser between each website
            self.browser.safe_restart()

    def resolve_final_url(self, url: str) -> str:
        """Resolve the final URL after redirects.

        Args:
            url (str): URL to resolve

        Returns:
            str: resolved URL
        """
        # Get the final URL after redirects
        try:
            ua_string = {"User-Agent": config.user_agent}
            response = requests.get(url, headers=ua_string, timeout=(10, 10))
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("Failed to get final URL %s", url)

        if response.url != url:
            logging.info("URL %s resolved to %s", url, response.url)
        return str(response.url)

    def url_sanitise(self, url: str) -> str:
        """Sanitise URLs.

        Args:
            url (str): URL to be sanitised
        Returns:
            str: sanitised URL
        """
        # Parse URL with urllib.parse
        try:
            parsed_url = urllib.parse.urlparse(url)
        except ValueError as exc:
            raise ValueError("Invalid URL") from exc

        # Ensure scheme is either http or https
        if parsed_url.scheme not in ["http", "https"]:
            raise ValueError("Invalid URL scheme")

        # Save if it was trailing slash
        was_trailing_slash = url.endswith("/")

        # Encode the URL path to handle special characters
        parsed_url = parsed_url._replace(path=urllib.parse.quote(parsed_url.path, safe="/"))

        # Prevent path traversal using posixpath.normpath
        parsed_url = parsed_url._replace(path=posixpath.normpath(parsed_url.path))

        # Add trailing slash if it was there
        if was_trailing_slash and not parsed_url.path.endswith("/"):
            parsed_url = parsed_url._replace(path=parsed_url.path + "/")

        # Rebuild URL
        url = urllib.parse.urlunparse(parsed_url)

        return url

    def url_filter_prevent_intersections(self, current_base_url: str, current_url: str) -> bool:
        """Filter out when a URL intersects with another base_url.

        Prevents, for instance, https://example.com/ from being scanned
        when https://example.com/abc/ is being scanned and
        prevents https://example.com/abc/ from being scanned when
        https://example.com/ is being scanned

        Args:
            url (str): A URL to filter

        Returns:
            bool: True if URL is valid, else False
        """

        def remove_file_from_path(url: str) -> str:
            """Remove the file from the URL path.

            E.g. https://example.com/abc/def.html -> https://example.com/abc/

            Args:
                url (str): URL to remove file from

            Returns:
                str: URL with file removed
            """
            if not url.endswith("/"):
                url = url[: url.rfind("/") + 1]
            return url

        def lowercase_protocol_and_domain(url: str) -> str:
            """Make URL protocol and domain lowercase.

            Args:
                url (str): URL to make lowercase

            Returns:
                str: lowercase URL
            """
            parsed_url = urllib.parse.urlparse(url)
            scheme = parsed_url.scheme.lower()
            netloc = parsed_url.netloc.lower()
            path = parsed_url.path
            return f"{scheme}://{netloc}{path}"

        # Prepares the base_url and url for the matching algorithm
        current_base_url = lowercase_protocol_and_domain(current_base_url)
        current_url = lowercase_protocol_and_domain(current_url)
        current_base_url = remove_file_from_path(current_base_url)
        current_url = remove_file_from_path(current_url)

        # If the current_url does not start with the current_base_url,
        # then the url should not be scanned as it is not within the
        # scope of the current_base_url
        if not current_url.startswith(current_base_url):
            logging.info(
                "URL filtered out due to not starting with base_url %s %s",
                current_base_url,
                current_url,
            )
            return False

        # Iterate through all (other) base_urls and check if the current_url
        # starts with any of them. If it does, then the current_url
        # should not be scanned as it is within the scope of another
        # base_url

        for base_url in self.analytics.base_urls:
            base_url = lowercase_protocol_and_domain(base_url)
            base_url = remove_file_from_path(base_url)
            if current_url.startswith(base_url) and len(base_url) > len(current_base_url):
                # If the current_url starts with a base_url that is longer
                # this means that the current_url is within the scope of
                # another base_url that is more specific than current_base_url
                logging.info(
                    "URL filtered out due to being within \
                            the scope of another base_url %s %s",
                    base_url,
                    current_url,
                )
                return False
        return True

    def handle_base_element(self, url: str) -> str:
        """Handle the base element for relative URLs."""
        base_element = url
        try:
            base_element = self.browser.get_base_uri()
        except Exception:
            logging.exception("Failed to get base element %s", url)
            return url

        # Check that the base_element has same domain as base_url
        if not src.filters.url_filter_not_same_domain(base_element, url):
            logging.info(
                "get_links skipped due to equality of: %s %s",
                base_element,
                url,
            )
            return url

        # Check that the protocol is equal between base_element and url
        if not src.filters.url_filter_same_protocol(base_element, url):
            logging.info(
                "get_links skipped due to different protocol of: %s %s",
                base_element,
                url,
            )
            return url

        return base_element

    def get_links(self, base_url: str, url: str) -> list[str]:
        """Get a list of (viable) links on a page.

        Args:
            base_url (str): the base URL being audited
            url (str): url to find links on (within the scope of base_url)

        Returns:
            list[str]: a list of links on the page
        """
        try:
            soup = BeautifulSoup(self.browser.driver.page_source, "lxml")
        except selenium.common.exceptions.TimeoutException:
            logging.exception("Failed to get page source, TimeoutException%s", url)
            return []
        links = []

        all_a_elements = soup.find_all("a", href=True)

        # Handles if <base> element is manipulating relative URLs
        # otherwise, it is simply the 'url' value.
        base_uri = self.handle_base_element(url)

        for new_url in all_a_elements:
            # Compiles the full URL
            href = new_url.get("href").strip()
            try:
                href = urllib.parse.urljoin(base_uri, href)
            except ValueError as exc:
                # Log base_uri, href, and the exception
                logging.exception("Failed to join URL %s %s %s", base_uri, href, exc)
                continue

            # Run a range of filters on the URL
            if not self.url_filter.run_url_filters(href):
                continue

            # If URL is not on the same domain, skip it
            if not src.filters.url_filter_not_same_domain(href, base_url):
                continue

            # If URL has been scanned previously, skip it
            # if self.analytics.is_url_in_pages_scanned(href):
            #    continue

            if len(href) > 2 and base_url == href[:-1]:
                logging.info(
                    "get_links skipped due to equality of: %s %s",
                    base_url,
                    href,
                )
                continue
            links.append(href)

        return links

    def register_audit_plugins(
        self,
        audit_manager: AuditManager,
        new_link: str,
        site_data: SiteData,
    ) -> None:
        """Register audit plugins with AuditManager.

        Args:
            audit_manager (AuditManager): AuditManager instance
            new_link (str): the link to be audited
            site_data (dict[Any, Any]): contains info about the site
        """
        for filename, audit_config in config.audit_plugins.items():
            # Use importlib to dynamically import audit plugins specified
            # inside config.json.
            # audit plugins must be placed inside src/audit_plugins

            # Unpack the config for the audit,
            # and skip the audit if the second arg
            # in config.json for the audit is False
            should_run: bool = audit_config["enabled"]
            if not should_run:
                continue

            audit_module = importlib.import_module(f"src.audit_plugins.{filename}")
            audit_class = getattr(audit_module, config.audit_plugins[filename]["class_name"])
            audit_manager.register_audit(
                audit_name=filename,
                audit_class=audit_class,
                url=new_link,
                site_data=site_data,
                viewport_size=self.browser.get_window_size(),
            )

    def are_url_headers_acceptable(self, base_url: str, parent_url: str, url: str, status_code: int) -> bool:
        """Check if the URL has acceptable headers.

        Args:
            base_url (str): base URL - homepage of website specified
            parent_url (str): parent URL of url
            url (str): URL to check
            status_code (int): status code of the rul

        Returns:
            bool: True if URL has acceptable headers, else False
        """
        if status_code is None:
            status_code = -1

        ok_status_codes = [200, 301, 302, 307, 308]
        if status_code not in ok_status_codes:
            logging.info(
                "URL filtered out due to bad http status_code: %s %i",
                url,
                status_code,
            )
            # Write bad response codes with CSVWriter
            csv_writer = src.output.CSVWriter()
            csv_writer.add_row(
                {
                    "base_url": base_url,
                    "parent_url": parent_url,
                    "url": url,
                    "status_code": status_code,
                }
            )
            if config.record_unexpected_response_codes:
                csv_writer.write_csv_file(f"./results/{config.audit_name}/unexpected_response_codes.csv")

            return False
        return status_code is not None

    def fetch_robots_txt(self, robots_txt_url: str) -> str:
        """Fetches a robots.txt file from a domain.

        This is a custom implementation as the standard library's
        urllib.robotparser.RobotFileParser does not appear to handle
        large file problems, non-UTF-8 chars, or Content-Type checks.

        Args:
            robots_txt_url (str): URL to fetch robots.txt from

        Returns:
            str: robots.txt file
        """
        # Fetch the robots.txt file
        try:
            logging.info("Fetching robots.txt %s", robots_txt_url)
            response = requests.get(robots_txt_url, headers={"User-Agent": config.user_agent}, timeout=10)
            response.raise_for_status()

            # Check Content-Type is text/plain (in a safe way)
            is_content_type_set = "Content-Type" in response.headers
            if is_content_type_set and not re.search(
                "^text/plain(?:;|$)", response.headers["Content-Type"], re.IGNORECASE
            ):
                raise ValueError(
                    f"robots.txt has invalid Content-Type {robots_txt_url} {response.headers['Content-Type']}"
                )
        except requests.exceptions.RequestException as exc:
            logging.error("Failed to fetch robots.txt %s", robots_txt_url)
            raise exc

        logging.info("Fetched robots.txt %s", robots_txt_url)

        robots_txt_content = response.text

        # If the response is > 500 KB
        if len(robots_txt_content) > 1024 * 500:
            logging.warning("robots.txt file is too large (>500 KB) on %s", robots_txt_url)
            raise ValueError(f"robots.txt file is too large (>500 KB) on {robots_txt_url}")

        # Remove any non-UTF-8 characters
        file = robots_txt_content.encode("utf-8", errors="ignore").decode("utf-8")

        return file

    def is_url_allowed_by_robots_txt(self, url: str) -> bool:
        """Checks if a URL's robots.txt allows CWAC.

        Args:
            url (str): URL to check

        Returns:
            bool: True if URL is allowed by robots.txt, else False (True if config disables robots.txt checks)
        """
        if not config.follow_robots_txt:
            return True

        # Get the protocol/domain of the URL
        protocol, domain = urllib.parse.urlparse(url)[:2]

        # If the domain is in config.robots_txt_cache, use that
        if domain in config.robots_txt_cache:
            robot_parser = config.robots_txt_cache[domain]
            logging.info("Using cached robots.txt for %s", domain)
            result = robot_parser.can_fetch(config.user_agent_product_token, url)
            logging.info("robots.txt result for %s was %s", url, "allow" if result else "disallow")
            return result

        # Use urllib.robotparser to parse the robots.txt file
        robot_parser = urllib.robotparser.RobotFileParser()

        # Fetch the robots.txt file
        try:
            robots_txt = self.fetch_robots_txt(f"{protocol}://{domain}/robots.txt")
            robot_parser.parse(robots_txt.splitlines())
        except (requests.exceptions.RequestException, ValueError):
            robot_parser.parse("")
            config.robots_txt_cache[domain] = robot_parser
            logging.exception("Failed to fetch or parse robots.txt - default to allow! %s", domain)
            return True

        # Cache the robotparser object
        config.robots_txt_cache[domain] = robot_parser

        # Check if the URL is allowed by robots.txt
        result = robot_parser.can_fetch(config.user_agent_product_token, url)

        # Log the outcome
        logging.info("robots.txt result for %s was %s", url, "allow" if result else "disallow")

        return result

    def crawl(self, site_data: SiteData, base_url: str) -> None:
        """Crawls a domain and executes the AuditManager.

        Loads a webpage, and runs a set of tests on that page. If
        configured to visit more than one link per domain, it also
        scrapes new links out of the page which are then navigated
        to for further testing and scraping, effectively crawling
        the website.

        Args:
            site_data (SiteData): contains info about the site
            base_url (str): the first url to crawl
        """
        action = "crawl"
        if config.max_links_per_domain == 1:
            action = "visit"
        logging.info("Starting %s of %s", action, base_url)

        # Create an AuditManager instance
        audit_manager = AuditManager(browser=self.browser, analytics=self.analytics)

        # Counts number of test failures
        test_failures = 0

        # Counts number of pages scanned
        pages_scanned = 0

        # queue element: (parent_url, url, depth)
        queue = RandomQueue()
        queue.push((base_url, base_url, 0))

        # track visited urls
        visited = {base_url}

        # Filter and sanitise the initial URL
        if not self.url_filter.run_url_filters(base_url):
            self.record_pages_scanned(site_data, pages_scanned)
            logging.error("base_url was filtered out! %s", base_url)
            return

        while queue:
            parent_url, url, depth = queue.pop()

            if pages_scanned >= config.max_links_per_domain:
                logging.info("Max pages scanned reached %s", base_url)
                break

            # Delay
            time.sleep(config.delay_between_page_loads)

            # Filter/sanitise the URL
            try:
                url = self.url_sanitise(url)
            except ValueError:
                continue

            # Check if URL is allowed by robots.txt
            if not self.is_url_allowed_by_robots_txt(url):
                logging.info("URL disallowed by robots.txt %s", url)
                continue

            # process_url_headers returns a dict with
            # status_code and final_url after redirects
            # status_code is None if an error occurred
            if config.perform_header_check:
                url_data = src.filters.process_url_headers(url, supports_head_requests=site_data["supports_head"])
                url_status_code = url_data["status_code"]
                url = url_data["final_url"]
                if not self.are_url_headers_acceptable(
                    base_url=base_url, parent_url=parent_url, url=url, status_code=url_status_code
                ):
                    continue

            if not self.url_filter.run_url_filters(url):
                continue

            # Confines to URLs that are within the scope of the base_url
            # and prevents URLs that intersect with another base_url
            # (useful for multiple websites on the same domain)
            if not self.url_filter_prevent_intersections(base_url, url):
                continue

            # Check that page has not been scanned before
            if self.analytics.is_url_in_pages_scanned(base_url, url):
                logging.info("URL has been scanned before %s for %s", url, base_url)
                continue

            # Write to audit_log.csv
            csv_writer = CSVWriter()
            csv_writer.add_rows(
                [
                    {
                        "organisation": site_data["organisation"],
                        "base_url": site_data["url"],
                        "url": url,
                        "sector": site_data["sector"],
                    }
                ]
            )
            csv_writer.write_csv_file(f"./results/{config.audit_name}/audit_log.csv")

            self.register_audit_plugins(audit_manager, url, site_data)
            test_success = audit_manager.run_audits()

            if test_success:
                self.analytics.add_page_scanned(base_url, url)
                test_failures = 0
                pages_scanned += 1
            else:
                test_failures += 1
                if test_failures >= 3:
                    self.analytics.record_test_failure(base_url)
                    self.record_pages_scanned(site_data, pages_scanned)
                    logging.error("Too many sequential test failures, skipping %s", url)
                    return

            # don't bother getting links if we are only scanning one link per base url
            if config.max_links_per_domain == 1:
                break

            links = self.get_links(base_url, url)

            # Add all links to the queue
            for new_link in links:
                if new_link not in visited:
                    visited.add(new_link)
                    queue.push((url, new_link, depth + 1))

        self.analytics.record_test_failure(base_url)
        self.record_pages_scanned(site_data, pages_scanned)
        if config.max_links_per_domain != 1:
            logging.info("Crawl exhausted all links %s", base_url)

    def record_pages_scanned(self, site_data: SiteData, pages_scanned: int) -> None:
        """Record the number of pages that were scanned for the site."""
        with config.lock:
            csv_writer = src.output.CSVWriter()
            csv_writer.add_rows(
                [
                    {
                        "organisation": site_data["organisation"],
                        "base_url": site_data["url"],
                        "number_of_pages": pages_scanned,
                        "sector": site_data["sector"],
                    }
                ]
            )
            csv_writer.write_csv_file(f"./results/{config.audit_name}/pages_scanned.csv")


class RandomQueue:
    """A queue that pops in random order, but biased toward 0."""

    def __init__(self) -> None:
        """Initialise the queue."""
        self.items: list[Any] = []

    def __len__(self) -> int:
        """Return the length of the queue."""
        return len(self.items)

    def __str__(self) -> str:
        """Return the queue as a string."""
        return str(self.items)

    def push(self, item: Any) -> None:
        """Push an item onto the queue.

        Args:
            item (Any): item to push onto the queue
        """
        self.items.append(item)

    def pop(self) -> Any:
        """Pop an item off the queue.

        Returns:
            Any: item popped off the queue
        """
        index = self.biased_rand(len(self.items))
        return self.items.pop(index)

    def biased_rand(self, maximum: int) -> int:
        """Generate a random number with a bias towards 0.

        Args:
            maximum (int): maximum value

        Returns:
            int: random number
        """
        # these random numbers are not used for security
        # or cryptographic purposes so it is safe to use
        # and 'nosec' is added to suppress bandit warning.
        random_number = random.random()  # nosec
        random_number *= random.random()  # nosec
        return int(maximum * random_number)

    def clear(self) -> None:
        """Clear the queue."""
        self.items = []
