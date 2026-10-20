"""Tests the behaviour of the AuditManager class."""

import json
from collections.abc import Callable
from pathlib import PurePath
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
from src.output import CSVWriter

# pylint: disable=too-many-lines


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
      url=self.browser.requested_url,
      site_data=self.site_data,
      audit_id=self.audit_id,
      page_id=self.page_id,
      viewport=dict(self.browser.viewport_size),
    )


def create_event_tracker(mocker: MockerFixture, manager: AuditManager, on_run: Mock) -> Mock:
  """Create a mock that records page loads, browser restarts, viewport changes, audit runs, and result writes in the order they happen."""
  events = Mock()

  events.attach_mock(mocker.spy(manager.browser, 'get'), 'get')
  events.attach_mock(mocker.spy(manager.browser, 'safe_restart'), 'restart')
  events.attach_mock(mocker.spy(manager.browser, 'set_window_size'), 'set_window_size')
  events.attach_mock(on_run, 'run')
  events.attach_mock(mocker.spy(CSVWriter, 'append_rows'), 'write')

  return events


def event_log(events: Mock) -> list[tuple[Any, ...]]:
  """Summarise the recorded events as (name, *args) tuples, with audit runs and result writes reduced to the audit name."""
  log: list[tuple[Any, ...]] = []

  for name, args, kwargs in events.mock_calls:
    match name:
      case 'run':
        log.append(('run', kwargs['audit_name']))
      case 'write':
        # results are written to a csv file named after the audit
        # (args[0] is the CSVWriter, as the spy is on the class)
        log.append(('write', PurePath(args[1]).stem))
      case _:
        log.append((name, *args))

  return log


def setup_manager_and_mocks(
  mocker: MockerFixture,
  audit_plugins: dict[str, Any],
  config_changes: dict[str, Any] | None = None,
) -> tuple[AuditManager, Mock, Mock]:
  """Create an AuditManager running a FakeAudit for each audit plugin, along with the events and on_run mocks.

  on_run returns a successful result by default, so tests only need to set up the failures they care about.
  """
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
      type(
        'FakeAudit',
        (FakeAudit,),
        {
          'audit_name': name,
          'modifies_page': audit_config.get('modifies_page', True),
        },
      ),
    )
    for name, audit_config in audit_plugins.items()
  }

  manager = AuditManager(config, browser, audits)
  mocker.patch.object(manager, '_check_for_closed_details_elements')
  mocker.patch.object(manager, 'test_for_anti_bot', return_value='Pass')

  events = create_event_tracker(mocker, manager, on_run)

  return manager, events, on_run


def test_run_audits_runs_an_audit_against_a_page(
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
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/news'),
    ('run', 'first'),
    ('write', 'first'),
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


def test_run_audits_runs_every_audit_against_every_page_at_every_viewport(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs each audit against multiple pages across multiple sites at multiple viewports."""
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

  # every audit modifies the page by default, so the page is reloaded before each one
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/news'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/news'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://bnl.com/news'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/news'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 320, 450),
    ('get', 'https://acme.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://acme.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://acme.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://acme.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 320, 450),
    ('get', 'https://acme.com/contact'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://acme.com/contact'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://acme.com/contact'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://acme.com/contact'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 320, 450),
    ('get', 'https://acme.com/legal'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://acme.com/legal'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://acme.com/legal'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://acme.com/legal'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 320, 450),
    ('get', 'https://wayne.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://wayne.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://wayne.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://wayne.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 320, 450),
    ('get', 'https://wayne.com/security'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://wayne.com/security'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://wayne.com/security'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://wayne.com/security'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 320, 450),
    ('get', 'https://wayne.com/legal'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://wayne.com/legal'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://wayne.com/legal'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://wayne.com/legal'),
    ('run', 'second'),
    ('write', 'second'),
  ]

  # check each audit was given the right page, site, ids, and viewport
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
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
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


def test_run_audits_writes_the_results_of_each_audit_to_its_own_file(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Writes the rows returned by each audit, unchanged, to a csv file named after that audit."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}, 'second': {}})

  on_run.side_effect = [
    [{'issue': 'a'}, {'issue': 'b'}],
    [{'issue': 'c'}],
  ]

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('write', 'second'),
  ]

  # the first argument is the CSVWriter instance, as the spy is on the class
  results_dir = f'./results/{manager.config.audit_name}'
  assert events.write.call_args_list == [
    mocker.call(mocker.ANY, f'{results_dir}/first.csv', {'issue': 'a'}, {'issue': 'b'}),
    mocker.call(mocker.ANY, f'{results_dir}/second.csv', {'issue': 'c'}),
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
  ]


def test_run_audits_reuses_the_page_after_an_audit_that_does_not_modify_it(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Skips reloading the page for the next audit when the previous audit does not modify it."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'reads': {'modifies_page': False},
      'modifies': {},
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads'),
      ('write', 'reads'),
      # no "get" since "reads" didn't modify the page
      ('run', 'modifies'),
      ('write', 'modifies'),
    ],
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name=audit_name,
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    )
    for audit_name in ['reads', 'modifies']
  ]


def test_run_audits_reuses_the_page_across_consecutive_audits_that_do_not_modify_it(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Loads the page once for a run of audits that do not modify it."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'reads_a': {'modifies_page': False},
      'reads_b': {'modifies_page': False},
      'reads_c': {'modifies_page': False},
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads_a'),
      ('write', 'reads_a'),
      # no "get" since "reads_a" didn't modify the page
      ('run', 'reads_b'),
      ('write', 'reads_b'),
      # no "get" since "reads_b" didn't modify the page
      ('run', 'reads_c'),
      ('write', 'reads_c'),
    ],
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name=audit_name,
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    )
    for audit_name in ['reads_a', 'reads_b', 'reads_c']
  ]


def test_run_audits_reloads_the_page_at_each_viewport_even_if_the_last_audit_did_not_modify_it(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Reloads the page after changing viewport, even if the last audit at the previous viewport did not modify it."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {'reads': {'modifies_page': False}},
    {
      'viewport_sizes': {
        'small': {'width': 320, 'height': 450},
        'medium': {'width': 1280, 'height': 800},
      }
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  # even though "reads" didn't modify the page, we should
  # still do a "get" as part of changing the window size
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/news'),
    ('run', 'reads'),
    ('write', 'reads'),
    ('set_window_size', 1280, 800),
    ('get', 'https://bnl.com/news'),
    ('run', 'reads'),
    ('write', 'reads'),
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name='reads',
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
      audit_name='reads',
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_medium',
      page_id='1',
      viewport={'width': 1280, 'height': 800},
    ),
  ]


def test_run_audits_reuses_the_page_across_an_audit_skipped_for_its_viewport_to_test(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Does not treat an audit skipped due to its viewport_to_test as having modified the page."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'reads': {'modifies_page': False},
      'modifies_small_only': {'viewport_to_test': 'small'},
      'modifies': {},
    },
    {
      'viewport_sizes': {
        'small': {'width': 320, 'height': 450},
        'medium': {'width': 1280, 'height': 800},
      }
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  # "modifies_small_only" sits between two audits but only runs on
  # the "small" viewport, so at the "medium" viewport we should only
  # make a single "get" as the "reads" audit didn't modify the page
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads'),
      ('write', 'reads'),
      # no "get" since "reads" didn't modify the page
      ('run', 'modifies_small_only'),
      ('write', 'modifies_small_only'),
    ],
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'modifies'),
      ('write', 'modifies'),
    ],
    ('set_window_size', 1280, 800),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads'),
      ('write', 'reads'),
      # no "get" since "reads" didn't modify the page, and "modifies_small_only" is skipped
      ('run', 'modifies'),
      ('write', 'modifies'),
    ],
  ]

  assert on_run.call_args_list == [
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://bnl.com/news',
        site_data=site_data,
        audit_id='1_small',
        page_id='1',
        viewport={'width': 320, 'height': 450},
      )
      for audit_name in ['reads', 'modifies_small_only', 'modifies']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://bnl.com/news',
        site_data=site_data,
        audit_id='1_medium',
        page_id='1',
        viewport={'width': 1280, 'height': 800},
      )
      for audit_name in ['reads', 'modifies']
    ],
  ]


def test_run_audits_runs_audits_that_do_not_modify_the_page_first(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs audits that do not modify the page before those that do, so the page is loaded as few times as possible."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'modifies_a': {},
      'reads_a': {'modifies_page': False},
      'modifies_b': {},
      'reads_b': {'modifies_page': False},
      'reads_c': {'modifies_page': False},
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  # we should run all audits that don't modify the page first with a single "get",
  # and then run the remaining page-modifying audits, with a "get" between each
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads_a'),
      ('write', 'reads_a'),
      ('run', 'reads_b'),
      ('write', 'reads_b'),
      ('run', 'reads_c'),
      ('write', 'reads_c'),
      ('run', 'modifies_a'),
      ('write', 'modifies_a'),
    ],
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'modifies_b'),
      ('write', 'modifies_b'),
    ],
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name=audit_name,
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    )
    for audit_name in [
      'reads_a',
      'reads_b',
      'reads_c',
      'modifies_a',
      'modifies_b',
    ]
  ]


def test_run_audits_runs_audits_that_do_not_modify_the_page_first_at_each_viewport(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs audits that do not modify the page first at each viewport, including when some only run at certain viewports."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'modifies': {},
      'reads_small_only': {'modifies_page': False, 'viewport_to_test': 'small'},
      'reads': {'modifies_page': False},
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

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  # modifies_page and viewport_to_test should be independent of each other, so at the "medium"
  # viewport the audits should run as if "reads_small_only" wasn't configured at all
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads_small_only'),
      ('write', 'reads_small_only'),
      ('run', 'reads'),
      ('write', 'reads'),
      ('run', 'modifies'),
      ('write', 'modifies'),
    ],
    ('set_window_size', 1280, 800),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads'),
      ('write', 'reads'),
      ('run', 'modifies'),
      ('write', 'modifies'),
    ],
  ]

  assert on_run.call_args_list == [
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://bnl.com/news',
        site_data=site_data,
        audit_id='1_small',
        page_id='1',
        viewport={'width': 320, 'height': 450},
      )
      for audit_name in ['reads_small_only', 'reads', 'modifies']
    ],
    *[
      mocker.call(
        audit_name=audit_name,
        url='https://bnl.com/news',
        site_data=site_data,
        audit_id='1_medium',
        page_id='1',
        viewport={'width': 1280, 'height': 800},
      )
      for audit_name in ['reads', 'modifies']
    ],
  ]


def test_run_audits_stops_auditing_entirely_when_anti_bot_happens(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Stops running audits entirely when anti-bot blocking happens, including at any remaining viewports."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {'first': {}, 'second': {}},
    {
      'viewport_sizes': {
        'small': {'width': 320, 'height': 450},
        'medium': {'width': 1280, 'height': 800},
      },
    },
  )

  mocker.patch.object(manager, 'test_for_anti_bot', side_effect=['Pass', 'Cloudflare'])

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    # the page is blocked, so the medium viewport is never audited
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
    ('set_window_size', 320, 450),
    # first "get" is not blocked, so we run the audit
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
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
    ('set_window_size', 320, 450),
    # the page is blocked, so no audits are run
    ('get', 'https://bnl.com/'),
  ]

  assert on_run.call_args_list == []


def test_run_audits_only_checks_for_anti_bot_when_the_page_is_loaded(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Only checks for anti-bot blocking after loading the page, not before audits that reuse it."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'reads': {'modifies_page': False},
      'modifies_a': {},
      'modifies_b': {},
    },
  )

  mocker.patch.object(manager, 'test_for_anti_bot', side_effect=['Pass', 'Cloudflare'])

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  # anti-bot checking should only be done after a "get", so "modifies_a" shouldn't
  # be blocked since it can reuse the unmodified page after running the "reads" audit
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/'),
      ('run', 'reads'),
      ('write', 'reads'),
      # no "get" since "reads" didn't modify the page, so no anti-bot check either
      ('run', 'modifies_a'),
      ('write', 'modifies_a'),
    ],
    # this "get" is blocked, so we stop entirely
    *[
      ('get', 'https://bnl.com/'),
    ],
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name=audit_name,
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    )
    for audit_name in ['reads', 'modifies_a']
  ]


def test_run_audits_skips_an_audit_when_the_page_fails_to_load(
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
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/'),
    # second audit is not run since the page failed to load
    ('get', 'https://bnl.com/'),
    ('run', 'third'),
    ('write', 'third'),
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
      audit_name='third',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
  ]


def test_run_audits_returns_false_when_the_page_fails_to_load_for_every_audit(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Returns False when the page fails to load for every audit, as no audit could produce results."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}, 'second': {}})

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  # have every "get" fail via having the driver time out
  manager.browser.driver.get.side_effect = TimeoutException()

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is False

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('get', 'https://bnl.com/'),
  ]

  assert on_run.call_args_list == []


def test_run_audits_loads_the_page_for_an_audit_that_does_not_modify_it_after_a_failed_load(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Loads the page for the next audit when the previous load failed, even if the previous audit would not have modified it."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'reads_a': {'modifies_page': False},
      'reads_b': {'modifies_page': False},
      'modifies': {},
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  # have the first "get" fail via having the driver time out (twice, since the browser does a retry)
  manager.browser.driver.get.side_effect = [TimeoutException(), TimeoutException(), None]

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  # we should always do a "get" if the previous "get" was not successful,
  # regardless of whether the audit we tried to run modifies the page or not
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
    ],
    # "reads_a" is not run since the page failed to load,
    # so the page is loaded again for the next two audits
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads_b'),
      ('write', 'reads_b'),
      ('run', 'modifies'),
      ('write', 'modifies'),
    ],
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name=audit_name,
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    )
    for audit_name in ['reads_b', 'modifies']
  ]


def test_run_audits_restarts_the_browser_and_continues_when_an_audit_raises(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Restarts the browser and restores the viewport when an audit raises, then runs the remaining audits."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {'first': {}, 'second': {}, 'third': {}},
  )

  # have "reads_b" error, with the others returning the default successful result
  on_run.side_effect = [mocker.DEFAULT, Exception('oh noes'), mocker.DEFAULT]

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    # second audit raised, so the browser is restarted and the viewport restored
    ('restart',),
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'third'),
    ('write', 'third'),
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
      audit_name='third',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
  ]


def test_run_audits_restores_the_current_viewport_when_an_audit_raises(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Restores the viewport being audited, rather than the first, when an audit raises after the first viewport."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {'first': {}, 'second': {}},
    {
      'viewport_sizes': {
        'small': {'width': 320, 'height': 450},
        'medium': {'width': 1280, 'height': 800},
      },
    },
  )

  # have the first audit run at the medium viewport error
  on_run.side_effect = [mocker.DEFAULT, mocker.DEFAULT, Exception('oh noes'), mocker.DEFAULT]

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('write', 'first'),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('write', 'second'),
    ('set_window_size', 1280, 800),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    # first audit raised, so the browser is restarted at the medium viewport
    ('restart',),
    ('set_window_size', 1280, 800),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('write', 'second'),
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
    mocker.call(
      audit_name='second',
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_medium',
      page_id='1',
      viewport={'width': 1280, 'height': 800},
    ),
  ]


def test_run_audits_returns_false_when_every_audit_raises(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Returns False when every audit raises, as no audit produced results."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}, 'second': {}})

  on_run.side_effect = Exception('oh noes')

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is False

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    ('restart',),
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'second'),
    ('restart',),
    ('set_window_size', 320, 450),
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
  ]


def test_run_audits_reloads_the_page_after_an_audit_that_does_not_modify_it_raises(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Reloads the page after a restart, even when the audit that raised does not modify the page."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'reads_a': {'modifies_page': False},
      'reads_b': {'modifies_page': False},
      'reads_c': {'modifies_page': False},
    },
  )

  # have "reads_b" error, with the others returning the default successful result
  on_run.side_effect = [mocker.DEFAULT, Exception('oh noes'), mocker.DEFAULT]

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  # even though none of the audits modify the page, we should do a second
  # "get" since the browser is restarted due to "reads_b" raising an error
  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads_a'),
      ('write', 'reads_a'),
      # no "get" since "reads_a" didn't modify the page
      ('run', 'reads_b'),
      # "reads_b" raised, so the browser is restarted and the page reloaded
      ('restart',),
    ],
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/news'),
      ('run', 'reads_c'),
      ('write', 'reads_c'),
    ],
  ]

  assert on_run.call_args_list == [
    mocker.call(
      audit_name=audit_name,
      url='https://bnl.com/news',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    )
    for audit_name in ['reads_a', 'reads_b', 'reads_c']
  ]


@pytest.mark.parametrize('audit_result', [True, False, []])
def test_run_audits_returns_false_when_no_audit_produces_results(
  fs: FakeFilesystem,
  mocker: MockerFixture,
  audit_result: bool | list[dict[str, str]],
) -> None:
  """Returns False when the only audit is not applicable (True), failed (False), or gave no results ([])."""
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
    ('set_window_size', 320, 450),
    ('get', 'https://bnl.com/'),
    ('run', 'first'),
    # the audit gave no results, so nothing is written
  ]


def test_run_audits_returns_true_when_any_audit_produces_results(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Returns True when at least one audit produced results, even if others did not."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(mocker, {'first': {}, 'second': {}})

  # have the first audit give no results, with the second returning the default successful result
  on_run.side_effect = [[], mocker.DEFAULT]

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/'),
      ('run', 'first'),
    ],
    # the first audit gave no results, so nothing is written for it
    *[
      ('get', 'https://bnl.com/'),
      ('run', 'second'),
      ('write', 'second'),
    ],
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
  ]


@pytest.mark.parametrize('audit_result', [True, False, []])
def test_run_audits_reuses_the_page_after_an_audit_that_does_not_modify_it_produces_no_results(
  fs: FakeFilesystem,
  mocker: MockerFixture,
  audit_result: bool | list[dict[str, str]],
) -> None:
  """Reuses the page after an audit that does not modify it, regardless of whether it produced results."""
  setup_filesystem(fs)

  manager, events, on_run = setup_manager_and_mocks(
    mocker,
    {
      'reads': {'modifies_page': False},
      'modifies': {},
    },
  )

  on_run.return_value = audit_result

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is False

  assert event_log(events) == [
    ('set_window_size', 320, 450),
    *[
      ('get', 'https://bnl.com/'),
      ('run', 'reads'),
      # no "get" since "reads" didn't modify the page, even though it gave no results
      ('run', 'modifies'),
      # neither audit gave results, so nothing is written
    ],
  ]
