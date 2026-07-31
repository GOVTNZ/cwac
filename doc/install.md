# Installing CWAC

## Step 1: Ensure appropriate Python and NodeJS are installed

CWAC is a Python app and requires Python 3.12 or later. Ensure you have an
appropriate version of Python installed and available. You can verify this by
running:

```bash
$ python --version
# should return a version number 3.12 or greater
```

CWAC also requires NodeJS for these dependencies:

- axe-core
- Readability
- Chrome for Testing

You can verify that NodeJS and npm (the NodeJS package manager) are installed by
running:

```bash
node -v # should not fail, should return the installed nodejs version
npm -v  # should not fail, should return the installed npm version
```

## Step 2: Set up Python env and install Python packages

Next you need to install the required Python libraries. There are multiple ways
to achieve this in Python. Below documents using [uv](https://docs.astral.sh/uv/) which manages a lot of the details and is recommended if you don't already have a preferred way of managing Python versions.

Before you begin you need to install `uv` via one of the methods listed on https://docs.astral.sh/uv/getting-started/installation/#standalone-installer

```bash
cd cwac # change to project root dir

# verify you have uv installed and available in your shell
uv --version

uv python install # install an appropriate version of python

# set up Python venv
uv venv
source .venv/bin/activate

# check Python is set up in your shell
python --version

# install required packages (taken from pyproject.toml
uv sync
```

### Step 3: Install NPM packages

```bash
cd cwac # change to project root dir

# install NodeJS packages
npm install
```

The NodeJS package installation should also install a locally downloaded copy of
[Chrome for Testing](https://developer.chrome.com/blog/chrome-for-testing) (a
stand-alone version of the Chrome browser optimised for testing pages) as well
as a compatible version of chromedriver (which forms the bridge between CWAC and
the _Chrome for Testing_ instance).

Verify that these have downloaded correctly by manually inspecting the
`cwac/chrome` and `cwac/drivers` directories. They should contain files and
folders.

> [!NOTE]
>
> Pull requests improving the automatic detection to cover additional OSs and
> architectures are welcome

## Troubleshooting

### CWAC fails to find Chrome for Testing or Chromedriver

By default, CWAC will attempt to automatically determine the paths for Chrome
for Testing and the Chrome driver based on your OS and architecture.

If the paths cannot be determined automatically, you can pass them manually by:

1. Look inside the `cwac/chrome/` directory. Note the folder name for the
   version of Chrome for Testing that was downloaded i.e.
   `mac_arm-114.0.5735.90`
2. Open `cwac/config/`. For every config file in this directory e.g.
   `config_default.json`, modify the value of `chrome_binary_location` so the
   correct binary path is specified. For example:
   - For ARM based macOS the value of `chrome_binary_location` could be:
     `./chrome/mac_arm-114.0.5735.90/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`
     **NB: This path must be the FULL path to the binary within the `.app`
     directory**.
   - For Linux x64, the `chrome_binary_location` could be:
     `./chrome/linux-114.0.5735.90/chrome-linux64/chrome`

### If you get nltk certificate errors on macOS

On macOS, `urllib` may fail when attempting to fetch data for `nltk`, with
certificate errors. To fix this, go to
`/Applications/Python 3.x.x/Install Certificates.command`. This file should
install the necessary certificates and resolve the error.

### macOS security error

If you run CWAC and get the error
`"chromedriver_mac_arm64" can't be opened because Apple cannot check it for malicious software.`
then running this may resolve it:

```bash
xattr -d com.apple.quarantine <name-of-executable>
```
