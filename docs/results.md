# Results

Scan outputs are saved to a new subdirectory of [./results](./results) using the naming scheme `./results/<scan-timestamp>/<scan-output-files>`. As well as the accessibility findings for the scanned URLs, the results directory contains supporting files from the scan itself e.g. `config.json`, `chromedriver.log`, the main run log, and the `screenshots/` directory.

The files in the results directory are in one of 2 categories:

1. Audit results - the accessibililty findings discovered by the scan.
2. Scan control results - details of the scanning process itself.

## Audit results

Audit results are stored as the following CSV files. These files contain the accessibility findings discovered by the scan.

| CSV file | Columns | Notes |
| --- | --- | --- |
| `axe_core_audit.csv` | `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id`, `audit_type`, `helpUrl`, `description`, `impact`, `target`, `html`, `help`, `best-practice`, `issue_id`, `num_issues` | Each row records one axe-core finding, or a single zero-issue row when no findings are detected. |
| `axe_core_audit_template_aware.csv` | Same as `axe_core_audit.csv`, plus `num_pages` | Shows how many pages share the same issue. |
| `element_audit.csv` | `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id`, `element_html` | Used by the element audit to record matching elements. |
| `element_audit.csv` | `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id`, `audit_type`, `helpUrl`, `description`, `html`, `num_issues` | Used by the focus indicator audit to record missing focus indicators and zero-issue pass rows. |
| `language_audit.csv` | `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id`, `flesch_kincaid_gl`, `smog_gl`, `num_sentences`, `words_per_sentence`, `syllables_per_word`, `sentiment_neg`, `sentiment_neu`, `sentiment_pos`, `sentiment_compound` | The sentiment columns are only present when sentiment analysis is enabled. |
| `reflow_audit.csv` | `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id`, `overflows`, `overflow_amount_px`, `num_issues` | Each row records whether the page overflowed horizontally at 320px. |
| `screenshot_audit.csv` | `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id`, `audit_type`, `screenshot` | Each row records the filename of the captured screenshot. |
| `title_audit.csv` | `organisation`, `sector`, `page_title`, `base_url`, `url`, `viewport_size`, `audit_id`, `page_id` | Each row records the page title for the scanned page. |

## Scan control results

The results of how the scan itself ran are captured across some CSV and regular log files.

### Scan control results: CSV files

These files describe _how_ the scan ran. The audit result files (see above) capture _what_ the scan found. You can probably ignore these unless you are debugging issues with the scan itself.

| CSV file | Columns | Notes |
| --- | --- | --- |
| `audit_log.csv` | `organisation`, `base_url`, `url`, `sector` | Each row records a URL queued for scanning. |
| `pages_scanned.csv` | `organisation`, `base_url`, `number_of_pages`, `sector` | Each row records how many pages were scanned for a base URL. |
| `progress.csv` | `time`, `iteration`, `total`, `speed`, `percent`, `elapsed`, `remaining` | Each row records the current scan progress. |

### Scan control results: Log files

The following log files are saved:

| Log file | Format | Notes |
| --- | --- | --- |
| `<audit_name>.log` | Plain text log file | The main CWAC run log. It records the scan start time, configuration, enabled audit plugins, and runtime messages emitted while the scan is running. |
| `chromedriver.log` | Plain text log file | The ChromeDriver log. It records browser-driver startup, session creation, browser capabilities, and lower-level Selenium or ChromeDriver activity that is useful when debugging browser automation issues. |

### Scan control results: Scan config

The full configuration used for the scan is captures in `config.json`.
