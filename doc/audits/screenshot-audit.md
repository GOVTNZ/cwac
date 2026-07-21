# screenshot audit

## Overview

This "audit" saves a screenshot of each page visited as part of the scan. You
can check the screenshots for any obvious rendering issues or use them to get
more context on a page that failed one of the other audits.

This is an informational audit. It captures visual evidence but does not perform
pass/fail accessibility assertions by itself.

## Configuration

As with all audits, this audit is configured by the `audit_plugins` section in
the JSON config.

```jsonc
// Truncated snippet from config/config_default.json
{
  "audit_plugins": {
    // ...
    "screenshot_audit": {
      "class_name": "ScreenshotAudit", // Dev use only - do not change this.
      "enabled": false
    }
    // ...
  }
  // ...
}
```

The screenshot audit has no special configuration requirements beyond being
enabled.

## How the audit works

1. Visit each page URL in the scan.
2. Capture a screenshot at the active viewport size.
3. Save the screenshot file into the `screenshots/` directory for that scan
   result.
4. Record the screenshot filename and metadata in the CSV output.

## Interpreting results

If the screenshot audit was enabled for a scan, its results will be in
`screenshot_audit.csv` in the results.

### Report columns

The columns in `screenshot_audit.csv` include standard metadata fields plus
screenshot-specific fields:

- `organisation`
  - Copied directly from the `organisation` column in the visits CSV documented
    in [Configuring CWAC](../audit-config.md).
- `sector`
  - Copied directly from the `sector` column in the visits CSV documented in
    [Configuring CWAC](../audit-config.md).
- `page_title`
  - The page `<title>` text captured by the browser for this URL.
- `base_url`
  - Copied directly from the `url` column in the visits CSV documented in
    [Configuring CWAC](../audit-config.md).
- `url`
  - The specific page URL that was audited.
- `viewport_size`
  - The dimensions of the browser window at the time of the screenshot.
- `audit_id`
  - The audit run + viewport identifier (for example `1_small`).
- `page_id`
  - Sequential page identifier within the run.
- `screenshot`
  - The filename of the screenshot in the `screenshots/` directory within the
    scan results.

## Replicating findings

To manually replicate a finding for a specific page:

1. Open the page URL in a browser.
2. Set the viewport to match `viewport_size` from the CSV row.
3. Capture a screenshot and compare it to the image file named in the
   `screenshot` column.
4. Use this comparison to confirm rendering differences or to gather context
   around issues found by other audits.

## Fixing issues

This audit is informational - it facilitates manually checking for issues. It
does not produce a list of issues to fix.

- Use screenshots to identify visual defects such as clipping, overlap, missing
  UI states, or unexpected layout shifts.
- If visual problems are present, fix the underlying HTML, CSS, or client-side
  behavior on the affected page or shared template.

## More information

- [Web Content Accessibility Guidelines (WCAG) overview](https://www.w3.org/WAI/standards-guidelines/wcag/)
