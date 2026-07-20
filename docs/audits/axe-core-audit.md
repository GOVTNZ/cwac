# Understanding the axe-core audit

## Overview

This audit uses the [axe-core](https://github.com/dequelabs/axe-core) automated accessibility testing engine to scan each page for WCAG violations and optional best-practice issues. axe-core performs static analysis on the DOM to detect a wide range of accessibility issues including colour contrast, heading structure, image alt text, form labelling, and more.

> [!WARNING]
>
> Automated testing cannot detect all accessibility issues. Many WCAG requirements require manual inspection. axe-core typically catches 30-40% of accessibility issues; the remainder must be found through manual testing, user testing, and code review.

If the axe-core audit was enabled for a scan, its results will be in the `axe_core_audit.csv` and `axe_core_audit_template_aware.csv` files in the results.

## Severity rationale

Issues reported by axe-core are automatically detectable failures of specific WCAG success criteria or best practices. However, automation has limits; absence of a finding does not mean the page passes WCAG.

## Required configuration

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

## Interpreting the report spreadsheet

The important columns in the CSV are:

- `num_issues`
  - `0` — no issues found on this page.
  - `1` — this row represents a single violation instance.
- `id`
  - The axe-core rule ID (e.g. `color-contrast`, `missing-alt-text`, `empty-heading`). Consult axe-core's documentation for details.
- `description`
  - A human-readable summary of the rule being tested.
- `impact`
  - The severity of the issue if found: `critical`, `serious`, `moderate`, or `minor`. Typically correlates with WCAG level (A/AA/AAA) but not always.
- `target`
  - The XPath expression identifying the element(s) with the issue on the page.
- `html`
  - The opening tag of the affected element (truncated to 100 characters).
- `help` & `helpUrl`
  - Guidance on how to fix the issue, including links to WCAG understanding documents.
- `best-practice`
  - `Yes` if this rule is a best-practice rule (not a strict WCAG requirement), `No` if it is a WCAG requirement.
- `issue_id`
  - A hash uniquely identifying this issue instance (based on base URL, rule ID, element HTML, and viewport). Useful for tracking the same issue across multiple scans.

## Two CSV files

- `axe_core_audit.csv` — contains all violations found during the scan.
- `axe_core_audit_template_aware.csv` — a filtered version where violations appearing on multiple pages due to shared template/component code are de-duplicated. This file helps identify systemic issues that need to be fixed in templates rather than on individual pages.

## Fixing axe-core issues

The fix depends on the specific rule. Common issues include:

- **Colour contrast** (`color-contrast`): Increase the contrast ratio between text and background. Aim for at least 4.5:1 for normal text (WCAG AA).
- **Missing alt text** (`missing-alt-text`, `image-alt`): Add descriptive alt text to all images. Decorative images should have empty alt text (`alt=""`).
- **Empty headings** (`empty-heading`): Remove headings with no text content, or add text to clarify the heading purpose.
- **Missing form labels** (`label`, `form-field-multiple-labels`): Ensure every form input has an associated label, either via `<label>` element or ARIA attributes.
- **Landmarks** (best-practice): Add semantic landmarks (`<main>`, `<nav>`, `<header>`, `<footer>`) to structure your page.
- **Page title** (best-practice): Ensure every page has a unique, descriptive `<title>` element.

Consult the [axe-core rules documentation](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md) for a complete list of rules and detailed fix guidance.
