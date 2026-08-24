"""Tests the behaviour of the verify_axe_results function."""

import logging

from src.verify import verify_axe_results


def test_no_warning_when_max_links_per_domain_is_zero(caplog: logging.Logger) -> None:
  """A max_links_per_domain of 0 means no limit, so counts are not checked."""
  with caplog.at_level(logging.WARNING, logger='cwac'):
    verify_axe_results(
      max_links_per_domain=0,
      pages_scanned={'https://example.govt.nz': {'https://example.govt.nz/a', 'https://example.govt.nz/b'}},
    )

  assert caplog.records == []


def test_warning_when_page_count_does_not_match_limit(caplog: logging.Logger) -> None:
  """A site with fewer pages than the limit is reported."""
  with caplog.at_level(logging.WARNING, logger='cwac'):
    verify_axe_results(
      max_links_per_domain=3,
      pages_scanned={'https://example.govt.nz': {'https://example.govt.nz/a'}},
    )

  assert len(caplog.records) == 1
  assert 'had 1 pages scanned, not 3' in caplog.records[0].getMessage()


def test_no_warning_when_page_count_matches_limit(caplog: logging.Logger) -> None:
  """A site with exactly the expected number of pages is not reported."""
  with caplog.at_level(logging.WARNING, logger='cwac'):
    verify_axe_results(
      max_links_per_domain=2,
      pages_scanned={'https://example.govt.nz': {'https://example.govt.nz/a', 'https://example.govt.nz/b'}},
    )

  assert caplog.records == []
