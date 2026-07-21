# Centralised Web Accessibility Checker (CWAC) 🦆

![CWAC](/icons/logo.svg)

- [Centralised Web Accessibility Checker (CWAC) 🦆](#centralised-web-accessibility-checker-cwac-)
  - [About CWAC](#about-cwac)
  - [Using CWAC](#using-cwac)
  - [Developing CWAC](#developing-cwac)
    - [Core technologies](#core-technologies)
    - [Linting source code](#linting-source-code)
    - [Setting up pre-commit hooks](#setting-up-pre-commit-hooks)
    - [Audit plugin architecture](#audit-plugin-architecture)
  - [Updating Chrome and Chromedriver versions](#updating-chrome-and-chromedriver-versions)
  - [Copyright notices](#copyright-notices)
    - [Copyright of Centralised Web Accessibility Checker (CWAC)](#copyright-of-centralised-web-accessibility-checker-cwac)
    - [chromedriver binaries copyright and license](#chromedriver-binaries-copyright-and-license)

## About CWAC

CWAC is designed and developed by the Web Standards team at <span lang="mi">Te Pūnaha Matihiko</span> | Government Digital Delivery Agency, New Zealand Government.

**Note:** "CWAC" is pronounced "quack", like a duck.

CWAC is a tool that can scan hundreds of websites for accessibility issues, automatically.

CWAC can be used as a mechanism to monitor the New Zealand Government's implementation of minimum accessibility standards and guidelines on its websites. The primary standard, is the [NZ Government Web Accessibility Standard](https://www.digital.govt.nz/standards-and-guidance/nz-government-web-standards/web-accessibility-standard-1-2/), which includes [Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/) Level AA conformance. CWAC enables the partial fulfillment of [Article 9 of the United Nations Convention on the Rights of Persons with Disabilities (CRPD)](https://www.un.org/development/desa/disabilities/convention-on-the-rights-of-persons-with-disabilities/article-9-accessibility.html).

Provided a list of URLS to visit, CWAC will check each page for automatically-identifiable accessibility issues and store the results in an easy-to-read CSV file.

CWAC can also crawl each page as it goes to determine additional pages to check (up to a set max number per URL), respecting `robots.txt` and server signals when doing so. This makes it easy to check entire sites without knowing the all paths beforehand.

CWAC is designed to be extensible, so new forms of web testing can be added over time. For instance, CWAC could also run [The Nu Html Checker](https://github.com/validator) on web pages. Or, it could theoretically check other website requirements, such as website data usage and performance, or the existence of a privacy or copyright statement.


## Using CWAC

- [Installing CWAC](./doc/install.md)
- [Understanding audits](./doc/audits.md)
- [Configuring audits](./doc/audit-config.md)
- [Running CWAC CLI](./doc/run-cwac.md)
- [Working with audit results](./doc/audit-results.md)

## Developing CWAC

### Core technologies

CWAC combines the following technologies:

- [Python 3](https://www.python.org/) (the primary scripting language CWAC is written in)
- [Selenium](https://github.com/seleniumhq/selenium) (used to control web browsers)
- [axe-core](https://github.com/dequelabs/axe-core) (the accessibility rules engine)
- [Chrome for Testing](https://github.com/GoogleChromeLabs/chrome-for-testing) (main browser CWAC uses)

### Linting source code

CWAC uses several tools to maintain the quality and integrity of its source code, including:

- [ruff](https://github.com/astral-sh/ruff), an uncompromising code formatter and linter
- [bandit](https://github.com/PyCQA/bandit), for detecting potential security vulnerabilities
- [flake8](https://github.com/pycqa/flake8), for linting
- [pylint](https://github.com/PyCQA/pylint), for linting
- [mypy](https://github.com/python/mypy), for static type checking

Use `pre-commit run --all-files` to run all pre-commit hooks.

### Setting up pre-commit hooks

To set up CWAC for development, you must first install all required pre-commit hooks. This isn't necessary if you just want to run CWAC.

1. Open a shell
2. Run `pre-commit autoupdate`
3. Run `pre-commit install`

A series of linters, security checking, and formatting will occur at every git commit.

To run the pre-commit hooks at any time, run:
`pre-commit run --all-files`
This is useful for debugging why a pre-commit hook failed.

### Audit plugin architecture

CWAC is designed to be extensible with plugins. This enables CWAC to run multiple different types of audits against web pages.

The available audit plugins are described in [Understanding audits](./doc/audits.md). The code for each plugin is located in `/src/audit_plugins/`

To specify which audits run during testing, modify the `audit_plugins` object in `./config/config_default.json`. The format of `audit_plugins` entries requires a snake case name as the key, and a camel case name as the value for the `class_name` property, e.g.:

```json
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
    "title_audit": {
        "class_name": "TitleAudit",
        "enabled": true
    },
    "screenshot_audit": {
        "class_name": "ScreenshotAudit",
        "enabled": true,
        "viewport_to_test": "small"
    },
    "focus_indicator_audit": {
        "class_name": "FocusIndicatorAudit",
        "enabled": true,
        "root_element_css_selector": "main",
        "pre_tab_key_presses": 0,
        "max_tab_key_presses": 15
    },
    "element_audit": {
        "class_name": "ElementAudit",
        "target_element_css_selector": "input:not([type="search"])",
        "enabled": true
    }
}
```

To add new audit plugins, first develop an appropriate test module/class within `./src/audit_plugins/`, and then enable that audit plugin by adding an entry within `config_default.json`.

Each plugin can have an optional `viewport_to_test` item, which allows you to run a plugin only at particular viewport sizes, if multiple are being tested. The value of this key must match a value within the `viewport_sizes` option.

## Updating Chrome and Chromedriver versions

From time to time, it might make sense to update the version of Chrome for Testing that CWAC uses.

To do this:

1. Visit [Chrome for Testing - GitHub](https://github.com/GoogleChromeLabs/chrome-for-testing)
2. Open the API endpoint `last-known-good-versions-with-downloads.json` in a JSON viewer (Firefox has one built-in)
3. Find the entry for the latest stable version of Chrome for Testing
4. Download the `chromedriver` that matches the version of Chrome for Testing you want to use
5. Place the `chromedriver` executable into the `/drivers/` folder in `cwac`, with a unique filename
6. Update the `chromeVersion` config property in `package.json`, ensuring it matches the `chromedriver` version
7. Run `npm install` to install the newly specified version of Chrome for Testing
8. Note: the `chromedriver` executable may need to have `chmod +x` run on it in order to give it execution permissions
9. macOS might come up with an error stating "chromedriver_mac_arm64" can't be opened because Apple cannot check it for malicious software.". This is fixed by running `xattr -d com.apple.quarantine <name-of-executable>`

## Copyright notices

### Copyright of Centralised Web Accessibility Checker (CWAC)

Crown copyright (c) 2024, Department of Internal Affairs on behalf of the New Zealand Government.

This copyright, along with CWAC's GPL-3.0 license, does not extend to the third-party chromedriver binaries located in the `/drivers/` folder. Permission to re-use third party copyright material cannot be given by the Department of Internal Affairs.

### chromedriver binaries copyright and license

CWAC includes chromedriver binaries at `/drivers/`. chromedriver licenses can be found in the `/drivers/` folder.

```plain
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
