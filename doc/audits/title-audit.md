# title audit

## Overview

This audit records the `<title>` element of each page visited during a scan. The results can be used to verify that all pages have a unique and descriptive title, supporting [WCAG 2.4.2 Page Titled](https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html).

> [!WARNING]
>
> This audit only records page titles — it does not automatically detect duplicate or missing titles. Reviewing the results for duplicates and empty values requires manual inspection of the output CSV.

## Configuration

As with all audits, this audit is configured by the `audit_plugins` section in the JSON config.

```jsonc
// Truncated snippet from config/config_default.json
{
  "audit_plugins": {
    // ...
    "title_audit": {
      "class_name": "TitleAudit", // Dev use only - do not change this.
      "enabled": true
    }
    // ...
  }
  // ...
}
```

The title audit has no special configuration requirements. It runs under the same conditions as any other audit plugin.

## How the audit works

1. Navigate to the page URL (if not already loaded).
2. Read the content of the `<title>` element.
3. Record the title along with standard page metadata (organisation, sector, base URL, URL, viewport size, audit ID, page ID).

## Interpreting results

If the title audit was enabled for a scan, its results will be in `title_audit.csv` in the results.

### Report columns

The columns in `title_audit.csv` include standard metadata fields plus title-specific result fields:

- `organisation`
  - The organisation label from the input base URL list.
- `sector`
  - The sector label from the input base URL list.
- `base_url`
  - The base site URL the page belongs to.
- `url`
  - The specific page URL that was audited.
- `viewport_size`
  - Browser viewport dimensions used for this audit row (stored as a width/height object string).
- `audit_id`
  - The audit run + viewport identifier (for example `1_small`).
- `page_id`
  - Sequential page identifier within the run.

- `page_title`
  - The text content of the `<title>` element at the time of the audit.
  - An empty value indicates the page has no title.
  - Repeated values across different URLs indicate duplicate titles.

## Replicating findings

To manually replicate a finding for a specific page:

1. Open the page URL in a browser.
2. Inspect the page title using either the browser tab label or DevTools (`document.title`).
3. Compare the value against the `page_title` value in `title_audit.csv`.
4. Check other rows for duplicate `page_title` values across different URLs.

## Fixing title issues

Title issues are controlled by the HTML or CMS templates of the site.

- A missing title should be added to the page template so that every page has a `<title>` element.
- Duplicate titles should be made unique and descriptive, typically by including the page name alongside the site name (e.g. `"Contact Us | Acme Agency"`).

## More information

- [WCAG 2.4.2 Page Titled](https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html)
