"""URL helpers."""

import re
import string
import urllib.parse
from typing import NewType, cast

import ada_url

NormalizedUrl = NewType('NormalizedUrl', str)
"""An http(s) URL in a canonical form, so two URLs are equal if and only if their strings are equal.

URLs are equal if the requests a browser would make for them (per the WHATWG
URL Standard) are equivalent (per RFC 3986 and RFC 9110). Equivalences that
depend on the server, such as `/abc` and `/abc/` (RFC 3986 §6.2.4), are not
normalized, and are left to callers.

These aspects do not affect equality, so are normalized as shown:

- missing or extra slashes after the scheme: `//` (e.g. `https://a/`, not `https:a` or `https:////a`)
- case of the scheme and host: lowercase
- escapes in the host: decoded (e.g. `abc.com`, not `a%62c.com`)
- non-ASCII hosts: punycode, mapped per UTS 46 (e.g. `xn--mori-qsa.nz`, not `māori.nz`)
- IPv4 hosts: dotted decimal, without a trailing dot (e.g. `127.0.0.1`, not `0x7f.1` or `127.0.0.1.`)
- IPv6 hosts: compressed (e.g. `[2001:db8::1]`, not `[2001:db8:0:0::1]`)
- default or empty port: removed (e.g. no `:443` for https)
- empty path: `/`
- fragment, even an empty one: removed, as it is never sent (e.g. no `#top` or `#`)
- dot segments, escaped or not: resolved (e.g. no `/../` or `/%2e%2e/`)
- `\\` as a path separator: `/`
- tabs and newlines anywhere, and leading or trailing spaces and control characters: removed
- escaped unreserved characters (`A-Z a-z 0-9 - . _ ~`): unescaped (e.g. `/A`, not `/%41`),
  unless the URL has a `%` that does not start an escape (e.g. `/100%/%41`)
- characters not allowed literally: escaped (e.g. `/caf%C3%A9`, not `/café`)
- `'` in the query: escaped (e.g. `?q=%27a%27`, not `?q='a'`)
- case of hex digits in escapes: uppercase (e.g. `%C3`, not `%c3`)

These aspects do affect equality, so are left as is:

- the case of the path, query, and userinfo
- reserved characters, escaped or not (e.g. `/a%2Fb` is not `/a/b`, and `+` is
  not `%20`)
- an empty query (e.g. `https://example.com/?` is not `https://example.com/`)
- a trailing dot in a domain host (e.g. `example.com.` is not `example.com`)

E.g. `https://xn--mori-qsa.nz/caf%C3%A9?q=1` is normalized, whereas
`HTTPS://Māori.NZ:443/a/../caf%c3%a9?q=1#top` is not.
"""


UNRESERVED_CHARACTERS = frozenset(string.ascii_letters + string.digits + '-._~')

# characters that RFC 3986 allows to appear literally, in addition to the
# unreserved characters (which are always allowed), plus "%" for escapes
ALLOWED_CHARACTERS = ":/?#[]@!$&'()*+,;=%"


def _normalize_escapes(url: str) -> str:
  """Normalize the escapes in a URL that has been parsed per the WHATWG URL Standard.

  This escapes characters that are not allowed literally, unescapes unreserved
  characters, and uppercases the hex digits of all other escapes.

  Unreserved characters are left escaped if the URL has a "%" that does not start
  an escape, since unescaping could create a new escape (e.g. `%%341` -> `%41`).
  """
  url = urllib.parse.quote(url, safe=ALLOWED_CHARACTERS)

  has_bare_percent = re.search(r'%(?![0-9a-fA-F]{2})', url) is not None

  def normalize_escape(match: re.Match[str]) -> str:
    char = chr(int(match.group(1), 16))

    if char in UNRESERVED_CHARACTERS and not has_bare_percent:
      return char

    return match.group(0).upper()

  return re.sub(r'%([0-9a-fA-F]{2})', normalize_escape, url)


def normalize_url(url: str) -> NormalizedUrl:
  """Normalize a URL so that equal URLs are represented by the same string.

  URLs are parsed per the WHATWG URL Standard (the same as browsers), and then
  their escapes are normalized per RFC 3986, since the WHATWG URL Standard
  leaves them mostly as they were written.

  The fragment is also removed, since it is never sent to the server.

  See `NormalizedUrl` for what a normalized URL looks like.

  Args:
      url (str): URL to normalize

  Returns:
      NormalizedUrl: normalized URL

  Raises:
      ValueError: if the URL is not valid, or does not use http(s)
  """
  parsed = ada_url.URL(url)

  if parsed.protocol not in ('http:', 'https:'):
    raise ValueError(f'Unsupported scheme: {parsed.protocol}')

  parsed.hash = ''

  return cast(NormalizedUrl, _normalize_escapes(parsed.href))
