# reflow audit

## Overview

This audit tests [WCAG 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). For each URL included in the scan, the page is opened in a 320px wide browser window. If the page can be scrolled horizontally then the audit fails.

> [!WARNING]
>
> This test does not fully test the normative requirement of [WCAG 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). But, it does provide a good indication of whether the page is responsive. Manual testing is still required to ensure [WCAG 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) is met.

## Configuration

As with all audits, this audit is configured by the `audit_plugins` section in the JSON config.

```jsonc
// Truncated snippet from config/config_default.json
{
  "headless": true,
  "audit_plugins": {
    // ...
    "reflow_audit": {
      "class_name": "ReflowAudit", // Dev use only - do not change this.
      "enabled": true,
      "viewport_to_test": "small",
      "screenshot_failures": false
    }
    // ...
  }
  // ...
}
```

The reflow audit requires the following scan configuration:

- `headless` must be set to `true`. This is required because of limitations in the underlying browser control technology (Selenium).
- If `screenshot_failures` is set to `true`, a screenshot will be recorded for each page that fails.

## How the audit works

1. Verify viewport is 320px wide.
2. Re-load the page.
3. Scroll to position x=100, y=0 using JS
4. Measure `window.scrollX;` using JS.
5. `window.scrollX` returns the number of pixels by which the document is currently scrolled horizontally. If scrollX is greater than 0 then the page is wider than the viewport so we report a failure.
6. Reset the scroll position on the page.

## Interpreting results

If the reflow audit was enabled for a scan, its results will be in `reflow_audit.csv` in the results.

### Report columns

The columns in `reflow_audit.csv` include standard metadata fields plus reflow-specific result fields:

- `organisation`
  - The organisation label from the input base URL list.
- `sector`
  - The sector label from the input base URL list.
- `page_title`
  - The page `<title>` text captured by the browser for this URL.
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
- `num_issues`
  - `0` means no horizontal overflow was detected.
  - `1` means horizontal overflow was detected for this row.
- `overflows` (boolean true/false)
  - Indicates whether there an overflow issue with this URL
  - Issue exists if value is `TRUE`
- `overflow_amount_px`
  - How wide the hidden part of the page is at a 320px viewport size.

## Replicating findings

To manually replicate a finding for a specific page:

1. Open the page in a browser and set the viewport width to 320px.
2. Scroll horizontally (or run `window.scrollTo(100, 0)` in DevTools console).
3. Check `window.scrollX` in DevTools console.
4. If `window.scrollX` is greater than 0 after horizontal scroll, the page overflows horizontally and likely fails this check.
5. Compare with `overflow_amount_px` and any related screenshot captured by `screenshot_failures`.

## Fixing reflow issues

Horizontal overflow is controlled by the CSS Stylesheets of the site.

If the reflow issue is isolated to a single page, it _may_ be possible to fix it by adjusting the content of just that page.
However in most cases, the issue needs to be addressed by updating the CSS stylesheets.

## More information

- [WCAG 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)
