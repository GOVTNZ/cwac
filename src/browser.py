"""A wrapper class for the webdriver.

Contains useful functions for managing browsers.
"""

import json
import logging
import os
import platform
import shutil
import tempfile
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
    self._chrome_tmp_dir: str | None = None
    self.viewport_size = next(iter(self.config.viewport_sizes.values()))
    self.driver: WebDriverType = self.spawn_single_webdriver(window_size=self.viewport_size)
    self.requested_url = ''

  def get(self, url: str) -> bool:
    """Load a URL in the webdriver.

    Args:
        url (str): url to load

    Returns:
        bool: True if page loaded, False if something went wrong
    """
    self.requested_url = ''
    for attempts in range(self.num_retries):
      try:
        logger.info('Running .get: %s', url)
        self.driver.get(url)
        logger.info('.get successful')
        self.requested_url = url
        break
      except selenium.common.exceptions.TimeoutException:
        logger.exception('Timeout exception: %s, attempt:%i', url, attempts)
        if attempts == self.num_retries - 1:
          logger.error('%i attempts failed to .get: %s', attempts + 1, url)
          return False
      except selenium.common.exceptions.WebDriverException:
        logger.exception('WebDriverException')
        if attempts == self.num_retries - 1:
          logger.error('%i attempts failed to .get: %s', attempts + 1, url)
          return False
        self.safe_restart()
      except Exception:  # pylint: disable=broad-exception-caught
        logger.exception('Unhandled exception')
        if attempts == self.num_retries - 1:
          logger.error('%i attempts failed to .get: %s', attempts + 1, url)
          return False

    # Delay to allow page to load more
    time.sleep(self.config.delay_after_page_load)
    return True

  def evaluate(self, js: str) -> Any:
    """Evaluate a JavaScript snippet on the current page using CDP.

    The snippet is run with Runtime.evaluate, so it behaves like `eval`:
    https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#method-Runtime-evaluate

    The snippet is run in the global scope but wrapped in a block so that lexical
    declarations (`let`, `const`, and `class`) are scoped to each call, preventing
    redeclaration errors across calls that use the same names.

    The value of the last statement is returned; if it's a Promise, it's awaited
    and the resolved value is returned instead.

    Snippets involving promises should use `Promise.race` against `config.script_timeout`
    to ensure they don't hang, as CDP only supports timing out for synchronous execution.

    Args:
        js (str): the JavaScript snippet to evaluate

    Returns:
        Any: the result as JSON; values that aren't JSON-serializable don't round-trip
            (functions come back as `{}`, NaN as None, and DOM nodes as junk)

    Raises:
        selenium.common.exceptions.JavascriptException: if the snippet throws
        selenium.common.exceptions.WebDriverException: if synchronous execution times out
    """
    response = self.driver.execute_cdp_cmd(
      'Runtime.evaluate',
      {
        # wrap the snippet in a block to scope locals
        'expression': f'{{\n{js}\n}}',
        'returnByValue': True,
        'awaitPromise': True,
        # this only applies to synchronous evaluations, and will surface as a generic
        # WebDriverException; asynchronous evaluations should include a Promise.race
        'timeout': self.config.script_timeout * 1000,
      },
    )

    if 'exceptionDetails' in response:
      # exceptions here are effectively always bugs (ours or the page's), so rather
      # than trying to pick out a message from whatever JS threw and CDP reported,
      # we include everything to make debugging easier
      raise selenium.common.exceptions.JavascriptException(
        f'Runtime.evaluate threw: {json.dumps(response["exceptionDetails"])}'
      )

    return response['result'].get('value')

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
          self.requested_url,
        )
    except urllib3.exceptions.HTTPError:
      logger.exception('urllib3 HTTPError, browser probably hung %s', self.requested_url)
    self.driver = self.spawn_single_webdriver(window_size=self.viewport_size)
    self.requested_url = ''

  def close(self) -> None:
    """Close the browser."""
    logger.info('Quitting browser')
    try:
      self.driver.quit()
    except (selenium.common.exceptions.WebDriverException, urllib3.exceptions.HTTPError):
      logger.exception('Failed to quit browser')
    self._remove_chrome_tmp_dir()
    self.requested_url = ''

  def _remove_chrome_tmp_dir(self) -> None:
    if self._chrome_tmp_dir is None:
      return
    shutil.rmtree(
      self._chrome_tmp_dir,
      onexc=lambda func, path, exc: logger.warning('Failed to remove %s (%s): %s', path, func.__name__, exc),
    )
    self._chrome_tmp_dir = None

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

  def spawn_single_webdriver(self, window_size: dict[Any, Any]) -> WebDriverType:
    """Spawn a single instance of a browser.

    Args:
        window_size (dict[Any, Any]): window dimensions of browser.

    Returns:
        WebDriverType: a webdriver object.
    """
    # Get appropriate null path for OS
    null_path = '/dev/null'
    if platform.system() == 'Windows':
      null_path = 'NUL'

    chrome_options = webdriver.ChromeOptions()
    if self.config.headless:
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

    # Timeouts are in milliseconds
    chrome_options.timeouts = {
      'script': self.config.script_timeout * 1000,
      'pageLoad': self.config.page_load_timeout * 1000,
    }

    # Disable downloads
    chrome_options.add_experimental_option(
      'prefs',
      {
        'download.default_directory': null_path,
        'download.prompt_for_download': False,
      },
    )

    # set up a dedicated temp directory for this instance of chrome,
    # so we can ensure it is removed later in case we have a crash
    self._remove_chrome_tmp_dir()
    self._chrome_tmp_dir = tempfile.mkdtemp(prefix='cwac-chrome-')

    chrome_service = Service(
      self.config.chrome_driver_location,
      env={**os.environ, 'TMPDIR': self._chrome_tmp_dir},
      service_args=[
        '--verbose',
        '--log-path=./results/' + self.config.audit_name + '/chromedriver.log',
      ],
    )

    # Set binary path
    chrome_options.binary_location = self.config.chrome_binary_location

    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    x_pos = 100 + 400 * (self.thread_id % 4)
    y_pos = 0 if self.thread_id < 4 else 400
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(**window_size)

    return driver
