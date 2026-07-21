# Screenshot audit

This "audit" saves a screenshot of each page visited as part of the scan. You can check the screenshots for any obvious rendering issues or use them to get more context on a page that failed one of the other audits.

## Required configuration

None.

## Interpreting the results

The results are in the `screenshot_audit.csv` file. The important columns in that file are:

- `viewport_size`
  - the dimensions of the browser window at the time of the screenshot
- `screenshot`
  - The filename of the screenshot in the `screenshots/` directory within the scan results.
