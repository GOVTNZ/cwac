"""Tests the behaviour of the Browser class."""

from typing import Any, cast
from unittest.mock import Mock

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture
from selenium.common.exceptions import JavascriptException

from config import Config
from src.browser import Browser


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
  """Make the browser's driver return the given response for any CDP command."""
  execute_cdp_cmd = cast(Mock, browser.driver.execute_cdp_cmd)
  execute_cdp_cmd.return_value = response
  return execute_cdp_cmd


class TestEvaluate:
  """Tests Browser.evaluate."""

  def test_evaluates_the_snippet_with_runtime_evaluate(self, browser: Browser) -> None:
    """Sends the snippet to Runtime.evaluate, awaiting promises and returning by value."""
    execute_cdp_cmd = mock_cdp_response(browser, {'result': {'type': 'number', 'value': 2}})

    browser.evaluate('1 + 1')

    execute_cdp_cmd.assert_called_once_with(
      'Runtime.evaluate',
      {
        'expression': '1 + 1',
        'returnByValue': True,
        'awaitPromise': True,
        'timeout': browser.config.script_timeout * 1000,
      },
    )

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

  def test_raises_when_the_snippet_throws_an_error(self, browser: Browser) -> None:
    """Raises a JavascriptException using the error's description and a 1-based position."""
    mock_cdp_response(
      browser,
      {
        'result': {
          'type': 'object',
          'subtype': 'error',
          'className': 'Error',
          'description': 'Error: boom\n    at <anonymous>:3:16\n    at <anonymous>:3:37',
          'objectId': '1.1.2',
        },
        'exceptionDetails': {
          'exceptionId': 1,
          'text': 'Uncaught',
          'lineNumber': 2,
          'columnNumber': 9,
          'scriptId': '33',
          'exception': {
            'type': 'object',
            'subtype': 'error',
            'className': 'Error',
            'description': 'Error: boom\n    at <anonymous>:3:16\n    at <anonymous>:3:37',
            'objectId': '1.1.3',
          },
        },
      },
    )

    with pytest.raises(JavascriptException) as exc_info:
      browser.evaluate('...')

    assert exc_info.value.msg == 'Error: boom\n    at <anonymous>:3:16\n    at <anonymous>:3:37 (line 3, column 10)'

  def test_raises_when_the_snippet_has_a_syntax_error(self, browser: Browser) -> None:
    """Raises a JavascriptException using the syntax error's description and a 1-based position."""
    mock_cdp_response(
      browser,
      {
        'result': {
          'type': 'object',
          'subtype': 'error',
          'className': 'SyntaxError',
          'description': 'SyntaxError: Unexpected end of input',
          'objectId': '1.1.4',
        },
        'exceptionDetails': {
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
      },
    )

    with pytest.raises(JavascriptException) as exc_info:
      browser.evaluate('...')

    assert exc_info.value.msg == 'SyntaxError: Unexpected end of input (line 1, column 4)'

  def test_raises_with_the_thrown_value_when_it_is_not_an_error(self, browser: Browser) -> None:
    """Uses the thrown value when there is no description, such as when a string is thrown."""
    mock_cdp_response(
      browser,
      {
        'result': {'type': 'string', 'value': 'oops'},
        'exceptionDetails': {
          'exceptionId': 1,
          'text': 'Uncaught',
          'lineNumber': 0,
          'columnNumber': 0,
          'scriptId': '34',
          'exception': {'type': 'string', 'value': 'oops'},
        },
      },
    )

    with pytest.raises(JavascriptException) as exc_info:
      browser.evaluate('...')

    assert exc_info.value.msg == 'oops (line 1, column 1)'

  def test_raises_with_the_exception_text_when_there_is_no_exception(self, browser: Browser) -> None:
    """Falls back to the exception text when no exception object is given, which CDP marks as optional."""
    mock_cdp_response(
      browser,
      {
        'result': {'type': 'undefined'},
        'exceptionDetails': {
          'exceptionId': 1,
          'text': 'Uncaught',
          'lineNumber': 0,
          'columnNumber': 0,
        },
      },
    )

    with pytest.raises(JavascriptException) as exc_info:
      browser.evaluate('...')

    assert exc_info.value.msg == 'Uncaught (line 1, column 1)'
