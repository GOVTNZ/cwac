"""Tests the behaviour of the Browser class."""

import json
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
    """Sends the snippet to Runtime.evaluate wrapped in a block, awaiting promises and returning by value."""
    execute_cdp_cmd = mock_cdp_response(browser, {'result': {'type': 'number', 'value': 2}})

    browser.evaluate('1 + 1')

    execute_cdp_cmd.assert_called_once_with(
      'Runtime.evaluate',
      {
        'expression': '{\n1 + 1\n}',
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
