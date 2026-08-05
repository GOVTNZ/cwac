# [CWAC-313](https://ackama.atlassian.net/browse/CWAC-313): Support reading sitemaps via the tool

## Background

We want to add support for using sitemaps as part of crawling, because they let
us discover pages that are not reachable by following links alone, e.g. because
the site uses JS-based pagination, or they are only discoverable through
searching.

We want to focus on supporting XML based sitemaps as defined in the
[sitemaps protocol](https://www.sitemaps.org/protocol.html).

## Key Considerations

### When to use the sitemap

We will consider the sitemap when a configuration option such as
`crawl_sitemaps` is `true`.

This option will be `true` by default as we think it is desirable most of the
time.

### Fetching the sitemap

We will use the
[`ultimate-sitemap-parser`](https://ultimate-sitemap-parser.readthedocs.io/en/latest/get-started.html)
library, which looks like it does all the things we'd like including:

- locating sitemaps via `robots.txt`
- sitemaps compressed with gunzip (`.gz`)
- [various sitemap locations](https://ultimate-sitemap-parser.readthedocs.io/en/latest/reference/api/usp.tree.html#usp.tree._UNPUBLISHED_SITEMAP_PATHS)
- `sitemapindex`s

It also has a CLI for listing sitemaps locally, which can be useful for
debugging

### Ordering and filtering urls added from sitemaps

URLs sourced from sitemaps will be treated the same as those crawled from HTML
pages, including:

- being subject to the `max_links_per_domain` limit
- being run through the URL filters
- being checked against `robots.txt`
- being checked for support headers
- being scoped to the `base_url` to prevent intersections

## Open Considerations

### When to fetch the sitemap for urls

Fetching the sitemap should most likely happen in the `Crawler`, and should only
need to be done once per `base_url`.

The current process within `Crawler#crawl` is:

1. create a `RandomQueue` (`queue`) with the `base_url` as the only entry
2. while the `queue` is not empty:
   1. pop a random page url off the queue
   2. check that we want to audit that page, `continue`ing if not
      - including checking if we're reached the `max_links_per_domain` limit
   3. audit the page
   4. extract all links on the page, and push them into the queue

Since we only need to fetch the sitemap once, we could do this before step 2.
however since urls are popped off the queue at random, we risk not auditing the
`base_url` before reaching the `max_links_per_domain` limit, which might be
surprising.

An alternative could be to fetch the sitemap within the loop before step 4. _if_
the `queue` is empty, and we had not recorded any other urls as being `visited`
(or if only the `base_url` had been visited), as that would indicate we were in
the first iteration.

An advantage to this is we'd avoid fetching the sitemap if the `base_url` was
skipped for some reason, such as failing the header check.

### Inspecting `robots.txt` for sitemaps

It is common (but not required) for sites to specify the location of their
sitemap(s) in their `robots.txt` file with the `Sitemap` directive:

```text
Sitemap: https://www.example.com/sitemap.xml
```

The CWAC tool does already support interacting with `robots.txt` using the
built-in
[`urllib.robotparser`](https://docs.python.org/3/library/urllib.robotparser.html)
which does understand the `Sitemap` directive (via
[`site_maps()`](https://docs.python.org/3/library/urllib.robotparser.html#urllib.robotparser.RobotFileParser.site_maps)).

Using this could improve the tool when dealing with sitemaps:

- sites that did not provide a gzipped version of their sitemap: we would not
  need to make an initial request for the gzipped sitemap
- sites that used an alternative sitemap location, and had a redirect: we would
  not need to go through the redirect chain
- sites that used an alternative sitemap location, and did not have a redirect:
  we would be able to discover their sitemap

However, it is not clear how this should interact with cases such as where
`robots.txt` is unavailable or checking is disabled entirely (via the
`follow_robots_txt` option), so it may be best to explore this separately.
