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
`crawl_urls_from_sitemap` is `true`.

This option will be `true` by default as we think it is desirable most of the
time.

### Fetching the sitemap

Before crawling a particular `base_url`, we will attempt to request a sitemap
from the root of the domain, first checking for a gzipped version of the sitemap
(i.e. `/sitemap.xml.gz`) before checking for an uncompressed version (i.e.
`/sitemap.xml`).

i.e. if the `base_url` is `https://ackama.com/projects`, then we will look for
`https://ackama.com/sitemap.xml.gz`, and then `https://ackama.com/sitemap.xml`.

For `/sitemap.xml.gz`, if we receive a 200 response with a `Content-Type`
indicating gzipped content (i.e. `application/x-gzip`, `application/gzip`), we
will decode the content and attempt to parse it as XML. If that is successful,
we will consider it a valid sitemap and attempt to convert it to a set of urls,
or otherwise move on to trying `/sitemap.xml`.

For `/sitemap.xml`, if we receive a 200 response with a `Content-Type`
indicating XML content (i.e. `text/xml`), we will consider it a valid sitemap,
and attempt to convert it to a set of urls.

If we receive a redirect response for these requests, we will follow that
redirect.

These fetches will not be considered towards the `max_links_per_domain` limit.

### Converting a sitemap to a set of URLs

We will parse XML sitemaps per the
[sitemap protocol](https://www.sitemaps.org/protocol.html).

#### `urlset` sitemaps

If the sitemap is a `urlset`, we will iterate over each `url` and push their
`loc` value into the queue of urls to be processed for the `base_url`.

Any other properties will be ignored.

For example given this sitemap:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.example.com/</loc>
    <lastmod>2005-01-01</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>

  <url>
    <loc>https://www.example.com/catalog?item=12&amp;desc=vacation_hawaii</loc>
    <changefreq>weekly</changefreq>
  </url>

  <url>
    <loc>https://www.example.com/catalog?item=73&amp;desc=vacation_new_zealand</loc>
    <lastmod>2004-12-23</lastmod>
    <changefreq>weekly</changefreq>
  </url>

  <url>
    <loc>https://www.example.com/catalog?item=74&amp;desc=vacation_newfoundland</loc>
    <lastmod>2004-12-23T18:00:15+00:00</lastmod>
    <priority>0.3</priority>
  </url>

  <url>
    <loc>https://www.example.com/catalog?item=83&amp;desc=vacation_usa</loc>
    <lastmod>2004-11-23</lastmod>
  </url>
</urlset>
```

We would "crawl" the following:

- https://www.example.com/
- https://www.example.com/catalog?item=12&amp;desc=vacation_hawaii
- https://www.example.com/catalog?item=73&amp;desc=vacation_new_zealand
- https://www.example.com/catalog?item=74&amp;desc=vacation_newfoundland
- https://www.example.com/catalog?item=83&amp;desc=vacation_usa

#### `sitemapindex` sitemaps

If the sitemap is a `sitemapindex`, we will iterate over each `sitemap`, fetch
the sitemap pointed to by their `loc`, and then process them accordingly.

Any other properties will be ignored.

These fetches will not be considered towards the `max_links_per_domain` limit.

For example given this sitemap:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <sitemap>
      <loc>https://www.example.com/sitemap1.xml.gz</loc>
      <lastmod>2004-10-01T18:23:17+00:00</lastmod>
   </sitemap>

   <sitemap>
      <loc>https://www.example.com/sitemap2.xml.gz</loc>
      <lastmod>2005-01-01</lastmod>
   </sitemap>
</sitemapindex>
```

We would process the following sitemaps:

- https://www.example.com/sitemap1.xml.gz
- https://www.example.com/sitemap2.xml.gz

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
