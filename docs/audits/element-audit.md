# Understanding the element audit

## Overview

This audit searches for specific HTML elements on each page using a configurable CSS selector and returns the full HTML of each match. It can be used to detect the presence or absence of particular elements (e.g., skip links, language toggles, ARIA landmarks) or to audit their structure and attributes.

If the element audit was enabled for a scan, its results will be in the `element_audit.csv` file in the results.

## Severity rationale

This audit is a general-purpose detection tool and does not inherently report a WCAG failure. Its purpose is to gather data — for example, to verify that all pages include certain accessibility features like skip links or proper heading structures, which can then be manually reviewed.

## Required configuration

The element audit requires the following configuration:

- `target_element_css_selector` — A CSS selector to match the elements you want to detect. For example:
  - `a[href="#main-content"]` — detect skip links
  - `h1` — detect top-level headings
  - `[role="banner"]` — detect elements with a banner role
  - `img:not([alt])` — detect images without alt text

## How the audit works

1. Retrieve the page source HTML.
2. Parse it with BeautifulSoup (using the `lxml` parser).
3. Select all elements matching the configured CSS selector.
4. For each matching element:
   a. Extract its full HTML using `prettify()` (formatted with indentation).
   b. Create a result row combining the element HTML with standard page metadata.
5. Return one row per matching element, or an empty result set if no elements match.

## Interpreting the report spreadsheet

The important columns in the CSV are:

- `element_html`
  - The full prettified HTML of the matched element, including all child elements and attributes.
  - An empty result set indicates no elements matched the selector.

All other columns are standard metadata from the [DefaultAudit](../README.md#default-audit-columns):

- `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id`

## Example use cases

- **Skip links audit**: Use selector `a[href*="#main"]` to detect skip-to-content links.
- **Heading structure audit**: Use selector `h1, h2, h3, h4, h5, h6` to audit heading hierarchy.
- **Landmark regions audit**: Use selector `[role="main"], [role="navigation"], [role="contentinfo"]` to verify regions are present.
- **Image alt text audit**: Use selector `img[alt=""], img:not([alt])` to find images with missing or empty alt text.
- **Language selector audit**: Use selector `a[hreflang], select[lang]` to detect language-switching mechanisms.

## Fixing element issues

The fix depends on what elements you're looking for:

- **Missing elements**: Add the required HTML structure to your site template. For example, add a skip link to your `<header>` or add a `<main>` element around your page content.
- **Malformed elements**: Review the HTML output and adjust the element's attributes, content, or nesting to match accessibility best practices. For example, ensure all images have descriptive alt text or that headings follow a logical hierarchy.
