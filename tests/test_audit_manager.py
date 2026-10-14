"""Tests the behaviour of the AuditManager class."""

import json
from typing import Any

from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture

from config import Config, SiteData
from src.audit_manager import AuditManager
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


class FakeAudit:
  """Test audit that always returns a successful result."""

  def __init__(self, **_: object) -> None:
    """Init variables."""

  def run(self) -> list[dict[str, str]]:
    """Return a non-empty audit result."""
    return [{'result': 'ok'}]


def make_audit_manager(mocker: MockerFixture) -> AuditManager:
  """Create an AuditManager with mocked dependencies for unit tests."""
  modify_default_config(
    {
      'viewport_sizes': {'small': {'width': 320, 'height': 450}},
      'audit_plugins': {'first': {}, 'second': {}},
      'delay_after_page_load': 0,
    }
  )

  config = Config('config_default.json')

  mocker.patch('src.browser.webdriver.Chrome')
  browser = Browser(config, 1)

  manager = AuditManager(config, browser)
  mocker.patch.object(manager, '_check_for_closed_details_elements')

  return manager


def test_run_audits_single_page_single_viewport_single_audit(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs the audit against a single page at a single viewport."""
  setup_filesystem(fs)

  manager = make_audit_manager(mocker)

  manager.register_audit(
    'first',
    FakeAudit,
    url='https://bnl.com/news',
    site_data={
      'url': 'https://bnl.com/',
      'supports_head': True,
      'columns': {'url': 'https://bnl.com/'},
    },
  )

  browser_get = mocker.spy(manager.browser, 'get')

  assert manager.run_audits() is True

  assert browser_get.call_args_list == [
    mocker.call('https://bnl.com/news'),
  ]


def test_run_audits_multiple_sites_pages_viewports_and_audits(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Runs the audit against multiple pages across multiple sites at multiple viewports."""
  setup_filesystem(fs)

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

    for url in urls:
      manager = make_audit_manager(mocker)

      manager.register_audit(
        'first',
        FakeAudit,
        url=url,
        site_data=site_data,
      )
      manager.register_audit(
        'second',
        FakeAudit,
        url=url,
        site_data=site_data,
      )

      browser_get = mocker.spy(manager.browser, 'get')

      assert manager.run_audits() is True

      assert browser_get.call_args_list == [
        mocker.call(url),
        mocker.call(url),
      ]


def test_run_audits_returns_true_when_anti_bot_happens_after_a_success(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Returns True when anti-bot blocking happens after an earlier audit succeeded."""
  setup_filesystem(fs)

  manager = make_audit_manager(mocker)

  manager.register_audit(
    'first',
    FakeAudit,
    url='https://example.govt.nz/ok',
    site_data={
      'url': 'https://bnl.com/',
      'supports_head': True,
      'columns': {
        'organisation': "Buy 'n' Large",
        'url': 'https://bnl.com/',
        'sector': 'Sales',
        'region': 'Overseas',
        'priority': 'Medium',
      },
    },
  )
  manager.register_audit(
    'second',
    FakeAudit,
    url='https://example.govt.nz/blocked',
    site_data={
      'url': 'https://bnl.com/',
      'supports_head': True,
      'columns': {
        'url': 'https://bnl.com/',
      },
    },
  )

  mocker.patch.object(manager, 'test_for_anti_bot', side_effect=['Pass', 'Cloudflare'])

  browser_get = mocker.spy(manager.browser, 'get')

  assert manager.run_audits() is True

  assert browser_get.call_args_list == [
    mocker.call('https://example.govt.nz/ok'),
    mocker.call('https://example.govt.nz/blocked'),
  ]


def test_run_audits_returns_false_when_anti_bot_happens_before_any_success(
  fs: FakeFilesystem,
  mocker: MockerFixture,
) -> None:
  """Returns False when anti-bot blocking happens before any audit succeeded."""
  setup_filesystem(fs)

  manager = make_audit_manager(mocker)

  manager.register_audit(
    'first',
    FakeAudit,
    url='https://example.govt.nz/blocked',
    site_data={
      'url': 'https://bnl.com/',
      'supports_head': True,
      'columns': {
        'url': 'https://bnl.com/',
      },
    },
  )

  mocker.patch.object(manager, 'test_for_anti_bot', return_value='Cloudflare')

  browser_get = mocker.spy(manager.browser, 'get')

  assert manager.run_audits() is False

  assert browser_get.call_args_list == [
    mocker.call('https://example.govt.nz/blocked'),
  ]
