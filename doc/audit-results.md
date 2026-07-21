# Audit Results

- [Audit Results](#audit-results)
  - [Accessibility findings from the audit](#accessibility-findings-from-the-audit)
  - [Screenshots](#screenshots)
  - [Scan logs](#scan-logs)
  - [Scan config](#scan-config)

Scan outputs are saved to a new subdirectory of `./results` using the naming scheme `./results/<scan-timestamp>/*`.

```bash
# example scan output
results/2026-07-14_13-53-12_5
          # Accessibility findings from the audits
          ├── axe_core_audit.csv
          ├── axe_core_audit_template_aware.csv
          ├── element_audit.csv
          ├── language_audit.csv
          ├── reflow_audit.csv
          ├── screenshot_audit.csv

          # accessory files for debugging
          ├── 2026-07-14_13-53-12_5.log
          ├── audit_log.csv
          ├── chromedriver.log
          ├── config.json
          ├── pages_scanned.csv
          ├── progress.csv

          # screenshots (if any)
          └── screenshots
              ├── 10_medium.png
              ├── 10_small.png
              ├── 11_medium.png
              ├── 11_small.png
              ...

```

## Accessibility findings from the audit

All audit results are stored as CSV files. These files contain the accessibility findings discovered by the scan.

> [!WARNING] All CSV files start with Byte-order Mark (BOM)
> All generated CSV files start with 3 hidden bytes called a [BOM marker](https://en.wikipedia.org/wiki/Byte_order_mark). The BOM allows MS Excel to choose the correct character set for the data and thereby avoid broken looking characters.
>
> Most software will automatically handle reading CSV files with a BOM but there are occasions where you may need to explicitly tell the software that the file starts with the BOM bytes.

| CSV file | Audit guide |
| --- | --- |
| `axe_core_audit.csv` | [Axe-core audit](audits/axe-core-audit.md) |
| `axe_core_audit_template_aware.csv` | [Axe-core audit](audits/axe-core-audit.md) |
| `element_audit.csv` | [Element audit](audits/element-audit.md) |
| `focus_indicator_audit.csv` | [Focus indicator audit](audits/focus-indicator-audit.md) |
| `language_audit.csv` | [Language audit](audits/language-audit.md) |
| `reflow_audit.csv` | [Reflow audit](audits/reflow-audit.md) |
| `screenshot_audit.csv` | [Screenshot audit](audits/screenshot-audit.md) |
| `title_audit.csv` | [Title audit](audits/title-audit.md) |

## Screenshots

If the scan generated any screenshots they are in `results/<scan-timestamp>/screenshots/`.

## Scan logs

The results of how the scan itself ran are captured across some CSV and regular log files. These files describe _how_ the scan ran. The audit result files (see above) capture _what_ the scan found. You can probably ignore these unless you are debugging issues with the scan itself.

| CSV file | Columns | Notes |
| --- | --- | --- |
| `audit_log.csv` | `organisation`, `base_url`, `url`, `sector` | Each row records a URL queued for scanning. |
| `pages_scanned.csv` | `organisation`, `base_url`, `number_of_pages`, `sector` | Each row records how many pages were scanned for a base URL. |
| `progress.csv` | `time`, `iteration`, `total`, `speed`, `percent`, `elapsed`, `remaining` | Each row records the current scan progress. |


| Log file | Format | Notes |
| --- | --- | --- |
| `<audit_name>.log` | Plain text log file | The main CWAC run log. It records the scan start time, configuration, enabled audit plugins, and runtime messages emitted while the scan is running. |
| `chromedriver.log` | Plain text log file | The ChromeDriver log. It records browser-driver startup, session creation, browser capabilities, and lower-level Selenium or ChromeDriver activity that is useful when debugging browser automation issues. |

## Scan config

The full configuration used for the scan is stored in `config.json`.
