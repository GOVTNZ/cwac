# Audit guides

The available audits are documented below.

| Full guide | Purpose | Result CSV |
| --- | --- | --- |
| [Axe-core audit](audits/axe-core-audit.md) | Runs automated WCAG checks and reports rule violations, including optional best-practice findings. | `axe_core_audit.csv` and `axe_core_audit_template_aware.csv` |
| [Element audit](audits/element-audit.md) | Detects whether pages contain specific HTML elements or structures selected by a CSS selector. | `element_audit.csv` |
| [Focus indicator audit](audits/focus-indicator-audit.md) | Checks whether keyboard focus produces a visible on-screen indicator. | `focus_indicator_audit.csv` |
| [Language audit](audits/language-audit.md) | Measures readability and optional sentiment for English-language pages. | `language_audit.csv` |
| [Reflow audit](audits/reflow-audit.md) | Checks whether a page overflows horizontally at a 320px viewport. | `reflow_audit.csv` |
| [Screenshot audit](audits/screenshot-audit.md) | Captures a screenshot of each scanned page for visual review. | `screenshot_audit.csv` |
| [Title audit](audits/title-audit.md) | Records each page's `<title>` element for manual review of uniqueness and clarity. | `title_audit.csv` |
