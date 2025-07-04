"""Loads a config object from config_[xyz].json."""

import csv
import datetime
import json
import logging
import os
import re
import sys
import threading
import urllib.robotparser
from typing import Any
from urllib import parse


class Config:
    """A global config class used throughout CWAC.

    Config settings are stored in ./config/config_[xyz].json.
    """

    # Enables autocomplete
    audit_name: str
    headless: bool
    max_links_per_domain: int
    thread_count: int
    browser: str
    chrome_binary_location: str
    chrome_driver_location: str
    user_agent: str
    user_agent_product_token: str
    follow_robots_txt: bool
    script_timeout: int
    page_load_timeout: int
    delay_between_page_loads: int
    delay_between_viewports: int
    delay_after_page_load: int
    only_allow_https: bool
    perform_header_check: bool
    nocrawl_mode: bool
    shuffle_base_urls: bool
    base_urls_crawl_path: str
    base_urls_nocrawl_path: str
    base_urls_nohead_path: str
    filter_to_organisations: list[str]
    filter_to_domains: list[str]
    viewport_sizes: dict[str, dict[str, int]]
    audit_plugins: dict[str, dict[str, Any]]
    check_for_broken_internal_links: bool
    force_open_details_elements: bool

    # Threading lock (shared amongst all threads)
    lock = threading.RLock()

    # global variable to store robots.txt data
    # the Crawler queries this and populates it
    # if no entry is found for a website.
    robots_txt_cache: dict[str, urllib.robotparser.RobotFileParser]

    def __init__(self) -> None:
        """Read config.json into self.config."""
        self.config = self.read_config()

        self.unique_id = 0

        # Sanitise audit_name
        self.config["audit_name"] = self.sanitise_string(self.config["audit_name"])

        # Add a timestamp to the test name
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.config["audit_name"] = timestamp + "_" + self.config["audit_name"]

        # Configure logging
        log_filename = self.config["audit_name"]
        log_format = (
            "[{%(asctime)s} %(levelname)-7s %(filename)10s : %(lineno)-4s] %(funcName)30s %(message)s %(threadName)s"
        )

        # Create the results folder
        folder_path = "./results/" + log_filename + "/"
        os.makedirs(folder_path, exist_ok=True)

        # Log timestamp format (ISO 8601)
        log_date_format = "%Y-%m-%dT%H:%M:%S%z"

        logging.basicConfig(
            filename=f"./{folder_path}/{log_filename}.log",
            format=log_format,
            filemode="w",
            level=logging.INFO,
            datefmt=log_date_format,
        )

        # Write self.config to the results folder for reference
        with open(f"{folder_path}/config.json", "w", encoding="utf-8-sig") as file:
            json.dump(self.config, file, indent=4)

        # Ensure base_url_crawl_path is within base_urls folder
        if not self.is_path_subdir(self.config["base_urls_crawl_path"], "./base_urls"):
            raise ValueError("base_urls_crawl_path must be within base_urls folder")

        # Ensure base_url_nocrawl_path is within base_urls folder
        if not self.is_path_subdir(self.config["base_urls_nocrawl_path"], "./base_urls"):
            raise ValueError("base_urls_nocrawl_path must be within base_urls folder")

        # Ensure base_urls_nohead_path is within base_urls folder
        if not self.is_path_subdir(self.config["base_urls_nohead_path"], "./base_urls"):
            raise ValueError("base_urls_nohead_path must be within base_urls folder")

        self.config["url_lookup"] = self.import_url_lookup_files()

        # global variable to store robots.txt data
        # the Crawler queries this and populates it
        # if no entry is found for a website.
        self.config["robots_txt_cache"] = {}

        # nocrawl_mode changes max_links_per_domain = 1
        if self.config["nocrawl_mode"]:
            logging.info("nocrawl_mode True config.json, max_links_per_domain = 1")
            logging.info("nocrawl_mode is True, using nocrawl_path_to_audit_log")
            self.config["max_links_per_domain"] = 1

    def sanitise_string(self, string: str) -> str:
        """Sanitise a string for use in a folder/filename.

        Args:
            string (str): the string to sanitise

        Returns:
            str: a sanitised string
        """
        temp_str = string.strip()
        temp_str = re.sub(r"[^a-zA-Z0-9_\-.]", "_", temp_str)
        temp_str = re.sub(r"_+", "_", temp_str)
        temp_str = temp_str[:50]
        return temp_str

    def get_unique_id(self) -> str:
        """Get a unique ID for an audit.

        Returns:
            str: a unique ID
        """
        with self.lock:
            self.unique_id += 1
            return str(self.unique_id)

    def __setattr__(self, attr_name: str, attr_value: Any) -> None:
        """Set a config value (not saved to disk).

        Args:
            attr_name (str): attribute name
            attr_value (Any): attribute value
        """
        self.__dict__[attr_name] = attr_value

    def __getattr__(self, name: str) -> Any:
        """Get attribute from config dict.

        Args:
            name (str): the name of the attribute (in config.json)
        """
        if name == "lock":
            return config.lock
        return self.config[name]

    def read_config(self) -> Any:
        """Read the config.json file and return it.

        Returns:
            dict (Any): a dict of the contents of test_config.json
        """
        # First arg passed to CWAC is the config filename
        if len(sys.argv) > 1:
            config_filename = sys.argv[1]
            # Only accept alphanumeric, underscores, dots, and hyphens
            if not re.match(r"^[a-zA-Z0-9_.-]+$", config_filename):
                raise ValueError("config_filename must be alphanumeric, underscores, and hyphens")
        else:
            config_filename = "config_default.json"
        with open("./config/" + config_filename, "r", encoding="utf-8-sig") as file:
            # Write the config file to the results folder
            return json.load(file)

    def lookup_organisation(self, url: str) -> dict[str, str]:
        """Lookup the agency details from a URL.

        Args:
            url (str): the URL to lookup

        Returns:
            dict[str, str]: a dictionary with "organisation" and
            "sector" as the keys, and the agency name and sector as
            the values.
        """
        # Parse the URL to get just the domain
        parsed_url = parse.urlparse(url)
        domain = parsed_url.netloc.lower()

        if domain not in self.config["url_lookup"]:
            logging.warning("Agency data missing for: %s", url)
            return {"organisation": "Unknown", "sector": "Unknown"}
        return {
            "organisation": self.config["url_lookup"][domain]["organisation"],
            "sector": self.config["url_lookup"][domain]["sector"],
        }

    def import_url_lookup_files(self) -> dict[str, dict[str, str]]:
        """Import all CSV files in base_urls_crawl_path.

        This data is primarily used for looking up the agency details
        given a URL by using the lookup_organisation() method.

        Returns:
            dict[str, dict[str, str]]: a dictionary with the URL as the key,
            and a list that contains the agency name, and the sector
            as the value.
        """
        base_urls: dict[str, dict[str, str]] = {}

        for filename in os.listdir(self.config["base_urls_crawl_path"]):
            if filename.endswith(".csv"):
                with open(
                    os.path.join(self.config["base_urls_crawl_path"], filename),
                    encoding="utf-8-sig",
                    newline="",
                ) as file:
                    reader = csv.reader(file)
                    next(reader)
                    for row in reader:
                        if len(row) != 3:
                            raise ValueError(
                                "crawl_path_to_audit_log CSV files must have 3 columns",
                                row,
                                filename,
                            )

                        # Parse the URL to get just the domain
                        parsed_url = parse.urlparse(row[1])

                        # Protocol
                        if parsed_url.scheme == "":
                            logging.error("URL missing protocol, skipping %s", row[1])
                            continue

                        # Cast to lowercase
                        domain = parsed_url.netloc.lower()

                        # Strip whitespace
                        domain = domain.strip()

                        # If only_allow_https is True, then only add
                        # URLs that start with https://
                        if self.config["only_allow_https"] and parsed_url.scheme != "https":
                            logging.error(
                                "only_allow_https is True, skipping %s",
                                row[1],
                            )
                            continue

                        base_urls[domain] = {
                            "organisation": row[0],
                            "sector": row[2],
                        }
        return base_urls

    def is_path_subdir(self, path: str, parent_path: str) -> bool:
        """Check if a path is a subdirectory of another path.

        Args:
            path (str): the path to check
            parent_path (str): the parent path

        Returns:
            bool: True if path is a subdirectory of parent_path
        """
        parent_path = os.path.realpath(parent_path)
        path = os.path.realpath(path)

        # os.path.commonpath() returns the longest path that is a
        # parent of all the paths in its arguments
        common_path = os.path.commonpath([path, parent_path])

        # If the common path is the same as the parent path, then
        # path is a subdirectory of parent_path
        return common_path == parent_path


config = Config()
