# Audit config

CWAC is configured using a single JSON file. A [default configuration JSON file](../config/config_default.json) is provided which sets sensible defaults. CWAC will execute using the default config file as its configuration source unless you provide a custom config file on the command line. Custom configuration files must be located in the `./config/` directory.

```bash
# uses ./config/config_default.json
python cwac.py

# uses ./config/config_custom.json
python cwac.py config_custom.json

# NOTE: custom config files must always be in ./config
```

The available configuration options are described below. See
the [default configuration JSON file](../config/config_default.json) for an example.

- `audit_name`
  - a name for the test, which is used as a folder name to store results inside of /results
- `headless`
  - a boolean that specifies whether the browsers will be headless, or not (browser windows will be invisible)
- `max_links_per_domain`
  - the maximum number of pages that will be tested for each URL specified in `base_urls_visit_path`
  - if set to 1 then pages will just be visited without any crawling for additional links
- `thread_count`
  - the number of browsers, and threads CWAC will use
  - a number equal to the number of CPU cores is most efficient
- `browser`
  - specifies what web browser is used for tests
  - can be either "chrome" or "firefox"
- `chrome_binary_location`
  - a valid path to a Chrome for Testing executable
  - if set to `auto`, CWAC will attempt to determine the path based on your OS and architecture
- `chrome_driver_location`
  - a valid path to a `chromedriver` executable (version must match the version of Chrome for Testing)
  - if set to `auto`, CWAC will attempt to determine the path based on your OS and architecture
- `user_agent`
  - the user agent string CWAC will use for all network requests
- `user_agent_product_token`
  - the product token (should match the one in `user_agent` used for robots.txt matching)
- `follow_robots_txt`
  - a bool, determines if robots.txt directives should be followed by CWAC
- `script_timeout`
  - the number of seconds before JavaScript execution will timeout
- `page_load_timeout`
  - the number of seconds before a page load will timeout
- `delay_between_page_loads`
  - delay amount (in seconds) that is used between visiting pages for each browser instance
  - if a Chrome instance hangs on a webpage, try increasing this value
- `delay_between_viewports`
  - if multiple viewport resolutions are specified in `viewport_sizes`, this is a delay (in seconds) between testing each viewport. It's useful to ensure the browser has re-rendered the content at the new viewport size
- `delay_after_page_load`
  - once the browser has loaded the page, this is a delay (in seconds) before running tests. This is helpful to allow any animations of JavaScript-based page changes to occur before running tests which may cause false positives i.e. fade-in animations can cause colour contrast false positives.
- `only_allow_https`
  - a boolean value that determines if CWAC will restrict to HTTPS-only URLs (true: restrict to HTTPS)
- `perform_header_check`
  - a boolean value that determines if CWAC will send a header-only request to each URL before loading the URL in a browser. This can prevent Chrome from loading garbage URLs, but it also slows down the crawler, and increases network requests.
- `shuffle_base_urls`
  - before CWAC starts scanning websites, it will randomly shuffle the order of URLs it will scan
- `base_urls_visit_path`
  - Defines which URLs will be scanned
  - a path to a folder that contains CSV files (as many as you like). The CSV files **must** have the headers: organisation,url,sector.
  - The entries in `base_urls_visit_path` are extremely important, as these files are used to associate URLs with other information like their organisation, and sector
- `base_urls_nohead_path`
  - Defines which URLs don't support HEAD requests
  - a path to a folder that contains CSV files (as many as you like). The CSV files **must** have only one header: url.
  - In cases where a HEAD request would be made CWAC will instead make a GET request
- `force_open_details_elements`
  - a boolean value that controls if `<details>` are explicitly marked as `open` before auditing
- `filter_to_organisations`
  - a list of strings that can be used to restrict a CWAC scan to particular organisations. The organisations are specified in CSVs within the `base_urls` folder
  - e.g. ["Ministry of Social Development", "Department of Internal Affairs"]
  - partial string matches are included, e.g. "Internal" would match "Department of Internal Affairs"
- `filter_to_urls`
  - a list of strings that can be used to restrict a CWAC scan to particular URLs. The URLs are specified in CSVs within the `base_urls` folder, and are only considered when parsing the CSVs
  - e.g. ["https://msd.govt.nz/", "https://dia.govt.nz"]
  - partial string matches are included e.g. "dia.govt" matches "https://dia.govt.nz"
- `viewport_sizes`
  - a JSON object specifying all viewport sizes CWAC will test each page with
  - Example: `{"small": {"width": 320, "height": 450}, "medium": {"width": 1280, "height": 450}}`
- `audit_plugins`
  - a dictionary of plugin configurations.
  - the key of each plugin entry must be a snake case file name that exists within `./src/audit_plugins/`
  - each plugin entry requires a camel case `class_name` as a value (equal to the class name in `./src/audit_plugins/[plugin_file].py`)
  - each plugin entry has an `enabled` boolean, which can be used to switch the plugin on and off
  - each plugin entry may have an optional `viewport_to_test` value, which can be used to restrict the plugin to run only at one viewport size that has been specified in `viewport_sizes` e.g. `viewport_to_test: "small"`
  - each plugin may have one or more custom properties that are passed to the plugin
