# focus indicator audit

## Overview

This audit tests [WCAG 2.4.11 Focus Appearance](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html) (and the related [WCAG 2.4.7 Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)). It simulates a keyboard user navigating the page by pressing Tab and uses pixel-level screenshot comparison (via OpenCV) to detect whether each focused element produces a visible change on screen. If pressing Tab causes no pixels to change, the focused element has no visible focus indicator.

> [!WARNING]
>
> This test detects the complete absence of a focus indicator - it does not assess whether the focus indicator meets the size, contrast, or area requirements of [WCAG 2.4.11](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html). Manual testing is required to verify those aspects.

## Configuration

As with all audits, this audit is configured by the `audit_plugins` section in the JSON config.

```jsonc
// Truncated snippet from config/config_default.json
{
		"headless": true,
		"audit_plugins": {
				// ...
				"focus_indicator_audit": {
						"class_name": "FocusIndicatorAudit", // Dev use only - do not change this.
						"enabled": false,
						"root_element_css_selector": "main",
						"pre_tab_key_presses": 0,
						"max_tab_key_presses": 5
				}
				// ...
		}
		// ...
}
```

The focus indicator audit requires the following scan configuration:

- `headless` must be set to `true`. This is required because screenshot-based comparison does not work reliably in a visible browser window.

The following optional settings are available under `audit_plugins.focus_indicator_audit` in the config:

- `root_element_css_selector` - CSS selector for the element that Tab key presses are sent to. Defaults to `body`.
- `pre_tab_key_presses` - Number of Tab presses to perform before the audit begins, to skip past any skip-navigation links or banners.
- `max_tab_key_presses` - Maximum number of Tab presses to perform during the audit.

## How the audit works

1. Expand the browser window to the full page height to prevent scrolling from affecting the screenshots.
2. Wait for any page animations to finish (up to 15 seconds) by comparing successive screenshots. If the page never stops animating, the audit reports a potential [WCAG 2.2.2 (Pause, Stop, Hide)](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) failure instead.
3. Take a reference screenshot of the page.
4. Optionally press Tab a configurable number of times to move past initial elements (e.g. skip links).
5. Repeatedly press Tab (up to `max_tab_key_presses` times). After each press:
	 a. Take a new screenshot.
	 b. Compare it to the reference screenshot pixel-by-pixel.
	 c. If zero pixels changed, the focused element has no visible focus indicator - record the element's HTML and which Tab press number triggered it.
	 d. Update the reference screenshot for the next iteration.
6. If focus leaves the page (address bar focused), stop early.
7. Return one result row per missing focus indicator found, or a single pass row if all Tab presses produced a visible change.

## Interpreting results

If the focus indicator audit was enabled for a scan, its results will be in `focus_indicator_audit.csv` in the results.

### Report columns

The columns in `focus_indicator_audit.csv` include standard metadata fields plus focus-specific result fields:

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
	- `0` means all Tab presses produced a visible focus indicator.
	- `1` means this row represents a Tab press with no visible focus indicator.
- `description`
	- A human-readable summary, e.g. `Tab key press #3 did not show a focus indicator`.
	- If the page never stopped animating, this describes a potential [WCAG 2.2.2](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) failure instead.
- `html`
	- The `outerHTML` of the element that had focus when the missing indicator was detected (truncated to 100 characters).

## Replicating findings

To manually replicate a finding for a specific page:

1. Open the page in a browser at the same viewport size used by the scan (see `viewport_size` column).
2. Navigate with the keyboard Tab key in the same sequence as described by the report row.
3. Confirm whether focus moves but no visible focus indicator appears for the flagged element.
4. Inspect the focused element in DevTools and compare it with the reported `html` snippet.
5. If the audit reported an animation-related issue, verify whether the page has persistent or long-running motion that prevents screenshot stability.

## Fixing issues

Focus indicator issues are controlled by the CSS stylesheets of the site.

- Ensure `:focus` and `:focus-visible` pseudo-class styles are not removed (e.g. avoid `outline: none` without an alternative).
- Add a clearly visible focus style - a solid outline with sufficient colour contrast against its background is the most reliable approach.
- Review the [WCAG 2.4.11 Focus Appearance understanding document](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html) for the full normative requirements.

## More information

- [WCAG 2.4.11 Understanding Focus Appearance (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html)
- [WCAG 2.4.7 Understanding Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)
- [WCAG 2.2.2 Understanding Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html)
