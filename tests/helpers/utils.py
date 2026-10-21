"""Utilities for tests."""

from src.urls import NormalizedUrl, normalize_url


def normalized_url(url: str) -> NormalizedUrl:
  """Mark a URL as normalized, asserting that it already is.

  This should be used for string literals to ensure they are in normalized form
  rather than casting.
  """
  normalized = normalize_url(url)

  assert normalized == url, f'{url!r} is not normalized (expected {normalized!r})'

  return normalized
