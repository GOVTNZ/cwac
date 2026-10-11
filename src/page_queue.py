"""A queue of urls to be crawled."""

import random
import typing


class QueuedPage(typing.NamedTuple):
  """A url to be crawled, along with the url of the page it was found on."""

  parent_url: str
  url: str


class PageQueue:
  """A queue of urls that pops in random order, skipping urls that have already been seen or are not http(s)."""

  def __init__(self) -> None:
    """Initialise the queue."""
    self.items: list[QueuedPage] = []
    self.seen = set[str]()

  def __len__(self) -> int:
    """Return the number of items in the queue."""
    return len(self.items)

  def __str__(self) -> str:
    """Return the queue as a string."""
    return str(self.items)

  def push(self, item: QueuedPage) -> None:
    """Push an item onto the queue, unless its url has been pushed before or does not use the http(s) scheme.

    Args:
        item (QueuedPage): item to push onto the queue
    """
    if item.url in self.seen or not item.url.lower().startswith(('https:', 'http:')):
      return

    self.items.append(item)
    self.seen.add(item.url)

  def pop(self) -> QueuedPage:
    """Pop a randomly picked item off the queue.

    Returns:
        QueuedPage: item popped off the queue

    Raises:
        ValueError: if the queue is empty
    """
    index = random.randrange(len(self.items))  # nosec # noqa: S311

    # swap the picked item with the last item, so that popping is fast
    self.items[index], self.items[-1] = self.items[-1], self.items[index]

    return self.items.pop()
