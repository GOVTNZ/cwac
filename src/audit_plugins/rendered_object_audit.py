"""Detect JavaScript object coercion text in rendered page content."""

import logging
from typing import Any

from src.audit_plugins.default_audit import DefaultAudit

logger = logging.getLogger('cwac')


class RenderedObjectAudit(DefaultAudit):
  """Count occurrences of ``[object`` in the page's rendered body text."""

  audit_type = 'RenderedObjectAudit'

  def run(self) -> list[dict[str, Any]] | bool:
    """Return one result per page, including pages with no matches."""
    try:
      text = self.browser.driver.execute_script("return document.body ? document.body.innerText : '';")
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception('Failed to get rendered text %s', self.url)
      return False

    return [
      {
        **self._default_audit_row,
        'audit_type': self.audit_type,
        'num_issues': text.count('[object'),
      }
    ]
