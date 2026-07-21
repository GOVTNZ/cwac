# Understanding the focus indicator audit

## Overview

This audit tests [WCAG 2.4.11 Focus Appearance](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html) (and the related [WCAG 2.4.7 Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)). It simulates a keyboard user navigating the page by pressing Tab and uses pixel-level screenshot comparison (via OpenCV) to detect whether each focused element produces a visible change on screen. If pressing Tab causes no pixels to change, the focused element has no visible focus indicator.

> [!WARNING]
>
> This test detects the complete absence of a focus indicator — it does not assess whether the focus indicator meets the size, contrast, or area requirements of [WCAG 2.4.11](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html). Manual testing is required to verify those aspects.

If the focus indicator audit was enabled for a scan, its results will be in the `focus_indicator_audit.csv` file in the results.


## Required configuration

The focus indicator audit requires the following scan configuration:

- `headless` must be set to `true`. This is required because screenshot-based comparison does not work reliably in a visible browser window.

The following optional settings are available under `audit_plugins.focus_indicator_audit` in the config:

- `root_element_css_selector` — CSS selector for the element that Tab key presses are sent to. Defaults to `body`.
- `pre_tab_key_presses` — Number of Tab presses to perform before the audit begins, to skip past any skip-navigation links or banners.
- `max_tab_key_presses` — Maximum number of Tab presses to perform during the audit.

## How the audit works

1. Expand the browser window to the full page height to prevent scrolling from affecting the screenshots.
2. Wait for any page animations to finish (up to 15 seconds) by comparing successive screenshots. If the page never stops animating, the audit reports a potential [WCAG 2.2.2 (Pause, Stop, Hide)](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) failure instead.
3. Take a reference screenshot of the page.
4. Optionally press Tab a configurable number of times to move past initial elements (e.g. skip links).
5. Repeatedly press Tab (up to `max_tab_key_presses` times). After each press:
	 a. Take a new screenshot.
	 b. Compare it to the reference screenshot pixel-by-pixel.
	 c. If zero pixels changed, the focused element has no visible focus indicator — record the element's HTML and which Tab press number triggered it.
	 d. Update the reference screenshot for the next iteration.
6. If focus leaves the page (address bar focused), stop early.
7. Return one result row per missing focus indicator found, or a single pass row if all Tab presses produced a visible change.

## Interpreting the report spreadsheet

The important columns in the CSV are:

- `num_issues`
	- `0` — all Tab presses produced a visible focus indicator.
	- `1` — this row represents a Tab press with no visible focus indicator.
- `description`
	- A human-readable summary, e.g. `Tab key press #3 did not show a focus indicator`.
	- If the page never stopped animating, this will describe a potential [WCAG 2.2.2](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) failure instead.
- `html`
	- The `outerHTML` of the element that had focus when the missing indicator was detected (truncated to 100 characters).

## Fixing focus indicator issues

Focus indicator issues are controlled by the CSS stylesheets of the site.

- Ensure `:focus` and `:focus-visible` pseudo-class styles are not removed (e.g. avoid `outline: none` without an alternative).
- Add a clearly visible focus style — a solid outline with sufficient colour contrast against its background is the most reliable approach.
- Review the [WCAG 2.4.11 Focus Appearance understanding document](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html) for the full normative requirements.
