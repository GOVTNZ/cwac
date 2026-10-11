"""Tests the behaviour of the PageQueue class."""

import random

import pytest

from src.page_queue import PageQueue, QueuedPage


def queued_page(path: str) -> QueuedPage:
  """Build a QueuedPage for the given path on a test site."""
  return QueuedPage(parent_url='https://example.com/', url=f'https://example.com/{path}')


class TestPageQueue:
  """Tests the PageQueue class."""

  def test_pops_the_randomly_picked_item(
    self,
    monkeypatch: pytest.MonkeyPatch,
  ) -> None:
    """Pops the item at the index returned by the random number generator."""
    queue = PageQueue()

    for path in ['a', 'b', 'c', 'd', 'e']:
      queue.push(queued_page(path))

    picks = iter([1, 0, 2, 1, 0])
    monkeypatch.setattr(random, 'randrange', lambda _: next(picks))

    # each pick moves the last item into the picked item's slot
    assert queue.pop() == queued_page('b')  # [a, e, c, d]
    assert queue.pop() == queued_page('a')  # [d, e, c]
    assert queue.pop() == queued_page('c')  # [d, e]
    assert queue.pop() == queued_page('e')  # [d]
    assert queue.pop() == queued_page('d')  # []

    assert len(queue) == 0

  def test_picks_within_the_bounds_of_the_queue(
    self,
    monkeypatch: pytest.MonkeyPatch,
  ) -> None:
    """Asks for a random index within the current length of the queue."""
    queue = PageQueue()

    for i in range(5):
      queue.push(queued_page(str(i)))

    calls: list[int] = []

    def fake_randrange(stop: int) -> int:
      calls.append(stop)
      return stop - 1

    monkeypatch.setattr(random, 'randrange', fake_randrange)

    while len(queue) > 0:
      queue.pop()

    assert calls == [5, 4, 3, 2, 1]

  def test_pops_every_item_exactly_once(self) -> None:
    """Pops every pushed item exactly once."""
    queue = PageQueue()

    items = [queued_page(str(i)) for i in range(100)]
    for item in items:
      queue.push(item)

    popped = [queue.pop() for _ in range(100)]

    assert sorted(popped) == sorted(items)
    assert len(queue) == 0

  def test_pop_from_empty_queue_raises(self) -> None:
    """Raises when popping from an empty queue."""
    queue = PageQueue()

    with pytest.raises(ValueError, match='empty range'):
      queue.pop()
