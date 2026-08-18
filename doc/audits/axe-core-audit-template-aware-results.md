# Highlighting findings which potentially have a common cause

Sometimes multiple axe-core accessibility findings can have a common cause e.g.
a shared template or a single CSS style. CWAC does not have enough information
to be certain about when issues have a common cause but we can compute some
metrics to help your analysis of this.

Once scanning is complete, the [axe_core_audit.csv](./axe-core-audit.md) is used
to generate `axe_core_audit_template_aware.csv`.

It makes the following changes from the standard axe-core results:

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

## Interpreting `num_pages`

The goal of `num_pages` is to give you a sense of which kinds of accessibility
issue are the most common across the scanned pages.

For the row you are looking at, the `num_pages` value is the total number of
URLs in the result-set that had the same `id` value (`id` is the type of
Axe-core failure).

For example if the current row has `id=image-alt` and `num_pages=12` then we
know that 12 scanned pages had an `image-alt` issue.
