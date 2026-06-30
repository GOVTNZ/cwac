"""Tests the behaviour of the AuditManager class."""

from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from src.audit_manager import AuditManager


class SuccessfulAudit:
  """Test audit that always returns a successful result."""

  def __init__(self, **_: object) -> None:
    """Init variables."""

  def run(self) -> list[dict[str, str]]:
    """Return a non-empty audit result."""
    return [{'result': 'ok'}]


def make_audit_manager(mocker: MockerFixture) -> AuditManager:
  """Create an AuditManager with mocked dependencies for unit tests."""
  mocker.patch('src.audit_manager.src.filters.URLFilter')

  config = MagicMock()
  config.viewport_sizes = {'small': {'width': 320, 'height': 640}}
  config.audit_plugins = {'first': {}, 'second': {}}
  config.audit_name = 'test-audit'
  config.delay_between_viewports = 0
  config.get_unique_id.return_value = 'page-id'

  browser = MagicMock()
  browser.get_if_necessary.return_value = True
  browser.driver = MagicMock()

  manager = AuditManager(config, browser, MagicMock())
  mocker.patch.object(manager, 'check_for_details_elements')
  mocker.patch('src.audit_manager.CSVWriter')

  return manager


def test_run_audits_returns_true_when_anti_bot_happens_after_a_success(
  mocker: MockerFixture,
) -> None:
  """Returns True when anti-bot blocking happens after an earlier audit succeeded."""
  manager = make_audit_manager(mocker)

  manager.register_audit('first', SuccessfulAudit, url='https://example.govt.nz/ok')
  manager.register_audit('second', SuccessfulAudit, url='https://example.govt.nz/blocked')

  mocker.patch.object(manager, 'test_for_anti_bot', side_effect=['Pass', 'Cloudflare'])

  assert manager.run_audits() is True


def test_run_audits_returns_false_when_anti_bot_happens_before_any_success(
  mocker: MockerFixture,
) -> None:
  """Returns False when anti-bot blocking happens before any audit succeeded."""
  manager = make_audit_manager(mocker)

  manager.register_audit('first', SuccessfulAudit, url='https://example.govt.nz/blocked')

  mocker.patch.object(manager, 'test_for_anti_bot', return_value='Cloudflare')

  assert manager.run_audits() is False
