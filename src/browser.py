"""A wrapper class for the webdriver.

Contains useful functions for managing browsers.
"""

import logging
import platform
import time
import traceback
from typing import Any, cast

import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.service import Service as FirefoxService

from config import Config

WebDriverType = selenium.webdriver.firefox.webdriver.WebDriver | selenium.webdriver.chrome.webdriver.WebDriver

logger = logging.getLogger('cwac')


class Browser:
  """A wrapper class for selenium webdriver."""

  def __init__(self, config: Config, thread_id: int) -> None:
    """Init variables and spawns webdriver."""
    self.config = config
    self.thread_id = thread_id
    self.num_retries = 2
    self.viewport_size = {'width': 320, 'height': 450}
    self.driver: WebDriverType = self.spawn_single_webdriver(window_size=list(self.config.viewport_sizes.values())[0])
    self.last_url_req = ''

  def get_if_necessary(self, url: str) -> bool:
    """Load a URL in the webdriver if it is not already loaded.

    Args:
        url (str): url to load

    Returns:
        bool: True if page loaded, False if something went wrong
    """
    if self.last_url_req == url:
      return True

    return self.get(url)

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

    for attempts in range(5):
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
      self.driver.close()
    except selenium.common.exceptions.InvalidSessionIdException:
      logger.exception('InvalidSessionIdException, browser probably crashed')
    except selenium.common.exceptions.WebDriverException as error:
      # check if 'message' is "disconnected: not connected to DevTools"
      if 'disconnected' in str(error):
        logger.exception(
          'WebDriverException, browser probably crashed %s',
          self.last_url_req,
        )
    self.driver = self.spawn_single_webdriver(window_size=self.viewport_size)
    self.last_url_req = ''

  def restart(self) -> None:
    """Restart the webdriver and restore its dimensions."""
    try:
      window_pos = self.driver.get_window_position()
      window_size = self.driver.get_window_size()
      self.driver.close()
      new_driver: WebDriverType = self.spawn_single_webdriver(window_size=window_size)
      new_driver.set_window_position(**window_pos)
      new_driver.set_window_size(**window_size)
      self.driver = new_driver
      self.last_url_req = ''
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception('Unhandled exception')
      self.safe_restart()

  def get_doctype(self) -> str:
    """Get the doctype of the currently loaded page in the webdriver.

    Returns:
        str: the doctype of the loaded page
    """
    doctype_string = ''
    doctype_js = """return "<!DOCTYPE " + document.doctype.name \
            + (document.doctype.publicId ? ' PUBLIC "' \
            + document.doctype.publicId + '"' : '') \
            + (!document.doctype.publicId && \
             document.doctype.systemId ? ' SYSTEM' : '') \
            + (document.doctype.systemId ? ' "' +\
            document.doctype.systemId + '"' : '') + '>';"""
    try:
      doctype_string = self.driver.execute_script(doctype_js)
    except Exception:  # pylint: disable=broad-exception-caught
      logger.error(
        ("An error occurred while trying to get this website's doctype. Defaulting to html5 for %s"),
        self.driver.current_url,
      )
      logger.error(traceback.format_exc())
      doctype_string = '<!DOCTYPE html>'
    return doctype_string

  def get_base_uri(self) -> str:
    """Returns document.baseURI of current page.

    Returns:
        str: base URI of current page.
    """
    try:
      return cast(str, self.driver.execute_script('return document.baseURI'))
    except Exception as exc:
      logger.exception('TimeoutException when getting base URI')
      self.safe_restart()
      raise exc

  def get_page_source(self) -> str:
    """Return the browser's page source.

    Return:
        str: page source
    """
    try:
      return self.get_doctype() + '\n' + self.driver.page_source
    except selenium.common.exceptions.TimeoutException as exc:
      logger.exception('TimeoutException when getting page source')
      self.safe_restart()
      raise exc

  def close(self) -> None:
    """Close the browser."""
    logger.info('Quitting browser')
    self.driver.close()
    self.last_url_req = ''

  def refresh(self) -> None:
    """Refresh the browser."""
    logger.info('Refreshing browser')
    try:
      self.driver.refresh()
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception('Error refreshing browser')

  def set_window_size(self, width: int, height: int) -> None:
    """Set browser size.

    Args:
        width (int): width of browser.
        height (int): height of browser.
    """
    try:
      self.viewport_size = {'width': width, 'height': height}
      self.driver.set_window_size(width, height)
    except selenium.common.exceptions.TimeoutException:
      logger.exception('TimeoutException')
      self.safe_restart()
    except selenium.common.exceptions.WebDriverException:
      logger.exception('WebDriverException')
      self.safe_restart()

  def get_window_size(self) -> dict[str, int]:
    """Get browser size.

    Returns:
        dict[str, int]: width and height of browser.
    """
    try:
      return self.driver.get_window_size()
    except selenium.common.exceptions.TimeoutException:
      logger.exception('TimeoutException')
      self.safe_restart()
      return self.driver.get_window_size()
    except selenium.common.exceptions.WebDriverException:
      logger.exception('WebDriverException')
      self.safe_restart()
      return self.driver.get_window_size()
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception('Unhandled exception')
      self.safe_restart()
      return self.viewport_size

  def spawn_single_webdriver(self, window_size: dict[Any, Any], headless_override: bool = False) -> WebDriverType:
    """Spawn a single instance of a browser.

    Args:
        window_size (dict[Any, Any]): window dimensions of browser.
        headless_override (bool, optional): override headless setting.

    Returns:
        WebDriverType: a webdriver object.
    """
    driver: WebDriverType

    # Get appropriate null path for OS
    null_path = '/dev/null'
    if platform.system() == 'Windows':
      null_path = 'NUL'

    # Sets up a Chrome instance
    if self.config.browser == 'chrome':
      chrome_options = webdriver.ChromeOptions()
      if self.config.headless or headless_override:
        chrome_options.add_argument('--headless')
      chrome_options.add_argument(f'--window-size={window_size["width"]},{window_size["height"]}')
      chrome_options.add_argument('--log-level=3')
      chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
      chrome_options.add_argument('--disable-notifications')
      chrome_options.add_argument('--disable-popup-blocking')
      chrome_options.add_experimental_option(
        'prefs',
        {
          'profile.default_content_setting_values.notifications': 1,
          'profile.default_content_setting_values.javascript': 2,
        },
      )

      # Set fake user agent
      chrome_options.add_argument(f'user-agent={self.config.user_agent}')

      chrome_options.unhandled_prompt_behavior = 'dismiss'

      # Disable downloads

      prefs = {
        'profile.default_content_settings_values\
                    .automatic_downloads': 2,
        'download.default_directory': null_path,
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
      }

      chrome_options.add_experimental_option('prefs', prefs)

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

    # Sets up a Firefox instance
    if self.config.browser == 'firefox':
      firefox_options = selenium.webdriver.firefox.options.Options()
      firefox_options.headless = self.config.headless  # type: ignore
      if headless_override:
        firefox_options.headless = True  # type: ignore
      firefox_options.add_argument(f'--width={window_size["width"]}')
      firefox_options.add_argument(f'--height={window_size["height"]}')

      # Set fake user agent
      firefox_options.set_preference('general.useragent.override', self.config.user_agent)

      # Disable file downloads
      firefox_options.set_preference('browser.download.dir', null_path)
      firefox_options.set_preference('browser.download.folderList', 2)

      firefox_options.unhandled_prompt_behavior = 'dismiss'
      firefox_service = FirefoxService(
        log_path='./results/' + self.config.audit_name + '/geckodriver.log',
      )
      driver = webdriver.Firefox(service=firefox_service, options=firefox_options)

    driver.set_script_timeout(self.config.script_timeout)
    driver.set_page_load_timeout(self.config.page_load_timeout)

    x_pos = 100 + 400 * (self.thread_id % 4)
    y_pos = 0 if self.thread_id < 4 else 400
    driver.set_window_position(x_pos, y_pos)
    driver.set_window_size(**window_size)

    return driver
