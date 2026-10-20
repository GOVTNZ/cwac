"""A queue of urls to be crawled."""

import random
import typing

import src.urls


class DiscoveredPage(typing.NamedTuple):
  """A url that has not been normalized yet and might be queued to be crawled, along with the url of the page it was found on."""

  parent_url: str
  url: str


class QueuedPage(typing.NamedTuple):
  """A url to be crawled, along with the url of the page it was found on."""

  parent_url: str
  url: src.urls.NormalizedUrl


class PageQueue:
  """A queue of urls that pops in random order, skipping urls that are invalid, not http(s), or already seen."""

  def __init__(self) -> None:
    """Initialise the queue."""
    self.items: list[QueuedPage] = []
    self.seen = set[src.urls.NormalizedUrl]()

  def __len__(self) -> int:
    """Return the number of items in the queue."""
    return len(self.items)

  def __str__(self) -> str:
    """Return the queue as a string."""
    return str(self.items)

  def push(self, item: DiscoveredPage) -> None:
    """Push an item onto the queue with its url normalized.

    The item is skipped if its url is invalid, does not use the http(s) scheme,
    or has been pushed before.

    Args:
        item (DiscoveredPage): item to push onto the queue
    """
    try:
      url = src.urls.normalize_url(item.url)
    except ValueError:
      return

    if url in self.seen:
      return

    self.items.append(QueuedPage(item.parent_url, url))
    self.seen.add(url)

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
