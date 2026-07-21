# axe-core audit

## Overview

This audit uses the [axe-core](https://github.com/dequelabs/axe-core) automated accessibility testing engine to scan each page for WCAG violations and optional best-practice issues. axe-core performs static analysis on the DOM to detect a wide range of accessibility issues including colour contrast, heading structure, image alt text, form labelling, and more.

> [!WARNING]
>
> Automated testing cannot detect all accessibility issues. Many WCAG requirements require manual inspection. axe-core typically catches 30-40% of accessibility issues; the remainder must be found through manual testing, user testing, and code review.
>
> Issues reported by axe-core are automatically detectable failures of specific WCAG success criteria or best practices. However, automation has limits; absence of a finding does not mean the page passes WCAG.

## Configuration

As with all audits, this audit is configured by the `audit_plugins` section in the JSON config.

```jsonc
// Truncated snippet from config/config_default.json
{
    "audit_plugins": {
        // ...
        "axe_core_audit": {
            "enabled": true, // enable/disable the audit
            "class_name": "AxeCoreAudit", // Dev use only - do not change this.
            "best-practice": false
        },
        // ...
    }
    // ...
}
```

The axe-core audit has minimal configuration requirements:

- `best-practice` (boolean) — Whether to include best-practice rules in addition to WCAG rules. Best-practice rules flag issues that are not WCAG violations but are strong recommendations (e.g. missing landmarks, overly long page titles). Set to `true` to be more thorough, or `false` to focus only on WCAG.

## How the audit works

1. Load axe-core (from `node_modules/axe-core/axe.min.js`) into memory if not already cached.
2. Inject the axe-core library into the page and execute it asynchronously.
3. Configure axe-core to:
   a. Use XPath expressions to identify elements (for clarity in reports).
   b. Return only violations (skip passes and inapplicable results).
   c. Optionally include best-practice rules if enabled in config.
4. For each violation:
   a. For each affected node (DOM element instance):
      - Generate an issue ID hash based on base URL, rule ID, element HTML, and viewport size (ensures consistent IDs across scans).
      - Extract the rule description, impact level, help text, and element XPath.
      - Record the element's HTML (truncated to 100 characters for CSV readability).
5. If no violations are found, return a single "No issues found" row.
6. Return one row per affected element per violation.

## Interpreting results

If the axe-core audit was enabled for a scan, its results will be in 2 files in the results:

1. `axe_core_audit.csv` — contains all violations found during the scan.
2. `axe_core_audit_template_aware.csv` — a filtered version where violations appearing on multiple pages due to shared template/component code are de-duplicated. This file helps identify systemic issues that need to be fixed in templates rather than on individual pages.

### Report columns

The columns in `axe_core_audit.csv` are:

- `organisation`
  - Copied directly from the `organisation` column in the visits CSV documented in [Configuring CWAC](../audit-config.md).
- `sector`
  - Copied directly from the `sector` column in the visits CSV documented in [Configuring CWAC](../audit-config.md).
- `page_title`
  - The page `<title>` text captured by the browser for this URL.
- `base_url`
  - Copied directly from the `url` column in the visits CSV documented in [Configuring CWAC](../audit-config.md).
- `url`
  - The specific page URL that was audited.
- `viewport_size`
  - Browser viewport dimensions used for this audit row (stored as a width/height object string).
- `audit_id`
  - The audit run + viewport identifier (for example `1_small`).
- `page_id`
  - Sequential page identifier within the run.
- `audit_type`
  - The plugin that produced the row (`AxeCoreAudit`).
- `issue_id`
  - A hash uniquely identifying this issue instance (based on base URL, rule ID, element HTML, and viewport). Useful for tracking the same issue across multiple scans.
- `description`
  - A human-readable summary of the rule being tested.
- `target`
  - The XPath expression identifying the element with the issue on the page.
- `num_issues`
  - `0` means no issues found for this page/viewport row.
  - `1` means this row represents one violation instance.
- `help`
  - Short guidance text describing how to fix the issue.
- `helpUrl`
  - Link to detailed guidance for the rule.
- `id`
  - The axe-core rule ID (for example `color-contrast`, `link-name`, `aria-hidden-focus`).
- `impact`
  - The axe-core severity level: `critical`, `serious`, `moderate`, or `minor`.
- `html`
  - The opening HTML of the affected element, truncated to 100 characters for report readability.
- `tags`
  - Axe-core tags for the rule (for example WCAG mappings and `best-practice`).
- `best-practice`
  - `Yes` if this rule is a best-practice rule (not a strict WCAG requirement), `No` if it is a WCAG requirement.

## Replicating findings

To manually replicate a finding for a specific page:

1. Open the page in a browser at the same viewport size used by the scan (see `viewport_size` column)
2. Inspect the element using the `target` XPath from the report row. In Chrome you can use [JS console $x() function](https://developer.chrome.com/docs/devtools/console/utilities#xpath-function) to find the element on the page. For example:
    ```js
    // Chrome provides the $x() shortcut function in console to find an element
    // on the page using the XPath - see
    // https://developer.chrome.com/docs/devtools/console/utilities#xpath-function
    // Example: Open dev tools JS console and call $x() passing it the XPath
    // value from the spreadsheet.
    $x("//section[@id='e1891']/section/ul/li[2]/details/div/p[3]/a[2]")
    ```
3. Compare the element with the `html` snippet and rule `id`/`description` in the CSV.
4. Use the `help` and `helpUrl` guidance to confirm why the issue was flagged.
5. Re-run the axe-core audit and confirm whether the same `issue_id` appears. There are axe-core add-ons available for all the major browsers to help with this e.g. [axe DevTools for Chrome](https://chromewebstore.google.com/detail/axe-devtools-web-accessib/lhdoppojpmngadmnindnejefpokejbdd?pli=1)
## Fixing issues

The fix depends on the specific rule. The [axe-core rule descriptions](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md) links from the `id` value in the result (e.g. `aria-hidden-focus` to an informative page giving context on the issue e.g. [aria-hidden-focus](https://dequeuniversity.com/rules/axe/4.12/aria-hidden-focus?application=RuleDescription). This should provide enough context for a developer (or other technical person) to understand the issue and devise a fix suitable for the site in question.

## More information

- [axe-core repository](https://github.com/dequelabs/axe-core)
- [axe-core rule descriptions](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md) - start here to better understand a particular rule
