# Element audit

## Overview

Use this audit to check your pages for elements whose presence or absence indicates a potential accessibility issue.

This audit searches for specific HTML elements on each page using a configurable CSS selector and returns the full HTML of each match. It can be used to detect the presence or absence of particular elements (e.g. skip links, language toggles, ARIA landmarks) or to audit their structure and attributes.

Unlike rule-based audits such as axe-core, this audit does not decide whether a result is a pass or fail. It reports whatever matches your selector so you can inspect or post-process those elements.

## Configuration

As with all audits, this audit is configured by the `audit_plugins` section in the JSON config.

```jsonc
// Truncated snippet from config/config_default.json
{
    "audit_plugins": {
        // ...
        "element_audit": {
            "enabled": false, // enable/disable the audit
            "class_name": "ElementAudit", // Dev use only - do not change this.

            //
            "target_element_css_selector": "a[href=\"#main\"]"
        }
        // ...
    }
    // ...
}
```

The element audit requires the following configuration:

- `target_element_css_selector` (string) - A CSS selector to match the elements you want to detect.

For example:

- `a[href="#main-content"]` - detect skip links
- `h1` - detect top-level headings
- `[role="banner"]` - detect elements with a banner role
- `img:not([alt])` - detect images without alt text

## How the audit works

1. Retrieve the page source HTML.
2. Parse it with BeautifulSoup (using the `lxml` parser).
3. Select all elements matching the configured CSS selector.
4. For each matching element:
   a. Extract its full HTML using `prettify()` (formatted with indentation).
   b. Create a result row combining the element HTML with standard page metadata.
5. Return one row per matching element, or an empty result set if no elements match.

## Interpreting results

If the element audit was enabled for a scan, its results will be in `element_audit.csv` in the results.

### Report columns

The columns in `element_audit.csv` are:

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
- `element_html`
  - The full prettified HTML of the matched element, including all child elements and attributes.

An empty result set indicates no elements matched the selector.

The metadata columns above are standard fields from [DefaultAudit](../README.md#default-audit-columns).

## Replicating findings

To manually replicate a finding for a specific page:

1. Open the page in a browser at the same viewport size used by the scan (see `viewport_size` column).
2. Use the configured selector from `target_element_css_selector` in browser DevTools (Elements panel search or Console APIs such as `document.querySelectorAll(...)`).
3. Compare the matched element(s) with the `element_html` value in the CSV.
4. If needed, inspect attributes and structure in DevTools to confirm whether the element meets your audit intent.

## Fixing issues

The fix depends on what elements you're looking for:

- **Missing elements**: Add the required HTML structure to your site template. For example, add a skip link to your `<header>` or add a `<main>` element around your page content.
- **Malformed elements**: Review the HTML output and adjust the element's attributes, content, or nesting to match accessibility best practices. For example, ensure all images have descriptive alt text or that headings follow a logical hierarchy.

Common use cases:

- **Skip links audit**: Use selector `a[href*="#main"]` to detect skip-to-content links.
- **Heading structure audit**: Use selector `h1, h2, h3, h4, h5, h6` to audit heading hierarchy.
- **Landmark regions audit**: Use selector `[role="main"], [role="navigation"], [role="contentinfo"]` to verify regions are present.
- **Image alt text audit**: Use selector `img[alt=""], img:not([alt])` to find images with missing or empty alt text.
- **Language selector audit**: Use selector `a[hreflang], select[lang]` to detect language-switching mechanisms.

## More information

- [CSS selectors reference (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_selectors)
- [BeautifulSoup documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
