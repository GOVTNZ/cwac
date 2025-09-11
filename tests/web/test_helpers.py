"""Helpers for tests."""

from bs4 import BeautifulSoup


def assert_has_valid_field(html: bytes, name: str) -> None:
  """Assert that there is a valid field with the given `name`."""
  soup = BeautifulSoup(html, 'html.parser')

  # check for the valid field
  fields = soup.select(f"[name='{name}']")

  assert len(fields) != 0, f'No fields named {name} found'
  assert len(fields) == 1, f'Multiple fields named {name} found'

  assert 'is-invalid' not in fields[0]['class'], f'No valid field named {name} found'

  # check for no validation feedback within the same parent as the field
  feedbacks = soup.select(f"[name='{name}'] ~ .invalid-feedback")

  assert len(feedbacks) == 0, f'Found validation feedback section near to valid field named {name}'


def assert_has_invalid_field(html: bytes, name: str, feedback: str) -> None:
  """Assert that there is an invalid field with the given `name` and feedback message."""
  soup = BeautifulSoup(html, 'html.parser')

  # check for the invalid field
  fields = soup.select(f"[name='{name}']")

  assert len(fields) != 0, f'No fields named {name} found'
  assert len(fields) == 1, f'Multiple fields named {name} found'

  assert 'is-invalid' in fields[0]['class'], f'No invalid field named {name} found'

  # check for validation feedback within the same parent as the field
  feedbacks = soup.select(f"[name='{name}'] ~ .invalid-feedback")

  assert len(feedbacks) != 0, f'No validation feedback sections near to field named {name} found'
  assert len(feedbacks) == 1, f'Multiple validation feedback sections near field named {name} found'

  assert feedback in feedbacks[0].get_text(strip=True)
