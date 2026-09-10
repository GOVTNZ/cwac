# [CWAC-327](https://ackama.atlassian.net/browse/CWAC-327): Make "organisation" and "sector" columns optional

## Background

We want to make it easier for developers to run scans, and ensure the
information in the results is useful.

Currently, the `base_urls/visit` CSVs follow this structure:

```csv
organisation,url,sector
demo,https://broken-workshop.dequelabs.com/,demo
demo,https://dequeuniversity.com/demo/dream,demo
demo,https://webtestingcourse.dequecloud.com/,demo
demo,https://dequeuniversity.com/demo/mars/,demo
```

The "organisation" and "sector" columns are required even though they're not
impactful for crawling and auditing, and are not meaningful in all use cases.

## Behaviours

### Parsing

We will remove the requirement that there be three columns in the
`base_urls/visit` CSVs, and instead enforce that there is a `url` column.

After parsing, we will ensure that all rows have the same columns to ensure they
can be written as CSVs.

### Filtering

We will leave the `filter_to_organisations` and `filter_to_urls` configuration
properties alone, since they will both continue to work.

We will ensure that the handling of `filter_to_organisations` accounts for the
column potentially not being present.

### Sorting

We will no longer use the "organisation" column or any other optional columns
when sorting in the template-aware CSV. This mirrors the other output CSVs which
are not sorted by any columns.

### Outputs

We will copy all columns that are present in the `base_urls` CSVs into our
output CSVs, including the `url`.

This will allow developers to add arbitrary columns, and preserve the
"organisation" and "sector" columns that some developers might be using.

## Questions

### What if a column is not present in all CSVs?

> [!NOTE]
>
> It was decided to go with Option 2

The `CSVWriter` will error if rows don't all have the same columns.

#### Option 1: reject if CSVs don't have the same columns

When processing the CSVs, we could raise an error if we found columns not
present in all CSVs.

Pros:

- Developers would receive immediate feedback

Cons:

- Wrappers of the tool (such as web applications) would have to account for this
- Developers would have to deal with this when attempting to mix-and-match URLs
  - this could be mitigated by applying `filters` before the column check, but
    that might make the logic more complicated

#### Option 2: include all columns in all rows

When processing the CSVs, we could identify all columns that are present, and
then ensure they are present with a blank value across all rows.

Pros:

- Wrappers of the tool (such as web applications) probably will have less to
  deal with
- Developers could more easily mix-and-match URLs

Cons:

- Ordering might be off at times?

### What should we do with the `filter_to_organisations` property?

> [!NOTE]
>
> It was decided to go with Option 1

With "organisation" becoming optional, this filter property is a bit awkward.

#### Option 1: do nothing

Pros:

- we don't have to worry about breaking existing configurations
- the filter will still continue to work if the column is present

Cons:

- no ways to filter by other columns

#### Option 2: replace with a more flexible `filters` feature

We could replace both `filter_to_organisations` and `filter_to_urls` with a
single `filters` object whose keys are column names.

Each value would be an array of strings, and any row whose column value is not
in the array would be skipped.

For example, given a configuration like this:

```json
{
  "filter_to_organisations": ["ACME"],
  "filter_to_urls": ["https://example.com"]
}
```

This would be changed to:

```json
{
  "filters": {
    "organisation": ["ACME"],
    "url": ["https://example.com"]
  }
}
```

Pros:

- not specific to the "organisations" column
- would reduce the total number of configuration properties by one

Cons:

- would break existing configurations

## Appendix
