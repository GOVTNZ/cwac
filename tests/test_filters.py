"""Tests for URL filters."""

import pytest

import src.filters


@pytest.mark.parametrize(
  'url',
  [
    'https://example.com/report.pdf',
    'https://example.com/a/b/report.pdf',
    'https://example.com/font.woff2',
    # extensions are matched case-insensitively
    'https://example.com/REPORT.PDF',
    'https://example.com/photo.JpEg',
    # multi-part extensions
    'https://example.com/archive.tar.gz',
    # query strings and fragments are not part of the path
    'https://example.com/report.pdf?download=1',
    'https://example.com/report.pdf#page=2',
    # params on the last path segment are not part of the path
    'https://example.com/report.pdf;jsessionid=abc',
  ],
)
def test_has_allowed_file_type_rejects_disallowed_extensions(url: str) -> None:
  """Rejects URLs whose path ends with a disallowed file extension."""
  assert src.filters.has_allowed_file_type(url) is False


@pytest.mark.parametrize(
  'url',
  [
    'https://example.com',
    'https://example.com/',
    'https://example.com/about',
    'https://example.com/about/',
    'https://example.com/index.html',
    'https://example.com/Default.aspx',
    'https://example.com/v1.2/docs',
    # only the end of the path matters
    'https://example.com/report.pdf/',
    'https://example.com/report.pdf.html',
    'https://example.com/pdf/report',
    'https://example.com/docs/pdf',
    # only the full multi-part extension is disallowed
    'https://example.com/archive.gz',
    # query strings and fragments are not part of the path
    'https://example.com/download?file=report.pdf',
    'https://example.com/page#report.pdf',
    # params on the last path segment are not part of the path
    'https://example.com/index.html;download=report.pdf',
  ],
)
def test_has_allowed_file_type_accepts_allowed_urls(url: str) -> None:
  """Accepts URLs whose path does not end with a disallowed file extension."""
  assert src.filters.has_allowed_file_type(url) is True
