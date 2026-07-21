# Title audit

## Overview

This audit records the `<title>` element of each page visited during a scan. The results can be used to verify that all pages have a unique and descriptive title, supporting [WCAG 2.4.2 Page Titled](https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html).

> [!WARNING]
>
> This audit only records page titles — it does not automatically detect duplicate or missing titles. Reviewing the results for duplicates and empty values requires manual inspection of the output CSV.

If the title audit was enabled for a scan, its results will be in the `title_audit.csv` file in the results.

## Required configuration

The title audit has no special configuration requirements. It runs under the same conditions as any other audit plugin.

## How the audit works

1. Navigate to the page URL (if not already loaded).
2. Read the content of the `<title>` element.
3. Record the title along with standard page metadata (organisation, sector, base URL, URL, viewport size, audit ID, page ID).

## Interpreting the results spreadsheet

The important columns in the CSV are:

- `page_title`
  - The text content of the `<title>` element at the time of the audit.
  - An empty value indicates the page has no title.
  - Repeated values across different URLs indicate duplicate titles.

## Fixing title issues

Title issues are controlled by the HTML or CMS templates of the site.

- A missing title should be added to the page template so that every page has a `<title>` element.
- Duplicate titles should be made unique and descriptive, typically by including the page name alongside the site name (e.g. `"Contact Us | Acme Agency"`).
