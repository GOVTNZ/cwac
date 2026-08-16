# axe-core audit template aware results

Once scanning is complete, the [axe_core_audit.csv](./axe-core-audit.md) is used
to generate `axe_core_audit_template_aware.csv`

This CSV adds some metrics to make it easier for you to identify failures which
_might_ be part of a reusable template.

The template aware CSV makes the following changes from the standard axe-core
results:

1. The `num_issues` column now represents the total number of failures in the
   result-set that have the same value for `base_url`, `id`, `viewport_size`,
   and `html`.
1. A new `num_pages` column which represents how many other URLs had same type
   of axe-core failure as the current row.

> [!WARNING]
>
> The meaning of the `num_issues` column is different in `axe_core_audit.csv`
> and `axe_core_audit_template_aware.csv`.

## Interpreting `num_issues`

The goal of this value is to help you find issues that appear in templates which
might be re-used across your site e.g. a common header or footer. Fixing these
issues is high impact because it fixes them on every page the template is used
on.

`num_issues` is our best guess at which issues seem likely to be from a
template. We cannot know this perfectly because CWAC does not know the
underlying structure of your site

For the row you are looking at, `num_issues` is the total number of failures in
the result-set that have the same value for `base_url`, `id`, `viewport_size`,
and `html`.

Higher values of `num_issues` indicate that the chunk of HTML had the same
axe-core failure across multiple URLs.

## Interpreting `num_pages`

The goal of `num_pages` is to give you a sense of which kinds of accessibility
issue are the most common across the scanned pages.

For the row you are looking at, the `num_pages` value is the total number of
URLs in the result-set that had the same `id` value (same kind of Axe-core
failure).

For example if the current row has `id=image-alt` and `num_pages=12` then we
know that 12 scanned pages had an `image-alt` issue.

## Questions

possible improvements

- capture more than 100char of html

This is an attempt to highlight f Is this the right grouping for "same page"?
(base_url, id, html, viewport)

- Needs to be base_url not url because we want to compare across pages
- id is the issue id so needs to be there because it's the type of the failure
- html is the line that failed (or 100 chars of)
- viewport ???
  - means that if the same failure happens at both viewports then it won't be
    double counted
  - necessary because axe_core_audit is not one row per failure
  - but we will still double count eh? - both viewports will be included, just
    not grouped?

why html not target? when would html be the same but target would not? if html
is the same but target is not then is it the same element? the idea is that
footer.php could be inserted in different places so might not always be same
target the downside is that if the same html appears in multiple lines it will
be counted as a dupe when it shouldn't be Should target maybe be part of this?
