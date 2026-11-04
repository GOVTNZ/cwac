"""Tests the behaviour of the Browser class."""

import itertools
import json
from typing import Any, cast
from unittest.mock import Mock, call

import pytest
import urllib3
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture
from selenium.common.exceptions import (
  InvalidSessionIdException,
  JavascriptException,
  TimeoutException,
  WebDriverException,
)

from config import Config
from src.browser import Browser
from tests.helpers.utils import normalized_url


@pytest.fixture(name='browser')
def fixture_browser(fs: FakeFilesystem, mocker: MockerFixture) -> Browser:
  """Create a Browser with a mocked webdriver."""
  fs.add_real_file('config/config_default.json')
  fs.add_real_file('package.json')
  fs.create_file('base_urls/visit/urls.csv', contents='url\nhttps://example.com')
  fs.makedirs('base_urls/nohead')
  fs.makedirs('results')

  mocker.patch('src.browser.webdriver.Chrome')

  return Browser(Config('config_default.json'), 1)


def mock_cdp_response(browser: Browser, response: dict[str, Any]) -> Mock:
  """Make the browser's driver return the given response for Runtime.evaluate, with an isolated world to run it in."""
  context_ids = itertools.count(1)

  def respond(cmd: str, _: dict[str, Any]) -> dict[str, Any]:
    # https://chromedevtools.github.io/devtools-protocol/#/stable/Page.getFrameTree
    if cmd == 'Page.getFrameTree':
      return {'frameTree': {'frame': {'id': 'MAIN_FRAME', 'url': 'https://example.com/'}}}

    # https://chromedevtools.github.io/devtools-protocol/#/stable/Page.createIsolatedWorld
    if cmd == 'Page.createIsolatedWorld':
      return {'executionContextId': next(context_ids)}

    assert cmd == 'Runtime.evaluate'
    return response

  execute_cdp_cmd = cast(Mock, browser.driver.execute_cdp_cmd)
  execute_cdp_cmd.side_effect = respond
  return execute_cdp_cmd


@pytest.fixture(name='sleep', autouse=True)
def fixture_sleep(mocker: MockerFixture) -> Mock:
  """Skip the delay after loading a page."""
  return mocker.patch('src.browser.time.sleep')


def evaluated_context_ids(execute_cdp_cmd: Mock) -> list[int]:
  """Get the context id that each Runtime.evaluate call was run in."""
  return [c.args[1]['contextId'] for c in execute_cdp_cmd.call_args_list if c.args[0] == 'Runtime.evaluate']


class TestGet:
  """Tests Browser.get."""

  def test_loads_the_url(self, browser: Browser, mocker: MockerFixture) -> None:
    """Loads the url once without restarting, and records it as the requested url."""
    safe_restart = mocker.spy(browser, 'safe_restart')

    assert browser.get(normalized_url('https://example.com/')) is True

    cast(Mock, browser.driver.get).assert_called_once_with('https://example.com/')
    safe_restart.assert_not_called()
    assert browser.requested_url == 'https://example.com/'

  @pytest.mark.parametrize(
    'error',
    [
      pytest.param(TimeoutException(), id='TimeoutException'),
      pytest.param(WebDriverException(), id='WebDriverException'),
      pytest.param(urllib3.exceptions.ProtocolError(), id='urllib3 HTTPError'),
    ],
  )
  def test_restarts_and_retries_when_loading_fails(
    self, browser: Browser, mocker: MockerFixture, error: Exception
  ) -> None:
    """Restarts the browser after every failed attempt, including the last, then gives up."""
    safe_restart = mocker.spy(browser, 'safe_restart')
    cast(Mock, browser.driver.get).side_effect = error

    assert browser.get(normalized_url('https://example.com/')) is False

    assert cast(Mock, browser.driver.get).call_count == browser.num_retries
    assert safe_restart.call_count == browser.num_retries
    assert browser.requested_url == ''

  def test_loads_the_url_after_a_failed_attempt(self, browser: Browser, mocker: MockerFixture) -> None:
    """Loads the url if a retry after restarting succeeds."""
    safe_restart = mocker.spy(browser, 'safe_restart')
    cast(Mock, browser.driver.get).side_effect = [TimeoutException(), None]

    assert browser.get(normalized_url('https://example.com/')) is True

    safe_restart.assert_called_once()
    assert browser.requested_url == 'https://example.com/'

  def test_does_not_handle_unexpected_exceptions(self, browser: Browser, mocker: MockerFixture) -> None:
    """Lets exceptions that aren't from the browser escape, as they're likely bugs."""
    safe_restart = mocker.spy(browser, 'safe_restart')
    cast(Mock, browser.driver.get).side_effect = ValueError('oh no')

    with pytest.raises(ValueError, match='oh no'):
      browser.get(normalized_url('https://example.com/'))

    safe_restart.assert_not_called()


class TestSafeRestart:
  """Tests Browser.safe_restart."""

  def test_quits_and_spawns_a_new_browser(self, browser: Browser, mocker: MockerFixture) -> None:
    """Quits the current browser and spawns a new one at the current viewport size."""
    old_driver = browser.driver
    spawn = mocker.spy(browser, 'spawn_single_webdriver')

    browser.safe_restart()

    cast(Mock, old_driver.quit).assert_called_once()
    spawn.assert_called_once_with(window_size=browser.viewport_size)

  @pytest.mark.parametrize(
    ('error', 'expected_log'),
    [
      pytest.param(
        InvalidSessionIdException('invalid session id', stacktrace=['#0 0x123']),
        # selenium appends a link to its docs for some exceptions
        'InvalidSessionIdException when quitting browser to restart: invalid session id; '
        'For documentation on this error, please visit: '
        'https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#invalidsessionidexception',
        id='InvalidSessionIdException',
      ),
      pytest.param(
        WebDriverException('disconnected: not connected to DevTools', stacktrace=['#0 0x123']),
        'WebDriverException when quitting browser to restart: disconnected: not connected to DevTools',
        id='WebDriverException (disconnected)',
      ),
      pytest.param(
        WebDriverException('chrome not reachable', stacktrace=['#0 0x123']),
        'WebDriverException when quitting browser to restart: chrome not reachable',
        id='WebDriverException (other)',
      ),
      pytest.param(
        urllib3.exceptions.ProtocolError('Connection aborted.'),
        'ProtocolError when quitting browser to restart: Connection aborted.',
        id='urllib3 HTTPError',
      ),
    ],
  )
  def test_logs_and_spawns_a_new_browser_when_quitting_fails(
    self, browser: Browser, mocker: MockerFixture, caplog: pytest.LogCaptureFixture, error: Exception, expected_log: str
  ) -> None:
    """Logs a warning without the stacktrace when quitting fails, and spawns a new browser regardless."""
    cast(Mock, browser.driver.quit).side_effect = error
    spawn = mocker.spy(browser, 'spawn_single_webdriver')

    browser.safe_restart()

    assert [(r.levelname, r.getMessage(), r.exc_info) for r in caplog.records] == [('WARNING', expected_log, None)]
    spawn.assert_called_once()

  def test_does_not_handle_unexpected_exceptions(self, browser: Browser) -> None:
    """Lets exceptions that aren't from the browser escape, as they're likely bugs."""
    cast(Mock, browser.driver.quit).side_effect = ValueError('oh no')

    with pytest.raises(ValueError, match='oh no'):
      browser.safe_restart()


class TestSetWindowSize:
  """Tests Browser.set_window_size."""

  def test_sets_the_window_size(self, browser: Browser, mocker: MockerFixture) -> None:
    """Resizes the browser without restarting, and remembers the size for future restarts."""
    safe_restart = mocker.spy(browser, 'safe_restart')

    browser.set_window_size(1280, 800)

    cast(Mock, browser.driver.set_window_size).assert_called_with(1280, 800)
    safe_restart.assert_not_called()
    assert browser.viewport_size == {'width': 1280, 'height': 800}

  @pytest.mark.parametrize(
    'error',
    [
      pytest.param(TimeoutException(), id='TimeoutException'),
      pytest.param(WebDriverException(), id='WebDriverException'),
      pytest.param(urllib3.exceptions.ProtocolError(), id='urllib3 HTTPError'),
    ],
  )
  def test_restarts_at_the_new_size_when_resizing_fails(
    self, browser: Browser, mocker: MockerFixture, caplog: pytest.LogCaptureFixture, error: Exception
  ) -> None:
    """Logs a warning without the stacktrace, and restarts the browser with the new size."""

    def fail_unless_spawning(*args: int, **_: int) -> None:
      # spawning resizes with keyword arguments, which should still succeed
      if args:
        raise error

    cast(Mock, browser.driver.set_window_size).side_effect = fail_unless_spawning
    spawn = mocker.spy(browser, 'spawn_single_webdriver')

    browser.set_window_size(1280, 800)

    assert [(r.levelname, r.getMessage(), r.exc_info) for r in caplog.records] == [
      ('WARNING', f'{type(error).__name__} when setting window size to 1280x800', None)
    ]
    spawn.assert_called_once_with(window_size={'width': 1280, 'height': 800})

  def test_does_not_handle_unexpected_exceptions(self, browser: Browser, mocker: MockerFixture) -> None:
    """Lets exceptions that aren't from the browser escape, as they're likely bugs."""
    safe_restart = mocker.spy(browser, 'safe_restart')
    cast(Mock, browser.driver.set_window_size).side_effect = ValueError('oh no')

    with pytest.raises(ValueError, match='oh no'):
      browser.set_window_size(1280, 800)

    safe_restart.assert_not_called()


class TestEvaluate:
  """Tests Browser.evaluate."""

  def test_evaluates_the_snippet_with_runtime_evaluate(self, browser: Browser) -> None:
    """Sends the snippet to Runtime.evaluate in an isolated world for the main frame, wrapped in a block, awaiting promises and returning by value."""
    execute_cdp_cmd = mock_cdp_response(browser, {'result': {'type': 'number', 'value': 2}})

    browser.evaluate('1 + 1')

    assert execute_cdp_cmd.call_args_list == [
      call('Page.getFrameTree', {}),
      call('Page.createIsolatedWorld', {'frameId': 'MAIN_FRAME', 'worldName': 'CWAC'}),
      call(
        'Runtime.evaluate',
        {
          'contextId': 1,
          'expression': '{\n1 + 1\n}',
          'returnByValue': True,
          'awaitPromise': True,
          'timeout': browser.config.script_timeout * 1000,
        },
      ),
    ]

  def test_reuses_the_isolated_world_across_evaluations(self, browser: Browser) -> None:
    """Creates the isolated world once, and evaluates every snippet in it."""
    execute_cdp_cmd = mock_cdp_response(browser, {'result': {'type': 'undefined'}})

    browser.evaluate('1')
    browser.evaluate('2')
    browser.evaluate('3')

    assert evaluated_context_ids(execute_cdp_cmd) == [1, 1, 1]

  def test_creates_a_new_isolated_world_after_loading_a_page(self, browser: Browser) -> None:
    """Creates a new isolated world on the first evaluation after a page is loaded, and reuses it for that page."""
    execute_cdp_cmd = mock_cdp_response(browser, {'result': {'type': 'undefined'}})

    browser.evaluate('1')
    browser.evaluate('2')
    assert browser.get(normalized_url('https://example.com/news')) is True
    assert browser.get(normalized_url('https://example.com/contact')) is True
    browser.evaluate('3')
    browser.evaluate('4')
    assert browser.get(normalized_url('https://example.com/blog')) is True
    browser.evaluate('5')

    assert evaluated_context_ids(execute_cdp_cmd) == [1, 1, 2, 2, 3]

  def test_creates_a_new_isolated_world_after_failing_to_load_a_page(self, browser: Browser) -> None:
    """Creates a new isolated world after a failed page load, since the browser may have still navigated away."""
    execute_cdp_cmd = mock_cdp_response(browser, {'result': {'type': 'undefined'}})
    cast(Mock, browser.driver.get).side_effect = TimeoutException()

    browser.evaluate('1')
    assert browser.get(normalized_url('https://example.com/')) is False
    browser.evaluate('2')

    assert evaluated_context_ids(execute_cdp_cmd) == [1, 2]

  def test_creates_a_new_isolated_world_after_the_browser_restarts(self, browser: Browser) -> None:
    """Creates a new isolated world after the browser is restarted, since the old one no longer exists."""
    execute_cdp_cmd = mock_cdp_response(browser, {'result': {'type': 'undefined'}})

    browser.evaluate('1')
    browser.safe_restart()
    browser.evaluate('2')

    assert evaluated_context_ids(execute_cdp_cmd) == [1, 2]

  @pytest.mark.parametrize(
    ('result', 'expected'),
    [
      ({'type': 'number', 'value': 2, 'description': '2'}, 2),
      ({'type': 'string', 'value': 'hello'}, 'hello'),
      ({'type': 'boolean', 'value': False}, False),
      ({'type': 'object', 'value': [1, 'a']}, [1, 'a']),
      ({'type': 'object', 'value': {'a': 1}}, {'a': 1}),
      ({'type': 'object', 'subtype': 'null', 'value': None}, None),
      ({'type': 'function', 'value': {}}, {}),
    ],
  )
  def test_returns_the_value_of_the_result(self, browser: Browser, result: dict[str, Any], expected: Any) -> None:
    """Returns the JSON value of the result."""
    mock_cdp_response(browser, {'result': result})

    assert browser.evaluate('...') == expected

  @pytest.mark.parametrize(
    'result',
    [
      {'type': 'undefined'},
      {'type': 'number', 'unserializableValue': 'NaN', 'description': 'NaN'},
    ],
  )
  def test_returns_none_when_the_result_has_no_value(self, browser: Browser, result: dict[str, Any]) -> None:
    """Returns None for results that have no JSON value, such as undefined and NaN."""
    mock_cdp_response(browser, {'result': result})

    assert browser.evaluate('...') is None

  @pytest.mark.parametrize(
    'exception_details',
    [
      pytest.param(
        {
          'exceptionId': 1,
          'text': 'Uncaught',
          'lineNumber': 2,
          'columnNumber': 9,
          'scriptId': '33',
          'stackTrace': {
            'callFrames': [
              {'columnNumber': 15, 'functionName': '', 'lineNumber': 2, 'scriptId': '33', 'url': ''},
              {'columnNumber': 36, 'functionName': '', 'lineNumber': 2, 'scriptId': '33', 'url': ''},
            ]
          },
          'exception': {
            'type': 'object',
            'subtype': 'error',
            'className': 'Error',
            'description': 'Error: boom\n    at <anonymous>:3:16\n    at <anonymous>:3:37',
            'objectId': '1.1.3',
          },
        },
        id='error',
      ),
      pytest.param(
        {
          'exceptionId': 1,
          'text': 'Uncaught (in promise) Error: nope',
          'lineNumber': 1,
          'columnNumber': 16,
          'scriptId': '32',
          'stackTrace': {
            'callFrames': [{'columnNumber': 15, 'functionName': '', 'lineNumber': 0, 'scriptId': '32', 'url': ''}]
          },
          'exception': {
            'type': 'object',
            'subtype': 'error',
            'className': 'Error',
            'description': 'Error: nope\n    at <anonymous>:1:16',
            'objectId': '1.1.1',
          },
        },
        id='rejected promise',
      ),
      pytest.param(
        {
          'exceptionId': 1,
          'text': 'Uncaught',
          'lineNumber': 0,
          'columnNumber': 3,
          'scriptId': '35',
          'exception': {
            'type': 'object',
            'subtype': 'error',
            'className': 'SyntaxError',
            'description': 'SyntaxError: Unexpected end of input',
            'objectId': '1.1.5',
          },
        },
        id='syntax error',
      ),
      pytest.param(
        {
          'exceptionId': 1,
          'text': 'Uncaught',
          'lineNumber': 0,
          'columnNumber': 0,
          'scriptId': '34',
          'stackTrace': {
            'callFrames': [{'columnNumber': 0, 'functionName': '', 'lineNumber': 0, 'scriptId': '34', 'url': ''}]
          },
          'exception': {'type': 'string', 'value': 'oops'},
        },
        id='thrown string',
      ),
      pytest.param(
        {
          'exceptionId': 1,
          'text': 'Uncaught',
          'lineNumber': 0,
          'columnNumber': 0,
        },
        id='no exception',
      ),
    ],
  )
  def test_raises_with_the_exception_details_when_the_snippet_throws(
    self, browser: Browser, exception_details: dict[str, Any]
  ) -> None:
    """Raises a JavascriptException including all of the exception details, whatever was thrown."""
    mock_cdp_response(browser, {'result': {'type': 'object', 'value': {}}, 'exceptionDetails': exception_details})

    with pytest.raises(JavascriptException) as exc_info:
      browser.evaluate('...')

    assert exc_info.value.msg == f'Runtime.evaluate threw: {json.dumps(exception_details)}'
