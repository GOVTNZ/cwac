"""URL filters."""

import urllib.parse
from logging import getLogger
from typing import Any, Callable

import requests

from config import Config

# url_filter_* functions are declared here
# url_filter_* functions return True when a URL is acceptable
# url_filter_* functions must be registered in the URLFilter class
# by using register_url_filter(func)


logging = getLogger("cwac")


def url_filter_whitelist(config: Config, url: urllib.parse.ParseResult) -> bool:
    """Filter out URLs not in whitelist.

    Args:
        config (Config): The configuration to use
        url (urllib.parse.ParseResult): A URL to filter

    Returns:
        bool: True if URL is valid, else False
    """
    netloc_without_www = url.netloc.removeprefix("www.").lower()

    netloc_with_www = url.netloc.lower()

    if not url.netloc.startswith("www."):
        netloc_with_www = "www." + url.netloc

    return netloc_without_www in config.url_lookup or netloc_with_www in config.url_lookup


def url_filter_https_only(config: Config, url: urllib.parse.ParseResult) -> bool:
    """Filter out non-https URLs if config.only_allow_https is True.

    Args:
        config (Config): The configuration to use
        url (urllib.parse.ParseResult): A URL to filter

    Returns:
        bool: True if URL is valid, else False
    """
    if config.only_allow_https:
        return url.scheme == "https"
    return True


def url_filter_fragment(_config: Config, url: urllib.parse.ParseResult) -> bool:
    """Filter out same-page URLs.

    Args:
        _config (Config): The configuration to use
        url (urllib.parse.ParseResult): A URL to filter

    Returns:
        bool: True if URL is valid, else False
    """
    return url.fragment == ""


def url_filter_http(_config: Config, url: urllib.parse.ParseResult) -> bool:
    """Filter out non-http/https URLs.

    Args:
        _config (Config): The configuration to use
        url (urllib.parse.ParseResult): A URL to filter

    Returns:
        bool: True of URL is valid, else False
    """
    return url.scheme in ("http", "https")


def url_filter_filetype(_config: Config, url: urllib.parse.ParseResult) -> bool:
    """Filter out common file extensions in URLs.

    Args:
        _config (Config): The configuration to use
        url (urllib.parse.ParseResult): A URL to filter

    Returns:
        bool: True if URL is valid, else False
    """
    disallowed_file_types = {
        ".xml",
        ".gif",
        ".csv",
        ".xls",
        ".xlsx",
        ".dmg",
        ".exe",
        ".wmv",
        ".wma",
        ".flv",
        ".ppt",
        ".py",
        ".pptx",
        ".jpg",
        ".jpeg",
        ".png",
        ".avi",
        ".mov",
        ".m4a",
        ".m4v",
        ".mp3",
        ".mp4",
        ".doc",
        ".docx",
        ".pdf",
        ".swf",
        ".jar",
        ".tar.gz",
        ".zip",
        ".iso",
        ".crt",
        ".crl",
        ".pem",
        ".key",
        ".pfx",
        ".p12",
        ".der",
        ".cer",
        ".psd",
        ".ai",
        ".eps",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        ".svg",
        ".srt",
        ".wav",
        ".brf",
        ".txt",
    }

    lowercase_path = url.path.lower()

    return not lowercase_path.endswith(tuple(disallowed_file_types))


def url_filter_not_same_domain(url_a: str, url_b: str) -> bool:
    """Filter out url_a when url_a and url_b have different domains.

    Args:
        url_a (str): A url to compare with url_b
        url_b (str): A url to compare with url_a

    Returns:
        bool: True if url_b is within domain of url_a, else False
    """
    # Ensure netloc are lowercase
    domain_a = urllib.parse.urlparse(url_a).netloc.lower()
    domain_b = urllib.parse.urlparse(url_b).netloc.lower()

    domain_a = domain_a.removeprefix("www.")
    domain_b = domain_b.removeprefix("www.")

    if domain_a != domain_b:
        logging.info("url out due to domain mismatch %s %s", url_a, url_b)
    return domain_a == domain_b


def url_filter_by_header_content_type(url: str, headers: dict[Any, Any]) -> bool:
    """Filter out when invalid Content-Type is set.

    Args:
        url (str):: url that headers were retrieved from
        headers (dict[Any, Any]): headers from a server

    Returns:
        bool: True if headers are ok, else False
    """
    try:
        headers = {k.lower(): v for k, v in headers.items()}
        if not headers["content-type"].startswith("text/html"):
            logging.info(
                "URL filtered due to a non-text/html response %s: %s",
                url,
                headers["content-type"],
            )
            return False
    except KeyError:
        logging.error("KeyError was encountered %s %s", url, headers)
        return False

    return True


def process_url_headers(config: Config, url: str, supports_head_requests: bool = True) -> dict[Any, Any]:
    """Process a URL by handling the headers.

    It does the following:
        - checks HTTP status code
        - checks Content-Type
        - Redirects and resolves to final_url

    Args:
        config (Config): configuration details
        url (str): A URL to filter
        supports_head_requests (bool): whether the URL supports HEAD requests

    Returns:
        dict[Any, Any]]: A dict of status_code, final_url
    """
    success = True
    timeout = (10, 10)
    output = {"status_code": -1, "final_url": url}
    final_url = None
    method = "head"

    if not supports_head_requests:
        method = "get"
        logging.info(
            "%s is marked as not supporting HEAD requests, using GET instead to check headers",
            url,
        )

    # Try to get the headers 2 times
    for i in range(3):
        try:
            # Set the user agent string
            ua_string = {"User-Agent": config.user_agent}
            headers = requests.request(method, url, headers=ua_string, timeout=timeout, allow_redirects=True)

            # this response does not really make sense, but if it does happen we might as well skip remaining retries
            if headers.status_code == 405 and method != "get":
                method = "get"
                logging.warning(
                    "%s does not support HEAD requests, retrying with GET (status code %i)",
                    url,
                    headers.status_code,
                )
                continue

            final_url = headers.url
            logging.info("%s has status code %i", url, headers.status_code)
            break
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("Failed to get headers; attempt: %d, %s", i + 1, url)
            if i == 2:
                logging.error("Giving up on headers check; attempt: %d, %s", i + 1, url)
                return output

    # check content-type
    if success and not url_filter_by_header_content_type(url, dict(headers.headers)):
        success = False

    if success:
        output["status_code"] = headers.status_code
        output["final_url"] = final_url

    return output


def url_filter_same_protocol(url_a: str, url_b: str) -> bool:
    """Filter url_a if url_b has different protocol.

    Args:
        url_a (str): A url to compare with url_b
        url_b (str): A url to compare with url_a

    Returns:
        bool: True if url_b is within domain of url_a, else False
    """
    try:
        parsed_a = urllib.parse.urlparse(url_a)
        parsed_b = urllib.parse.urlparse(url_b)
    except Exception as e:
        logging.error("Failed to parse URL: %s", e)
        return False

    return parsed_a.scheme == parsed_b.scheme


class URLFilter:
    """Registers and runs a set of url_filter functions."""

    def __init__(self, config: Config) -> None:
        """Init vars, and registers url_filters."""
        self.config = config

        self.url_filters: dict[str, Callable[[Config, urllib.parse.ParseResult], bool]] = {}

        # Register URL filtration functions defined at the top of this file
        self.register_url_filter("Non-empty fragment", url_filter_fragment)
        self.register_url_filter("HTTPS only", url_filter_https_only)
        self.register_url_filter("Non-http/s path", url_filter_http)
        self.register_url_filter("Non-allowed file extension", url_filter_filetype)
        self.register_url_filter("Whitelist", url_filter_whitelist)

    def register_url_filter(
        self,
        filter_name: str,
        filter_func: Callable[[Config, urllib.parse.ParseResult], bool],
    ) -> None:
        """Register a url_filter_* function defined in this file.

        Args:
            filter_name (str): Human-readable name for the filter
            filter_func: a function that filters URLs
        """
        self.url_filters[filter_name] = filter_func

    def run_url_filters(self, url: str) -> bool:
        """Iterate through registered url_filters and runs them.

        Args:
            url (str): The URL to run filtration on
        """
        try:
            parsed_url = urllib.parse.urlparse(url)
        except Exception as e:
            logging.error("Failed to parse URL: %s", e)
            return False

        for filter_name, filter_func in self.url_filters.items():
            if not filter_func(self.config, parsed_url):
                logging.info("%s filter rejected %s", filter_name, url)
                return False
        return True
