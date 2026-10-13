"""Tests the behaviour of the AuditManager class."""

import json
from collections.abc import Callable
from typing import Any

from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture

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
  """An audit that reports the conditions it was run under via on_run."""

  on_run: Callable[..., None] = staticmethod(lambda **_: None)

  def run(self) -> list[dict[str, str]]:
    """Report the current url, site data, ids, and browser viewport to on_run."""
    self.on_run(
      url=self.url,
      site_data=self.site_data,
      audit_id=self.audit_id,
      page_id=self.page_id,
      viewport=dict(self.browser.viewport_size),
    )
    return [{}]


def make_audit_manager(mocker: MockerFixture, config_changes: dict[str, Any] | None = None) -> AuditManager:
  """Create an AuditManager using a real Config and Browser, but a stubbed webdriver."""
  modify_default_config(
    {
      'viewport_sizes': {'small': {'width': 320, 'height': 450}},
      'audit_plugins': {'first': {}, 'second': {}},
      **(config_changes or {}),
      'delay_after_page_load': 0,
    }
  )

  config = Config('config_default.json')

  mocker.patch('src.browser.webdriver.Chrome')
  browser = Browser(config, 1)

  manager = AuditManager(config, browser)
  mocker.patch.object(manager, '_check_for_closed_details_elements')
  mocker.patch.object(manager, 'test_for_anti_bot', return_value='Pass')

  return manager


def test_run_audits_single_page_single_viewport_single_audit(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs the audit against a single page at a single viewport."""
  on_run = mocker.patch.object(FakeAudit, 'on_run')

  setup_filesystem(fs)

  manager = make_audit_manager(mocker)

  manager.register_audit('first', FakeAudit)

  browser_get = mocker.spy(manager.browser, 'get')

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/news', site_data=site_data) is True

  assert browser_get.call_args_list == [
    mocker.call('https://bnl.com/news'),
  ]

  assert on_run.call_args_list == [
    mocker.call(
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
  on_run = mocker.patch.object(FakeAudit, 'on_run')

  setup_filesystem(fs)

  # the config and browser are shared across the whole run, like in the tool
  base_manager = make_audit_manager(
    mocker,
    {
      'viewport_sizes': {
        'small': {'width': 320, 'height': 450},
        'medium': {'width': 1280, 'height': 800},
      },
    },
  )
  config, browser = base_manager.config, base_manager.browser
  browser_get = mocker.spy(browser, 'get')

  page_id = 0

  # this mirrors how the tool ends up running the audit manager
  for base_url, urls in {
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
  }.items():
    site_data: SiteData = {
      'url': base_url,
      'supports_head': True,
      'columns': {'url': base_url},
    }

    # each site gets its own audit manager, like in the crawler
    manager = AuditManager(config, browser)
    mocker.patch.object(manager, '_check_for_closed_details_elements')
    mocker.patch.object(manager, 'test_for_anti_bot', return_value='Pass')

    for url in urls:
      page_id += 1
      browser_get.reset_mock()
      on_run.reset_mock()

      manager.register_audit('first', FakeAudit)
      manager.register_audit('second', FakeAudit)

      assert manager.run_audits(url=url, site_data=site_data) is True

      assert browser_get.call_args_list == [
        mocker.call(url),
        mocker.call(url),
        mocker.call(url),
        mocker.call(url),
      ]

      assert on_run.call_args_list == [
        mocker.call(
          url=url,
          site_data=site_data,
          audit_id=f'{page_id}_small',
          page_id=f'{page_id}',
          viewport={'width': 320, 'height': 450},
        ),
        mocker.call(
          url=url,
          site_data=site_data,
          audit_id=f'{page_id}_small',
          page_id=f'{page_id}',
          viewport={'width': 320, 'height': 450},
        ),
        mocker.call(
          url=url,
          site_data=site_data,
          audit_id=f'{page_id}_medium',
          page_id=f'{page_id}',
          viewport={'width': 1280, 'height': 800},
        ),
        mocker.call(
          url=url,
          site_data=site_data,
          audit_id=f'{page_id}_medium',
          page_id=f'{page_id}',
          viewport={'width': 1280, 'height': 800},
        ),
      ]


def test_run_audits_only_runs_audits_at_their_viewport_to_test(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Skips an audit at any viewport other than its configured viewport_to_test."""
  on_run = mocker.patch.object(FakeAudit, 'on_run')

  setup_filesystem(fs)

  manager = make_audit_manager(
    mocker,
    {
      'viewport_sizes': {
        'small': {'width': 320, 'height': 450},
        'medium': {'width': 1280, 'height': 800},
      },
      'audit_plugins': {
        'first': {},
        'second': {'viewport_to_test': 'small'},
      },
    },
  )

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  manager.register_audit('first', FakeAudit)

  manager.register_audit('second', FakeAudit)

  browser_get = mocker.spy(manager.browser, 'get')

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert browser_get.call_args_list == [
    mocker.call('https://bnl.com/'),
    mocker.call('https://bnl.com/'),
    mocker.call('https://bnl.com/'),
  ]

  assert on_run.call_args_list == [
    mocker.call(
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
      url='https://bnl.com/',
      site_data=site_data,
      audit_id='1_small',
      page_id='1',
      viewport={'width': 320, 'height': 450},
    ),
    mocker.call(
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
  on_run = mocker.patch.object(FakeAudit, 'on_run')

  setup_filesystem(fs)

  manager = make_audit_manager(mocker)

  manager.register_audit('first', FakeAudit)
  manager.register_audit('second', FakeAudit)

  mocker.patch.object(manager, 'test_for_anti_bot', side_effect=['Pass', 'Cloudflare'])

  browser_get = mocker.spy(manager.browser, 'get')

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is True

  assert browser_get.call_args_list == [
    mocker.call('https://bnl.com/'),
    mocker.call('https://bnl.com/'),
  ]

  assert on_run.call_args_list == [
    mocker.call(
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
  on_run = mocker.patch.object(FakeAudit, 'on_run')

  setup_filesystem(fs)

  manager = make_audit_manager(mocker)

  manager.register_audit('first', FakeAudit)

  mocker.patch.object(manager, 'test_for_anti_bot', return_value='Cloudflare')

  browser_get = mocker.spy(manager.browser, 'get')

  site_data: SiteData = {
    'url': 'https://bnl.com/',
    'supports_head': True,
    'columns': {'url': 'https://bnl.com/'},
  }

  assert manager.run_audits(url='https://bnl.com/', site_data=site_data) is False

  assert browser_get.call_args_list == [
    mocker.call('https://bnl.com/'),
  ]

  assert on_run.call_args_list == []
