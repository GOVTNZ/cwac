"""Tests for URL helpers."""

import pytest

from src.urls import normalize_url


@pytest.mark.parametrize(
  ('url', 'expected'),
  [
    # missing or extra slashes after the scheme
    pytest.param('https:example.com', 'https://example.com/', id='missing slashes after the scheme'),
    pytest.param('https:////example.com/', 'https://example.com/', id='extra slashes after the scheme'),
    # case of the scheme and host
    pytest.param('HTTPS://Example.COM/', 'https://example.com/', id='case of the scheme and host'),
    # escapes in the host
    pytest.param('https://a%62c.com/', 'https://abc.com/', id='escapes in the host'),
    # non-ASCII hosts
    pytest.param('https://māori.nz/', 'https://xn--mori-qsa.nz/', id='non-ASCII host'),
    pytest.param('https://ｅｘａｍｐｌｅ.com/', 'https://example.com/', id='non-ASCII host mapped per UTS 46'),
    # IPv4 hosts
    pytest.param('https://0x7f.1/', 'https://127.0.0.1/', id='IPv4 host not in dotted decimal'),
    pytest.param('https://127.0.0.1./', 'https://127.0.0.1/', id='IPv4 host with a trailing dot'),
    # IPv6 hosts
    pytest.param('https://[2001:DB8:0:0::1]/', 'https://[2001:db8::1]/', id='IPv6 host'),
    # default or empty port
    pytest.param('https://example.com:443/', 'https://example.com/', id='default https port'),
    pytest.param('http://example.com:80/', 'http://example.com/', id='default http port'),
    pytest.param('https://example.com:/', 'https://example.com/', id='empty port'),
    pytest.param('https://example.com:8080/', 'https://example.com:8080/', id='non-default port'),
    # empty path
    pytest.param('https://example.com', 'https://example.com/', id='empty path'),
    # fragment
    pytest.param('https://example.com/a#top', 'https://example.com/a', id='fragment'),
    pytest.param('https://example.com/a#', 'https://example.com/a', id='empty fragment'),
    # dot segments, which must always be resolved (including when escaped) to
    # prevent urls from being used to traverse outside of their base url
    pytest.param('https://example.com/a/../b/./c', 'https://example.com/b/c', id='dot segments'),
    pytest.param('https://example.com/a/%2e%2E/b/%2E/c', 'https://example.com/b/c', id='escaped dot segments'),
    pytest.param('https://example.com/a/.%2e/b/%2e./c', 'https://example.com/c', id='partly escaped dot segments'),
    pytest.param('https://example.com/a/b/%2e%2e', 'https://example.com/a/', id='trailing escaped dot segment'),
    pytest.param('https://example.com/a/file%2ehtml', 'https://example.com/a/file.html', id='escaped dot in a segment'),
    # backslashes
    pytest.param('https://example.com\\a\\b', 'https://example.com/a/b', id='backslash as a path separator'),
    # tabs, newlines, and leading or trailing spaces and control characters
    pytest.param('https://exa\tmple.com/a\nb', 'https://example.com/ab', id='tabs and newlines'),
    pytest.param(
      '\x00 https://example.com/ \x1f', 'https://example.com/', id='leading or trailing spaces and controls'
    ),
    # escaped unreserved characters
    pytest.param('https://example.com/%41%7e', 'https://example.com/A~', id='escaped unreserved in path'),
    pytest.param('https://example.com/?q=%41%7e', 'https://example.com/?q=A~', id='escaped unreserved in query'),
    pytest.param('https://example.com/a%zzb/100%', 'https://example.com/a%zzb/100%', id='bare %'),
    pytest.param('https://example.com/100%/%41%7e', 'https://example.com/100%/%41%7E', id='with a bare %'),
    pytest.param('https://example.com/%%341', 'https://example.com/%%341', id='forming an escape with a bare %'),
    # characters not allowed literally
    pytest.param('https://example.com/a b/café', 'https://example.com/a%20b/caf%C3%A9', id='not allowed in path'),
    pytest.param('https://example.com/?q=a b"<>', 'https://example.com/?q=a%20b%22%3C%3E', id='not allowed in query'),
    pytest.param('https://example.com/a|b', 'https://example.com/a%7Cb', id='pipe not allowed in path'),
    pytest.param(
      'https://example.com/?q=|^{}`',
      'https://example.com/?q=%7C%5E%7B%7D%60',
      id='other characters not allowed in query',
    ),
    # ' in the query
    pytest.param("https://example.com/?q='a'", 'https://example.com/?q=%27a%27', id="' in the query"),
    # case of hex digits in escapes
    pytest.param('https://example.com/caf%c3%a9', 'https://example.com/caf%C3%A9', id='hex case in path'),
    pytest.param('https://example.com/?q=%c3%a9', 'https://example.com/?q=%C3%A9', id='hex case in query'),
    pytest.param('https://us%c3%a9r@example.com/', 'https://us%C3%A9r@example.com/', id='hex case in userinfo'),
    # the example from the NormalizedUrl docs
    pytest.param(
      'HTTPS://Māori.NZ:443/a/../caf%c3%a9?q=1#top',
      'https://xn--mori-qsa.nz/caf%C3%A9?q=1',
      id='documented example',
    ),
  ],
)
def test_normalize_url_normalizes_aspects_that_do_not_affect_equality(url: str, expected: str) -> None:
  """Normalizes each aspect documented on NormalizedUrl as not affecting equality."""
  assert normalize_url(url) == expected
  assert normalize_url(expected) == expected


@pytest.mark.parametrize(
  ('url', 'other'),
  [
    # case of the path, query, and userinfo
    pytest.param('https://example.com/Path', 'https://example.com/path', id='case of the path'),
    pytest.param('https://example.com/?q=A', 'https://example.com/?q=a', id='case of the query'),
    pytest.param('https://User@example.com/', 'https://user@example.com/', id='case of the userinfo'),
    # reserved characters, escaped or not
    pytest.param('https://example.com/a%2Fb', 'https://example.com/a/b', id='escaped / in path'),
    pytest.param('https://example.com/?q=%2F', 'https://example.com/?q=/', id='escaped / in query'),
    pytest.param('https://example.com/?q=a+b', 'https://example.com/?q=a%20b', id='+ versus %20'),
    pytest.param('https://example.com/a,b+c', 'https://example.com/a%2Cb%2Bc', id='escaped sub-delims'),
    pytest.param('https://example.com/a//b', 'https://example.com/a/b', id='empty path segment'),
    # an empty query
    pytest.param('https://example.com/?', 'https://example.com/', id='empty query'),
    # a trailing dot in a domain host
    pytest.param('https://example.com./', 'https://example.com/', id='trailing dot in a domain host'),
  ],
)
def test_normalize_url_preserves_aspects_that_affect_equality(url: str, other: str) -> None:
  """Leaves each aspect documented on NormalizedUrl as affecting equality as is."""
  assert normalize_url(url) == url
  assert normalize_url(other) == other


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


@pytest.mark.parametrize(
  ('url', 'expected'),
  [
    ('https://example.com/a#', 'https://example.com/a'),
    ('https://example.com/a#top', 'https://example.com/a'),
    ('https://example.com/a?q=1#top', 'https://example.com/a?q=1'),
    ('https://example.com/#/route', 'https://example.com/'),
  ],
)
def test_normalize_url_removes_fragments(url: str, expected: str) -> None:
  """Removes the fragment, including an empty one, since it refers to the same document."""
  assert normalize_url(url) == expected


@pytest.mark.parametrize('url', ['', 'example.com', 'https://exa mple.com/', 'https://[::1/'])
def test_normalize_url_raises_on_invalid_url(url: str) -> None:
  """Raises a ValueError when the URL is not valid."""
  with pytest.raises(ValueError, match='Invalid input'):
    normalize_url(url)


@pytest.mark.parametrize(
  'url',
  [
    'ftp://example.com/',
    'ws://example.com/',
    'file:///tmp/a',
    'mailto:a@example.com',
    'javascript:void(0)',
    'foo://a/',
  ],
)
def test_normalize_url_raises_on_non_http_url(url: str) -> None:
  """Raises a ValueError when the URL does not use http(s)."""
  with pytest.raises(ValueError, match='Unsupported scheme'):
    normalize_url(url)
