"""URL helpers."""

import re

import ada_url


def normalize_url(url: str) -> str:
  """Normalize a URL so that equivalent URLs are represented by the same string.

  URLs are normalized per the WHATWG URL Standard (the same as browsers), which
  includes lowercasing the scheme and host, converting internationalized domain
  names to punycode, removing default ports, percent-encoding special characters,
  and resolving dot segments.

  Additionally, percent-escapes in the path are uppercased (as recommended by
  RFC 3986), since the WHATWG URL Standard leaves them as they were written.

  The fragment (including an empty one, e.g. https://example.com/#) is also
  removed, since it is never sent to the server and so refers to the same
  document, matching the URL Standard's "exclude fragments" equality.

  E.g. HTTPS://Māori.NZ:443/a/../caf%c3%a9#top -> https://xn--mori-qsa.nz/caf%C3%A9

  Args:
      url (str): URL to normalize

  Returns:
      str: normalized URL

  Raises:
      ValueError: if the URL is not valid
  """
  parsed = ada_url.URL(url)
  parsed.pathname = re.sub(r'%[0-9a-fA-F]{2}', lambda m: m.group(0).upper(), parsed.pathname)
  parsed.hash = ''

  return parsed.href
