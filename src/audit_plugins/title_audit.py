"""TitleAudit plugin.

This plugin records the titles of each page that is visited,
which can be used to verify all pages have a unique title.
"""

import logging
from typing import Any

from src.audit_plugins.default_audit import DefaultAudit

logger = logging.getLogger('cwac')


class TitleAudit(DefaultAudit):
  """element audit."""

  audit_type = 'TitleAudit'

  def run(self) -> list[dict[str, Any]] | bool:
    """Run a title audit on a specified URL.

    Returns:
        list[dict[str, Any]]: a list of audit result dicts
    """
    return [{**self._default_audit_row, 'title': self.browser.driver.title}]
