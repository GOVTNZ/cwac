"""Tests for detecting object coercion text in rendered pages."""

from unittest.mock import MagicMock

import pytest

from src.audit_plugins.rendered_object_audit import RenderedObjectAudit


@pytest.mark.parametrize(
  ('text', 'num_issues'),
  [
    ('Welcome to our site', 0),
    ('null undefined', 0),
    ('', 0),
    ('[Object Object]', 0),
    ('Hello [object Object]', 1),
    ('[object Promise] and [object Object]', 2),
    ('Incomplete [object', 1),
  ],
)
def test_counts_rendered_object_text(text: str, num_issues: int) -> None:
  """Report both clean pages and object text, including incomplete tokens."""
  browser = MagicMock()
  browser.driver.execute_script.return_value = text
  audit = RenderedObjectAudit(
    config=MagicMock(),
    browser=browser,
    url='https://example.govt.nz/page',
    site_data={'url': 'https://example.govt.nz', 'columns': {}, 'supports_head': True},
    audit_id='audit-id',
    page_id='page-id',
  )

  result = audit.run()

  assert isinstance(result, list)
  assert len(result) == 1
  assert result[0]['num_issues'] == num_issues
  assert result[0]['audit_type'] == 'RenderedObjectAudit'
  assert result[0]['url'] == 'https://example.govt.nz/page'
  assert result[0]['page_id'] == 'page-id'


def test_returns_false_when_rendered_text_cannot_be_read() -> None:
  """Browser errors are reported as failed audits rather than clean pages."""
  browser = MagicMock()
  browser.driver.execute_script.side_effect = RuntimeError('Browser disconnected')
  audit = RenderedObjectAudit(
    config=MagicMock(),
    browser=browser,
    url='https://example.govt.nz/page',
    site_data={'url': 'https://example.govt.nz', 'columns': {}, 'supports_head': True},
    audit_id='audit-id',
    page_id='page-id',
  )

  assert audit.run() is False
