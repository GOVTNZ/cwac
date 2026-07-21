# Reflow audit

## Overview

This audit tests [WCAG 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). For each URL included in the scan, the page is opened in a 320px wide browser window. If the page can be scrolled horizontally then the audit fails.

> [!WARNING]
>
> This test does not fully test the normative requirement of [WCAG 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). But, it does provide a good indication of whether the page is responsive. Manual testing is still required to ensure [WCAG 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) is met.

If the reflow audit was enabled for a scan, it's results will be in `reflow_audit.csv` file in the results.

## Severity rationale

A page which fails this audit is potentially confusing and annoying for users on small screens.

Reflow issues are classified as `TODO`.
TODO: rationale here
TODO: is 320 too small in 2026?

## Required configuration

The reflow audit requires the following scan configuration:

- `headless` must be set to `true`. This is required because of limitations in the underlying browser control technology (Selenium).
- if `screenshot_failures` is set to `true` then a screenshot will be recorded of each page that fails.

## How the audit works

1. Verify viewport is 320px wide.
2. Re-load the page.
3. Scroll to position x=100, y=0 using JS
4. Measure `window.scrollX;` using JS.
5. `window.scrollX` returns the number of pixels by which the document is currently scrolled horizontally. If scrollX is greater than 0 then the page is wider than the viewport so we report a failure.
6. Reset the scroll position on the page.

## Interpreting the report spreadsheet

The important columns in the CSV are:

- `overflows` (boolean true/false)
  - Indicates whether there an overflow issue with this URL
  - Issue exists if value is `TRUE`
- `overflow_amount_px`
  - How wide the hidden part of the page is at a 320px viewport size.

## Fixing reflow issues

Horizontal overflow is controlled by the CSS Stylesheets of the site.

If the reflow issue is isolated to a single page, it _may_ be possible to fix it by adjusting the content of just that page.
However in most cases, the issue needs to be addressed by updating the CSS stylesheets.
