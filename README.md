# Centralised Web Accessibility Checker (CWAC) 🦆

![CWAC](/icons/logo.svg)

CWAC is a project originally designed and developed by the Web Standards team within the Digital Public Service branch of <span lang="mi">Te Tari Taiwhenua</span> | Department of Internal Affairs, New Zealand Government.

**Note:** "CWAC" is pronounced "quack", like a duck.

CWAC is a tool that can scan hundreds of websites for accessibility issues, automatically.

CWAC can be used as a mechanism to monitor the New Zealand Government's implementation of minimum accessibility standards and guidelines on its websites. The primary standard, is the [NZ Government Web Accessibility Standard](https://www.digital.govt.nz/standards-and-guidance/nz-government-web-standards/web-accessibility-standard-1-1/), which includes [Web Content Accessibility Guidelines (WCAG) 2.1](https://www.w3.org/TR/WCAG21/) Level AA conformance. CWAC enables the partial fulfillment of [Article 9 of the United Nations Convention on the Rights of Persons with Disabilities (CRPD)](https://www.un.org/development/desa/disabilities/convention-on-the-rights-of-persons-with-disabilities/article-9-accessibility.html).

Provided a list of URLs, CWAC automatically crawls a specified number of pages per URL, and checks each page for automatically-identifiable accessibility issues. It then stores results in an easy-to-read CSV file.

CWAC can also crawl an explicitly-defined set of URLs without a crawler, which is useful for re-running tests to see changes in accessibility conformance over time.

CWAC is designed to be extensible, so new forms of web testing can be added over time. For instance, CWAC could also run [The Nu Html Checker](https://github.com/validator) on web pages. Or, it could theoretically check other website requirements, such as website data usage and performance, or the existence of a privacy or copyright statement.

## Core technologies

CWAC combines the following technologies:
- [Python 3](https://www.python.org/) (the primary scripting language CWAC is written in)
- [Selenium](https://github.com/seleniumhq/selenium) (used to control web browsers)
- [axe-core](https://github.com/dequelabs/axe-core) (the accessibility rules engine)
- [Chrome for Testing](https://github.com/GoogleChromeLabs/chrome-for-testing) (main browser CWAC uses)

## Installation instructions

### Step 1: Ensure Python 3 is installed
Ensure you have Python 3.12 installed on your system.

### Step 2: Create a Python virtual environment
A Python virtual environment ensures that CWAC's dependencies aren't installed on your system's version of Python.
- In a terminal, `cd` to the `cwac` directory.
- Double-check you're using the right python environment - type `python --version` and ensure it's `Python 3.12.x`
- Run `python -m venv .venv`
- Run `source .venv/bin/activate`

### Step 3: Install Python libraries
- In a terminal, `cd` to the `cwac` directory.
- Run `pip install -r requirements.txt` to install all required Python libraries.

### Step 4: Setting up pre-commit hooks (OPTIONAL - this is for development purposes and contributing)
To set up CWAC for development, you must first install all required pre-commit hooks. This isn't necessary if you just want to run CWAC.
1. Open a shell
2. Run `pre-commit autoupdate`
3. Run `pre-commit install`

A series of linters, security checking, and formatting will occur at every git commit.

To run the pre-commit hooks at any time, run:
`pre-commit run --all-files`
This is useful for debugging why a pre-commit hook failed.

### Step 5: Install NPM packages
CWAC has three dependencies managed by NPM. These are:
- axe-core
- Readability
- Chrome for Testing

To get NPM, go here: https://nodejs.org/en/download/

1. In a shell, `cd` to the `cwac` root directory
2. run `npm install`

### Step 6: Setting up Chrome for Testing

Chrome for Testing is a specific version of Chrome used for testing purposes.

An instance of Chrome for Testing should be in the `cwac/chrome/` directory.

Depending on your OS/architecture, Chrome for Testing will have different folder names and executable paths.

You must specify the correct path to Chrome for Testing for CWAC to work within CWAC's configuration files.

To do this:
1. Look inside the `cwac/chrome/` directory. Note the folder name for the version of Chrome for Testing that was downloaded i.e. `mac_arm-114.0.5735.90`
2. Open `cwac/config/`. For every config file in this directory e.g. `config_default.json`, modify the value of `chrome_binary_location` so the correct binary path is specified. For example:
   - the value of `chrome_binary_location` for an ARM-based Mac could be: `./chrome/mac_arm-114.0.5735.90/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`
   - for Linux x64, the `chrome_binary_location` could be: `./chrome/linux-114.0.5735.90/chrome-linux64/chrome`

#### Updating Chrome for Testing (optional)
From time to time, it might make sense to update the version of Chrome for Testing that CWAC uses.

To do this:
1. Visit [Chrome for Testing - GitHub](https://github.com/GoogleChromeLabs/chrome-for-testing)
2. Open the API endpoint `last-known-good-versions-with-downloads.json` in a JSON viewer (Firefox has one built-in)
3. Find the entry for the latest stable version of Chrome for Testing
4. Download the `chromedriver` that matches the version of Chrome for Testing you want to use
5. Place the `chromedriver` executable into the `/drivers/` folder in `cwac`, with a unique filename
6. Open `package.json` and change the Chrome for Testing version number, ensuring it matches the `chromedriver` version
7. Run `npm install` to install the newly specified version of Chrome for Testing in `package.json`
8. Modify the CWAC configuration file i.e. `/config/config_default.json` and ensure it specifies the correct `chrome_binary_location` and `chrome_driver_location`
9. Note: the `chromedriver` executable may need to have `chmod +x` run on it in order to give it execution permissions
10. macOS might come up with an error stating "chromedriver_mac_arm64” can’t be opened because Apple cannot check it for malicious software.". This is fixed by running `xattr -d com.apple.quarantine <name-of-executable>`

## Troubleshooting

### If you get nltk certificate errors

On macOS, `urllib` may fail when attempting to fetch data for `nltk`, with certificate errors. To fix this, go to `/Applications/Python 3.x.x/Install Certificates.command`. This file should install the necessary certificates and resolve the error.

### macOS security error
If you run CWAC and get the error "“chromedriver_mac_arm64” can’t be opened because Apple cannot check it for malicious software.":

Run: `xattr -d com.apple.quarantine <name-of-executable>`


## Usage instructions

### Configuration files
CWAC uses JSON files within the `./config` directory for its configuration. Before running a test, ensure that these files contain the settings that you want to use.

#### `./config/config_default.json`
This file contains the configuration settings for new tests run using CWAC. The values in this file can be manually modified to change the way CWAC runs its tests.

Field descriptions:
- `audit_name`
  - a name for the test, which is used as a folder name to store results inside of /results
- `headless`
  - a boolean that specifies whether the browsers will be headless, or not (browser windows will be invisible)
- `max_links_per_domain`
  - the maximum number of pages that will be tested for each URL specified in `base_urls_crawl_path`
- `thread_count`
  - the number of browsers, and threads CWAC will use
  - a number equal to the number of CPU cores is most efficient
- `browser`
  - specifies what web browser is used for tests
  - can be either "chrome" or "firefox"
- `chrome_binary_location`
  - a valid path to a Chrome for Testing executable
- `chrome_driver_location`
  - a valid path to a `chromedriver` executable (version must match the version of Chrome for Testing)
- `user_agent`
  - the user agent string CWAC will use for all network requests
- `user_agent_product_token`
  - the product token (should match the one in `user_agnet` used for robots.txt matching)
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
- `nocrawl_mode`
  - a boolean value that can be used to switch off the crawling function
  - this causes CWAC to *only* scan explicitly-defined URLs within the CSV files located at `base_urls_nocrawl_path`
- `shuffle_base_urls`
  - before CWAC starts scanning websites, it will randomly shuffle the order of URLs it will scan
- `base_urls_crawl_path`
  - Defines which URLs will be scanned when `nocrawl_mode` is `false`
  - a path to a folder that contains CSV files (as many as you like). The CSV files **must** have the headers: organisation,url,sector.
  - The entries in `base_urls_crawl_path` are extremely important, as these files are used to associate URLs with other information like their organisation, and sector
- `base_urls_nocrawl_path`
  - Defines which URLs will be scanned when `nocrawl_mode` is `true`
  - a path to a folder that contains CSV files (as many as you like). The CSV files **must** have only one header: url.
  - CWAC will take the URL, and look it up within `base_urls_crawl_path` CSVs to determine the URL's organisation,sector automatically, otherwise 'Unknown' will be specified and a warning is put in the scan's log.
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
  - a list of strings of specific URLs to restrict a crawl to (these URLs *must* be specified within a CSV inside of `base_urls_crawl_path` or `base_urls_nocrawl_path`)
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

### Running CWAC

First, ensure you're in the `cwac` directory and using the Python virtual environment created earlier:
- `cd` to the `cwac` folder
- ensure the terminal prompt starts with `(.venv)`
- if it doesn't, run the command `source .venv/bin/activate`

Once the configuration files are set up, CWAC can be run by executing:
```
python cwac.py
```

CWAC will execute using `./config/config_default.json` as its configuration source, which by default works for macOS.

CWAC also supports specifying configuration file names as a singular command line argument. Configuration files must be located in the `./config/` directory.

To specify a config file for CWAC:
```
python cwac.py config_custom.json
```

This will cause CWAC to load `./config/config_custom.json` instead of `config_default.json`.

If you want to run CWAC on Linux, this can be done easily by using the pre-built config for Linux: 
```
python cwac.py config_linux.json
```

This feature can be useful if you want to chain, or concurrently run instances of CWAC with different configurations e.g. different viewports, different tests, different organisations, etc.

To chain two instances of CWAC where one test will run after the other in sequence, use:
```
python cwac.py config_a.json && python cwac.py config_b.json
```

### Results storage
The raw test results are stored within the `./results/` folder.

### Exporting reports from the raw data
You can either use the raw data stored in teh `./results/` folder directly, or you can use a data exporting feature which auto-generates leaderboards, and runs an algorithm which attempts to de-duplicate axe-core issues.

The CWAC data exporter is in the file `export_report_data.py`, and its configuration is in `export_report_data_config.json`.

To use the CWAC data exporter, first modify `export_report_data_config.json` to specify where it should import data from within the `./results/` folder. Set `input_results_folder_name` to a valid folder name found within `./results/`. Then, set `output_report_name` to specify the name of the output folder that will be generated within `./reports/`.

You can then run `export_report_data.py` and it will generate various leaderboard CSVs etc and the output will be placed within `./reports/{output_folder_name}/`.

## Checking CWAC's source code

CWAC uses several tools to maintain the quality and integrity of its source code, including:
- [black](https://github.com/psf/black), an uncompromising code formatter
- [pydocstyle](https://github.com/PyCQA/pydocstyle), for linting docstrings
- [isort](https://github.com/pycqa/isort), for sorting import statements
- [bandit](https://github.com/PyCQA/bandit), for detecting potential security vulnerabilities
- [flake8](https://github.com/pycqa/flake8), for linting
- [pylint](https://github.com/PyCQA/pylint), for linting
- [mypy](https://github.com/python/mypy), for static type checking


Use `pre-commit run --all-files` to run all pre-commit hooks.


## Audit plugin architecture
CWAC is designed to be extensible with plugins. This enables CWAC to run multiple different types of audits against web pages.

By default, CWAC has 6 plugins:
- `DefaultAudit` - a plugin that simply gets basic page information e.g. viewport size, page title. This audit plugin is never used directly, it is always imported by other plugins so they don't have to fetch basic page information.
- `AxeCoreAudit` - a plugin that runs `axe-core` on the page
- `LanguageAudit` - a plugin that estimates text readability using a Flesch-Kincaid and SMOG score. It can also perform sentiment analysis.
- `ReflowAudit` - a plugin that gives an indicative test for WCAG 1.4.10 Reflow
- `FocusIndicatorAudit` - a plugin that presses the tab key and detects if pixels changed after pressing tab, which can be an indicative test for WCAG 2.4.7 Focus Visible.
- `ScreenshotAudit` - a plugin that simply takes screenshots of each web page tested and saves it to a folder in the results directory.
- `ElementAudit` - a plugin that reports all instances of elements that match a CSS selector.

The code for each plugin is located in `/src/audit_plugins/`

To specify what audits run during testing, modify the `audit_plugin` dictionary in `config_default.json`.
The format of `audit_plugin` entries requires a snake case name as the key, and a camel case name as the value for the 'class_name' property, e.g.:
```
"audit_plugins": {
    "axe_core_audit": {
        "class_name": "AxeCoreAudit",
        "best-practice": true,
        "enabled": true
    },
    "language_audit": {
        "class_name": "LanguageAudit",
        "enabled": true,
        "viewport_to_test": "small",
        "run_sentiment_analysis": false
    },
    "reflow_audit": {
        "class_name": "ReflowAudit",
        "enabled": true,
        "viewport_to_test": "small",
        "screenshot_failures": false
    },
    "screenshot_audit": {
        "class_name": "ScreenshotAudit",
        "enabled": true,
        "viewport_to_test": "small"
    },
    "focus_indicator_audit": {
        "class_name": "FocusIndicatorAudit",
        "enabled": true,
        "max_tab_key_presses": 15
    },
    "element_audit": {
        "class_name": "ElementAudit",
        "target_element_css_selector": "input:not([type="search"])",
        "enabled": true
    }
}
```

This is because the key corresponds to a module name within `./src/audit_plugins/`, and the camel case name corresponds to the audit class name contained in each module.

To add new audit plugins, first develop an appropriate test module/class within `./src/audit_plugins/`, and then enable that audit plugin by adding an entry within `config_default.json`.

Each plugin can have an optional `viewport_to_test` item, which allows you to run a plugin only at particular viewport sizes, if multiple are being tested. The value of this key must match a value within the `viewport_sizes` option.

## Copyright of Centralised Web Accessibility Checker (CWAC)
Crown copyright (c) 2024, Department of Internal Affairs on behalf of the New Zealand Government.

This copyright, along with CWAC's GPL-3.0 license, does not extend to the third-party chromedriver binaries located in the `/drivers/` folder. Permission to re-use third party copyright material cannot be given by the Department of Internal Affairs.

## chromedriver binaries copyright and license
CWAC includes chromedriver binaries at `/drivers/`. chromedriver licenses can be found in the `/drivers/` folder.

```
// Copyright 2015 The Chromium Authors
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//    * Redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer.
//    * Redistributions in binary form must reproduce the above
// copyright notice, this list of conditions and the following disclaimer
// in the documentation and/or other materials provided with the
// distribution.
//    * Neither the name of Google LLC nor the names of its
// contributors may be used to endorse or promote products derived from
// this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
