"""A wrapper class for the webdriver.

Contains useful functions for managing browsers.
"""

import logging
import os
import platform
import time
from typing import Any

import selenium.common.exceptions
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver

from config import Config

WebDriverType = ChromeWebDriver

logger = logging.getLogger('cwac')


class Browser:
  """A wrapper class for selenium webdriver."""

  def __init__(self, config: Config, thread_id: int) -> None:
    """Init variables and spawns webdriver."""
    self.config = config
    self.thread_id = thread_id
    self.num_retries = 2
    self.viewport_size = {'width': 320, 'height': 450}
    self.driver: WebDriverType = self.spawn_single_webdriver(
      window_size=next(iter(self.config.viewport_sizes.values()))
    )
    self.last_url_req = ''

  def get(self, url: str) -> bool:
    """Load a URL in the webdriver.

    Args:
        url (str): url to load

    Returns:
        bool: True if page loaded, False if something went wrong
    """
    # If only_allow_https is set, check that the URL is HTTPS
    if self.config.only_allow_https and not url.startswith('https://'):
      logger.info('Skipping %s as only_allow_https is set', url)
      return False

    for attempts in range(self.num_retries):
      try:
        logger.info('Running .get: %s', url)
        self.driver.get(url)
        logger.info('.get successful')
        self.driver.set_script_timeout(self.config.script_timeout)
        self.driver.set_page_load_timeout(self.config.page_load_timeout)
        self.last_url_req = url
        break
      except selenium.common.exceptions.TimeoutException:
        logger.exception('Timeout exception: %s, attempt:%i', url, attempts)
        if attempts == self.num_retries - 1:
          logger.info('%i attempts failed to .get: %s', attempts + 1, url)
          return False
      except selenium.common.exceptions.WebDriverException:
        logger.exception('WebDriverException')
        if attempts == self.num_retries - 1:
          logger.info('%i attempts failed to .get: %s', attempts + 1, url)
          return False
        self.safe_restart()
      except Exception:  # pylint: disable=broad-exception-caught
        logger.exception('Unhandled exception')
        if attempts == self.num_retries - 1:
          logger.info('%i attempts failed to .get: %s', attempts + 1, url)
          return False

    # Delay to allow page to load more
    time.sleep(self.config.delay_after_page_load)
    return True

  def safe_restart(self) -> None:
    """Restart the webdriver."""
    try:
      self.driver.quit()
    except selenium.common.exceptions.InvalidSessionIdException:
      logger.exception('InvalidSessionIdException, browser probably crashed')
    except selenium.common.exceptions.WebDriverException as error:
      # check if 'message' is "disconnected: not connected to DevTools"
      if 'disconnected' in str(error):
        logger.exception(
          'WebDriverException, browser probably crashed %s',
          self.last_url_req,
        )
    except urllib3.exceptions.HTTPError:
      logger.exception('urllib3 HTTPError, browser probably hung %s', self.last_url_req)
    self.driver = self.spawn_single_webdriver(window_size=self.viewport_size)
    self.last_url_req = ''

  def close(self) -> None:
    """Close the browser."""
    logger.info('Quitting browser')
    try:
      self.driver.quit()
    except (selenium.common.exceptions.WebDriverException, urllib3.exceptions.HTTPError):
      logger.exception('Failed to quit browser')
    self.last_url_req = ''

  def set_window_size(self, width: int, height: int) -> None:
    """Set browser size.

    Args:
        width (int): width of browser.
        height (int): height of browser.
    """
    try:
      self.viewport_size = {'width': width, 'height': height}
      self.driver.set_window_size(width, height)
    except (selenium.common.exceptions.WebDriverException, urllib3.exceptions.HTTPError):
      logger.exception('Failed to set window size')
      self.safe_restart()

  def spawn_single_webdriver(self, window_size: dict[Any, Any], headless_override: bool = False) -> WebDriverType:
    """Spawn a single instance of a browser.

    Args:
        window_size (dict[Any, Any]): window dimensions of browser.
        headless_override (bool, optional): override headless setting.

    Returns:
        WebDriverType: a webdriver object.
    """
    # Get appropriate null path for OS
    null_path = '/dev/null'
    if platform.system() == 'Windows':
      null_path = 'NUL'

    chrome_options = webdriver.ChromeOptions()
    if self.config.headless or headless_override:
      chrome_options.add_argument('--headless')
    chrome_options.add_argument(f'--window-size={window_size["width"]},{window_size["height"]}')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'disable-popup-blocking'])
    chrome_options.add_argument('--disable-notifications')

    for arg in os.environ.get('CHROME_EXTRA_ARGS', '').split(','):
      if arg.strip():
        chrome_options.add_argument(arg.strip())

    # Set fake user agent
    chrome_options.add_argument(f'user-agent={self.config.user_agent}')

    chrome_options.unhandled_prompt_behavior = 'dismiss'

    # Disable downloads
    chrome_options.add_experimental_option(
      'prefs',
      {
        'download.default_directory': null_path,
        'download.prompt_for_download': False,
      },
    )

    chrome_service = Service(
      self.config.chrome_driver_location,
      service_args=[
        '--verbose',
        '--log-path=./results/' + self.config.audit_name + '/chromedriver.log',
      ],
    )

    # Set binary path
    chrome_options.binary_location = self.config.chrome_binary_location

    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    driver.set_script_timeout(self.config.script_timeout)
    driver.set_page_load_timeout(self.config.page_load_timeout)

    x_pos = 100 + 400 * (self.thread_id % 4)
    y_pos = 0 if self.thread_id < 4 else 400
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(**window_size)

    return driver
