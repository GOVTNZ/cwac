# Results

The tool places results in a new subdirectory of [./results](./results).

Any screenshots captured during the scan will be in the `screenshots/` subdirectory of the results.

When a scan is run with all audits enabled, the results directory also contains supporting files such as `config.json`, `chromedriver.log`, the main run log, and the `screenshots/` directory shown in the examples under [./results](./results).

## CSV columns

### Scan control files

| CSV file | Columns | Notes |
| --- | --- | --- |
| `audit_log.csv` | `organisation`, `base_url`, `url`, `sector` | Each row records a URL queued for scanning. |
| `pages_scanned.csv` | `organisation`, `base_url`, `number_of_pages`, `sector` | Each row records how many pages were scanned for a base URL. |
| `progress.csv` | `time`, `iteration`, `total`, `speed`, `percent`, `elapsed`, `remaining` | Each row records the current scan progress. |

### Audit result files

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

