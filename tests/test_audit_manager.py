"""Tests the behaviour of the AuditManager class."""

import json
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import Mock

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture
from selenium.common.exceptions import TimeoutException

from config import Config, SiteData
from src.audit_manager import AuditManager
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser


def setup_filesystem(fs: FakeFilesystem) -> None:
  """Set up the fake filesystem with the config, package.json, and base urls needed by Config."""
  fs.add_real_file('config/config_default.json', read_only=False)
  fs.add_real_file('package.json')

  fs.create_file(
    'base_urls/visit/urls.csv',
    contents='url\nhttps://example.com',
  )
  fs.makedirs('base_urls/nohead')
  fs.makedirs('results')


def modify_default_config(modifications: dict[str, Any]) -> None:
  """Merge the given modifications into the default config on disk."""
  with open('config/config_default.json', 'r+', encoding='utf-8') as f:
    c = {**json.load(f), **modifications}
    f.seek(0)
    json.dump(c, f)
    f.truncate()


class FakeAudit(DefaultAudit):
  """An audit that reports the conditions it was run under via on_run, and uses its return value as the audit result."""

  on_run: Callable[..., list[dict[str, str]] | bool] = staticmethod(lambda **_: [{}])

  audit_name = ''

  def run(self) -> list[dict[str, str]] | bool:
    """Report the current url, site data, ids, and browser viewport to on_run, and return what it returns."""
    return self.on_run(
      audit_name=self.audit_name,
      url=self.url,
      site_data=self.site_data,
      audit_id=self.audit_id,
      page_id=self.page_id,
      viewport=dict(self.browser.viewport_size),
    )


def create_event_tracker(mocker: MockerFixture, manager: AuditManager, on_run: Mock) -> Mock:
  """Create a mock which captures various call "events" that can be asserted on later."""
  events = Mock()

  events.attach_mock(mocker.spy(manager.browser, 'get'), 'get')
  events.attach_mock(mocker.spy(manager.browser, 'safe_restart'), 'restart')
  events.attach_mock(on_run, 'run')

  return events


def event_log(events: Mock) -> list[tuple[Any, ...]]:
  """Create an "event log" based on the calls made to the events mock."""
  return [('run', kwargs['audit_name']) if name == 'run' else (name, *args) for name, args, kwargs in events.mock_calls]


def setup_manager_and_mocks(
  mocker: MockerFixture,
  audit_plugins: dict[str, Any],
  config_changes: dict[str, Any] | None = None,
) -> tuple[AuditManager, Mock, Mock]:
  """Create an AuditManager and related mocks for testing, with on_run returning a successful result by default."""
  on_run = mocker.patch.object(FakeAudit, 'on_run', return_value=[{}])

  modify_default_config(
    {
      'viewport_sizes': {'small': {'width': 320, 'height': 450}},
      'audit_plugins': audit_plugins,
      # NOTE: source audit plugins from here once we can use extra_items=Any (Python 3.15+)
      **(config_changes or {}),
      'delay_after_page_load': 0,
    }
  )

  config = Config('config_default.json')

  mocker.patch('src.browser.webdriver.Chrome')
  browser = Browser(config, 1)

  audits = {
    name: cast(
      type[DefaultAudit],
      type('FakeAudit', (FakeAudit,), {'audit_name': name}),
    )
    for name in audit_plugins
  }

  manager = AuditManager(config, browser, audits)
  mocker.patch.object(manager, '_check_for_closed_details_elements')
  mocker.patch.object(manager, 'test_for_anti_bot', return_value='Pass')

  events = create_event_tracker(mocker, manager, on_run)

  return manager, events, on_run


def test_run_audits_single_page_single_viewport_single_audit(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs the audit against a single page at a single viewport."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}})

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  assert event_log(events) == [
    ('get', 'https://bnl.com/news'),
    ('run', 'first'),
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name='first',
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
  ]


def test_run_audits_multiple_sites_pages_viewports_and_audits(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs the audit against multiple pages across multiple sites at multiple viewports."""
  setup_filesystem(fs)

  viewport_sizes = {
    'small': {'width': 320, 'height': 450},
    'medium': {'width': 1280, 'height': 800},
  }

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {'first': {}, 'second': {}},
    {'viewport_sizes': viewport_sizes},
  )

  site_datas: dict[str, SiteData] = {
    'https://bnl.com/': {
      'url': 'https://bnl.com/',
      'supports_head': True,
      'columns': {'url': 'https://bnl.com/'},
    },
    'https://acme.com/': {
      'url': 'https://acme.com/',
      'supports_head': True,
      'columns': {'url': 'https://acme.com/'},
    },
    'https://wayne.com/': {
      'url': 'https://wayne.com/',
      'supports_head': True,
      'columns': {'url': 'https://wayne.com/'},
    },
  }

  sites = {
    'https://bnl.com/': [
      'https://bnl.com/',
      'https://bnl.com/news',
    ],
    'https://acme.com/': [
      'https://acme.com/',
      'https://acme.com/contact',
      'https://acme.com/legal',
    ],
    'https://wayne.com/': [
      'https://wayne.com/',
      'https://wayne.com/security',
      'https://wayne.com/legal',
    ],
  }

  for base_url, urls in sites.items():
    for url in urls:
      assert manager.run_audits(url=url, site_data=site_datas[base_url]) is True

  # expect the page to be fetched for each audit at each viewport
  assert event_log(events) == [
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('get', 'https://bnl.com/news'),
    ('run', 'first'),
    ('get', 'https://bnl.com/news'),
    ('run', 'second'),
    ('get', 'https://bnl.com/news'),
    ('run', 'first'),
    ('get', 'https://bnl.com/news'),
    ('run', 'second'),
    ('get', 'https://acme.com/'),
    ('run', 'first'),
    ('get', 'https://acme.com/'),
    ('run', 'second'),
    ('get', 'https://acme.com/'),
    ('run', 'first'),
    ('get', 'https://acme.com/'),
    ('run', 'second'),
    ('get', 'https://acme.com/contact'),
    ('run', 'first'),
    ('get', 'https://acme.com/contact'),
    ('run', 'second'),
    ('get', 'https://acme.com/contact'),
    ('run', 'first'),
    ('get', 'https://acme.com/contact'),
    ('run', 'second'),
    ('get', 'https://acme.com/legal'),
    ('run', 'first'),
    ('get', 'https://acme.com/legal'),
    ('run', 'second'),
    ('get', 'https://acme.com/legal'),
    ('run', 'first'),
    ('get', 'https://acme.com/legal'),
    ('run', 'second'),
    ('get', 'https://wayne.com/'),
    ('run', 'first'),
    ('get', 'https://wayne.com/'),
    ('run', 'second'),
    ('get', 'https://wayne.com/'),
    ('run', 'first'),
    ('get', 'https://wayne.com/'),
    ('run', 'second'),
    ('get', 'https://wayne.com/security'),
    ('run', 'first'),
    ('get', 'https://wayne.com/security'),
    ('run', 'second'),
    ('get', 'https://wayne.com/security'),
    ('run', 'first'),
    ('get', 'https://wayne.com/security'),
    ('run', 'second'),
    ('get', 'https://wayne.com/legal'),
    ('run', 'first'),
    ('get', 'https://wayne.com/legal'),
    ('run', 'second'),
    ('get', 'https://wayne.com/legal'),
    ('run', 'first'),
    ('get', 'https://wayne.com/legal'),
    ('run', 'second'),
  ]

  # expect each audit to be run once at each viewport for each page
  assert on_run.call_args_list == [
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://bnl.com/',
        site_data=site_datas['https://bnl.com/'],
        audit_id=f'1_{label}',
        page_id='1',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://bnl.com/news',
        site_data=site_datas['https://bnl.com/'],
        audit_id=f'2_{label}',
        page_id='2',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://acme.com/',
        site_data=site_datas['https://acme.com/'],
        audit_id=f'3_{label}',
        page_id='3',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://acme.com/contact',
        site_data=site_datas['https://acme.com/'],
        audit_id=f'4_{label}',
        page_id='4',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://acme.com/legal',
        site_data=site_datas['https://acme.com/'],
        audit_id=f'5_{label}',
        page_id='5',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://wayne.com/',
        site_data=site_datas['https://wayne.com/'],
        audit_id=f'6_{label}',
        page_id='6',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://wayne.com/security',
        site_data=site_datas['https://wayne.com/'],
        audit_id=f'7_{label}',
        page_id='7',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://wayne.com/legal',
        site_data=site_datas['https://wayne.com/'],
        audit_id=f'8_{label}',
        page_id='8',
        viewport=viewport,
      )
      for label, viewport in viewport_sizes.items()
      for audit_name in ['first', 'second']
    ],
  ]


def test_run_audits_only_runs_audits_at_their_viewport_to_test(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Skips an audit at any viewport other than its configured viewport_to_test."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'first': {},
      'second': {'viewport_to_test': 'small'},
    },
    {
      'viewport_sizes': {
        'small': {'width': 320, 'height': 450},
        'medium': {'width': 1280, 'height': 800},
      },
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name='first',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
      audit_name='second',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
      audit_name='first',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_medium',
      page_id='1',
      viewport={'width': 1280, 'height': 800},
    ),
  ]


def test_run_audits_returns_true_when_anti_bot_happens_after_a_success(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Returns True when anti-bot blocking happens after an earlier audit succeeded."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}, 'second': {}})

  mocker.patch.object(manager, 'test_for_anti_bot', side_effect=['Pass', 'Cloudflare'])

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    # first "get" is not blocked, so we run the audit
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    # second "get" is blocked, so we stop entirely
    ('get', 'https://bnl.com/'),
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name='first',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
  ]


def test_run_audits_returns_false_when_anti_bot_happens_before_any_success(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Returns False when anti-bot blocking happens before any audit succeeded."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}})

  mocker.patch.object(manager, 'test_for_anti_bot', return_value='Cloudflare')

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is False

  assert event_log(events) == [
    ('get', 'https://bnl.com/'),
  ]

  assert on_run.call_args_list == []


def test_run_audits_skips_audit_when_page_fails_to_load(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Skips an audit when the page fails to load, but still runs the remaining audits."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {'first': {}, 'second': {}, 'third': {}},
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  # have the second "get" fail via having the driver time out (twice, since the browser does a retry)
  manager.browser.driver.get.side_effect = [None, TimeoutException(), TimeoutException(), None]

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('get', 'https://bnl.com/'),
    # second audit is not run since the page failed to load
    ('get', 'https://bnl.com/'),
    ('run', 'third'),
  ]

  # expect only two of the audits to have been run
  assert on_run.call_args_list == [
    mocker.call(
      audit_name='first',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
      audit_name='third',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
  ]


def test_run_audits_restarts_browser_and_continues_when_an_audit_raises(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Restarts the browser and restores the viewport when an audit raises, then runs the remaining audits."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {'first': {}, 'second': {}, 'third': {}},
  )

  # have the second audit run error, with the others returning the default successful result
  on_run.side_effect = [mocker.DEFAULT, Exception('oh noes'), mocker.DEFAULT]

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  browser_set_window_size = mocker.spy(manager.browser, 'set_window_size')

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('restart',),
    ('get', 'https://bnl.com/'),
    ('run', 'third'),
  ]

  # expect the viewport to be set at the start, and then restored after the restart
  assert browser_set_window_size.call_args_list == [
    mocker.call(320, 450),
    mocker.call(320, 450),
  ]

  # expect the audit to have been called three times with the right data
  assert on_run.call_args_list == [
    mocker.call(
      audit_name='first',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
      audit_name='second',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
      audit_name='third',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
  ]


@pytest.mark.parametrize('audit_result', [True, False, []])
def test_run_audits_does_not_count_audits_without_results_as_success(
  fs: FakeFilesystem,
  mocker: MockerFixture,
  audit_result: bool | list[dict[str, str]],
) -> None:
  """Does not treat an audit that is not applicable (True), failed (False), or gave no results ([]) as a success."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}})

  on_run.return_value = audit_result

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is False

  assert event_log(events) == [
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
  ]
