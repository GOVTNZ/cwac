"""Tests for URL helpers."""

import pytest

from src.urls import normalize_url


@pytest.mark.parametrize(
  ('url', 'expected'),
  [
    ('HTTPS://Example.COM/Path', 'https://example.com/Path'),
    ('https://example.com', 'https://example.com/'),
    ('https://example.com:443/', 'https://example.com/'),
    ('https://example.com:8080/', 'https://example.com:8080/'),
    ('https://example.com/a/../b/./c', 'https://example.com/b/c'),
    ('https://example.com/a/%2e%2e/b', 'https://example.com/b'),
    ('https://example.com/a//b', 'https://example.com/a//b'),
    ('https://example.com/a,b+c', 'https://example.com/a,b+c'),
    ('https://example.com/a b/café', 'https://example.com/a%20b/caf%C3%A9'),
    ('https://example.com/caf%c3%a9', 'https://example.com/caf%C3%A9'),
    ('https://example.com/?q=%2f', 'https://example.com/?q=%2f'),
  ],
)
def test_normalize_url(url: str, expected: str) -> None:
  """Normalizes URLs per the WHATWG URL Standard, uppercasing path percent-escapes."""
  assert normalize_url(url) == expected


@pytest.mark.parametrize(
  ('url', 'expected'),
  [
    ('https://www.māorilandcourt.govt.nz/', 'https://www.xn--morilandcourt-wqb.govt.nz/'),
    ('https://www.TEKĀHUIKAUMĀTUA.govt.nz/', 'https://www.xn--tekhuikaumtua-yqbh.govt.nz/'),
    ('https://māori.nz:8080/', 'https://xn--mori-qsa.nz:8080/'),
    # browsers keep "ß" rather than mapping it to "ss"
    ('https://straße.de/', 'https://xn--strae-oqa.de/'),
    # browsers map a capital "Σ" to "σ" rather than the final form "ς"
    ('https://ΟΣ.gr/', 'https://xn--0xai.gr/'),
  ],
)
def test_normalize_url_converts_internationalized_domain_names_to_punycode(url: str, expected: str) -> None:
  """Converts internationalized domain names to punycode, as browsers do."""
  assert normalize_url(url) == expected


@pytest.mark.parametrize('url', ['', 'example.com', 'https://exa mple.com/', 'https://[::1/'])
def test_normalize_url_raises_on_invalid_url(url: str) -> None:
  """Raises a ValueError when the URL is not valid."""
  with pytest.raises(ValueError, match='Invalid input'):
    normalize_url(url)
