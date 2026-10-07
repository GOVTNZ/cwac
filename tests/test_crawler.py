"""Tests the behaviour of the crawler classes and functions."""

import random

import pytest

from src.crawler import RandomQueue


class TestRandomQueue:
  """Tests the RandomQueue class."""

  def test_pops_the_randomly_picked_item(
    self,
    monkeypatch: pytest.MonkeyPatch,
  ) -> None:
    """Pops the item at the index returned by the random number generator."""
    queue = RandomQueue[str]()

    for item in ['a', 'b', 'c', 'd', 'e']:
      queue.push(item)

    picks = iter([1, 0, 2, 1, 0])
    monkeypatch.setattr(random, 'randrange', lambda _: next(picks))

    # each pick moves the last item into the picked item's slot
    assert queue.pop() == 'b'  # [a, e, c, d]
    assert queue.pop() == 'a'  # [d, e, c]
    assert queue.pop() == 'c'  # [d, e]
    assert queue.pop() == 'e'  # [d]
    assert queue.pop() == 'd'  # []

    assert len(queue) == 0

  def test_picks_within_the_bounds_of_the_queue(
    self,
    monkeypatch: pytest.MonkeyPatch,
  ) -> None:
    """Asks for a random index within the current length of the queue."""
    queue = RandomQueue[int]()

    for item in range(5):
      queue.push(item)

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
    queue = RandomQueue[int]()

    for item in range(100):
      queue.push(item)

    popped = [queue.pop() for _ in range(100)]

    assert sorted(popped) == list(range(100))
    assert len(queue) == 0

  def test_pop_from_empty_queue_raises(self) -> None:
    """Raises when popping from an empty queue."""
    queue = RandomQueue[int]()

    with pytest.raises(ValueError, match='empty range'):
      queue.pop()
