"""Loads a config object from config_[xyz].json."""

import csv
import datetime
import json
import os
import platform
import re
import sys
import threading
import urllib.robotparser
from logging import INFO, FileHandler, Formatter, getLogger
from typing import Any, TypedDict, cast
from urllib import parse

logger = getLogger('cwac')


class SiteData(TypedDict):
  """Holds data for a site that should be crawled and audited."""

  organisation: str
  url: str
  sector: str
  supports_head: bool


class Config:
  """A config class used throughout CWAC.

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
  shuffle_base_urls: bool
  base_urls_visit_path: str
  base_urls_nohead_path: str
  filter_to_organisations: list[str]
  filter_to_urls: list[str]
  viewport_sizes: dict[str, dict[str, int]]
  audit_plugins: dict[str, dict[str, Any]]
  record_unexpected_response_codes: bool
  force_open_details_elements: bool

  # Threading lock (shared amongst all threads)
  lock = threading.RLock()

  def __init__(self, config_filename: str) -> None:
    """Read config.json into self.config."""
    with open('./config/' + config_filename, 'r', encoding='utf-8-sig') as file:
      self.config = json.load(file)

    self.unique_id = 0

    # Sanitise audit_name
    self.config['audit_name'] = self.sanitise_string(self.audit_name)

    # Add a timestamp to the test name
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    self.config['audit_name'] = timestamp + '_' + self.audit_name

    # Create the results folder
    folder_path = './results/' + self.audit_name + '/'
    os.makedirs(folder_path, exist_ok=True)

    # Configure logging
    self.__setup_logger(f'./{folder_path}/{self.audit_name}.log')

    # Write self.config to the results folder for reference
    with open(f'{folder_path}/config.json', 'w', encoding='utf-8-sig') as file:
      json.dump(self.config, file, indent=4)

    self.__resolve_automatic_settings()

    # Ensure base_urls_visit_path is within base_urls folder
    if not self.is_path_subdir(self.base_urls_visit_path, './base_urls'):
      raise ValueError('base_urls_visit_path must be within base_urls folder')

    # Ensure base_urls_nohead_path is within base_urls folder
    if not self.is_path_subdir(self.base_urls_nohead_path, './base_urls'):
      raise ValueError('base_urls_nohead_path must be within base_urls folder')

    self.audit_subjects: list[SiteData] = self.__import_base_urls()

    self.url_lookup = self.__map_base_urls_by_domain()

    # global variable to store robots.txt data
    # the Crawler queries this and populates it
    # if no entry is found for a website.
    self.robots_txt_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

  def __setup_logger(self, log_filename: str) -> None:
    """Set up the CWAC logger for a new run.

    Args:
        log_filename (str): The filename of the log file.
    """
    # remove any existing handlers
    for h in logger.handlers[:]:
      logger.removeHandler(h)
      h.close()

    # set the level back to INFO
    logger.setLevel(INFO)

    # create a new formatter with our desired format
    formatter = Formatter(
      '[{%(asctime)s} %(levelname)-7s %(filename)10s : %(lineno)-4s] %(funcName)30s %(message)s %(threadName)s',
      # Log timestamp format (ISO 8601)
      '%Y-%m-%dT%H:%M:%S%z',
    )

    # add a new file handler with our desired format
    handler = FileHandler(log_filename, 'w')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

  def __normalize_url(self, url: str) -> str:
    """Normalize a URL, making it lowercase and stripping out any extra whitespace.

    Args:
        url (str): URL to normalize

    Returns:
        str: normalize URL
    """
    parsed = parse.urlparse(url)
    modified = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    return parse.urlunparse(modified)

  def __import_base_urls_without_head_support(self) -> set[str]:
    """Import base urls that don't support HEAD requests.

    Returns:
        set[str]: a list of base urls that don't support HEAD requests
    """
    folder_path = self.base_urls_nohead_path
    base_urls = set()

    for filename in os.listdir(folder_path):
      if filename.endswith('.csv'):
        with open(
          os.path.join(folder_path, filename),
          encoding='utf-8-sig',
          newline='',
        ) as file:
          reader = csv.reader(file)
          header = next(reader)
          for row in reader:
            dict_row = cast(dict[str, str], dict(zip(header, row)))

            # Strip whitespace from URL
            dict_row['url'] = dict_row['url'].strip()

            # Make the URL lowercase
            dict_row['url'] = self.__normalize_url(dict_row['url'])

            base_urls.add(dict_row['url'])
    return base_urls

  def __should_skip_row(self, row: SiteData) -> bool:
    """Check if a row should be skipped.

    Checks if a URL/Organisation should be included
    in the audit according to config_default.json's
    filter_to_organisations and
    filter_to_urls.

    Args:
        subject (AuditSubject): an audit subject parsed from a CSV

    Returns:
        bool: True if the subject should be skipped, False otherwise
    """
    found_org = False
    if self.filter_to_organisations:
      for org in self.filter_to_organisations:
        if org in row['organisation']:
          found_org = True
          break

    found_url = False
    if self.filter_to_urls:
      for url in self.filter_to_urls:
        if url in row['url']:
          found_url = True
          break

    if self.filter_to_organisations and self.filter_to_urls:
      return not (found_org and found_url)
    if self.filter_to_organisations:
      return not found_org
    if self.filter_to_urls:
      return not found_url

    return False

  def __import_base_urls(self) -> list[SiteData]:
    subjects: list[SiteData] = []

    folder_path = self.base_urls_visit_path

    headless_base_urls = self.__import_base_urls_without_head_support()

    for filename in os.listdir(folder_path):
      if filename.endswith('.csv'):
        with open(
          os.path.join(folder_path, filename),
          encoding='utf-8-sig',
          newline='',
        ) as file:
          reader = csv.reader(file)
          header = next(reader)
          for row in reader:
            if len(row) != 3:
              raise ValueError(
                'CSV files must have 3 columns',
                row,
                filename,
              )

            subject = cast(SiteData, dict(zip(header, row)))

            # Parse the URL to get just the domain
            parsed_url = parse.urlparse(subject['url'])

            if parsed_url.scheme == '':
              logger.error('URL missing protocol, skipping %s', subject['url'])
              continue

            # If only_allow_https is True, then only add
            # URLs that start with https://
            if self.only_allow_https and parsed_url.scheme != 'https':
              logger.error(
                'only_allow_https is True, skipping %s',
                subject['url'],
              )
              continue

            if self.__should_skip_row(subject):
              continue

            subject['url'] = self.__normalize_url(subject['url'])

            subject['supports_head'] = subject['url'] not in headless_base_urls

            subjects.append(subject)

    return subjects

  def __resolve_automatic_settings(self) -> None:
    """Resolve configuration settings which are set to 'auto'.

    If a value cannot be automatically determined for a particular setting,
    such as because the OS or arch is not supported, then an error will be
    raised requesting the option be set manually in the config file
    """
    info = platform.uname()

    if self.chrome_binary_location == 'auto':
      chrome_version = self.__determine_chrome_version()

      if info.system == 'Linux' and info.machine == 'x86_64':
        self.chrome_binary_location = f'./chrome/linux-{chrome_version}/chrome-linux64/chrome'
      elif info.system == 'Darwin' and info.machine == 'arm64':
        # pylint: disable-next=line-too-long
        self.chrome_binary_location = f'./chrome/mac_arm-{chrome_version}/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'  # noqa: E501
      else:
        raise ValueError(
          f'chrome_binary_location cannot be automatically determined for {info.system} {info.machine} '
          f'- please set chrome_binary_location manually'
        )

    if self.chrome_driver_location == 'auto':
      if info.system == 'Linux' and info.machine == 'x86_64':
        self.chrome_driver_location = './drivers/chromedriver_linux_x64'
      elif info.system == 'Darwin' and info.machine == 'arm64':
        self.chrome_driver_location = './drivers/chromedriver_mac_arm64'
      else:
        raise ValueError(
          f'chrome_driver_location cannot be automatically determined for {info.system} {info.machine} '
          f'- please set chrome_driver_location manually'
        )

  def __determine_chrome_version(self) -> str:
    with open('package.json', 'r', encoding='utf-8-sig') as file:
      package_json = json.load(file)

      return str(package_json['config']['chromeVersion'])

  def sanitise_string(self, string: str) -> str:
    """Sanitise a string for use in a folder/filename.

    Args:
        string (str): the string to sanitise

    Returns:
        str: a sanitised string
    """
    temp_str = string.strip()
    temp_str = re.sub(r'[^a-zA-Z0-9_\-.]', '_', temp_str)
    temp_str = re.sub(r'_+', '_', temp_str)
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

  def __getattr__(self, name: str) -> Any:
    """Get attribute from config dict.

    Args:
        name (str): the name of the attribute (in config.json)
    """
    if name == 'lock':
      return self.config.lock
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
      if not re.match(r'^[a-zA-Z0-9_.-]+$', config_filename):
        raise ValueError('config_filename must be alphanumeric, underscores, and hyphens')
    else:
      config_filename = 'config_default.json'
    with open('./config/' + config_filename, 'r', encoding='utf-8-sig') as file:
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

    if domain not in self.url_lookup:
      logger.warning('Agency data missing for: %s', url)
      return {'organisation': 'Unknown', 'sector': 'Unknown'}
    return {
      'organisation': self.url_lookup[domain]['organisation'],
      'sector': self.url_lookup[domain]['sector'],
    }

  def __map_base_urls_by_domain(self) -> dict[str, dict[str, str]]:
    """Build a dictionary mapping base url information to their domain.

    This data is primarily used for looking up the agency details
    given a URL by using the lookup_organisation() method.

    Returns:
        dict[str, dict[str, str]]: a dictionary with the URL as the key,
        and a list that contains the agency name, and the sector
        as the value.
    """
    base_urls: dict[str, dict[str, str]] = {}

    for subject in self.audit_subjects:
      # Parse the URL to get just the domain
      parsed_url = parse.urlparse(subject['url'])

      # Cast to lowercase
      domain = parsed_url.netloc.lower()

      # Strip whitespace
      domain = domain.strip()

      base_urls[domain] = {
        'organisation': subject['organisation'],
        'sector': subject['sector'],
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
