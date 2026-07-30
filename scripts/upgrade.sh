#!/bin/bash

# set -x # Print commands and their arguments as they are executed
set -e # Exit immediately if a command exits with a non-zero status

# Find the latest stable version of Chrome for testing
CHROME_VERSION=$(curl --silent https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | jq -r '.channels.Stable.version')
echo "Using Chrome version: ${CHROME_VERSION}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/.."

cd $PROJECT_DIR/drivers
echo "Current working directory: $(pwd)"

echo "Downloading ChromeDriver binaries for version ${CHROME_VERSION}..."
curl -O https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip
curl -O https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/mac-arm64/chromedriver-mac-arm64.zip
curl -O https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/mac-x64/chromedriver-mac-x64.zip

# Unzip the downloaded files and move them to the appropriate locations
echo "Extracting Linux ChromeDriver and renaming to chromedriver_linux_x64..."
unzip -o chromedriver-linux64.zip "chromedriver-linux64/chromedriver" -d .
mv chromedriver-linux64/chromedriver ./chromedriver_linux_x64
rm -rf ./chromedriver-linux64/

echo "Extracting Mac ARM64 ChromeDriver and renaming to chromedriver_mac_arm64..."
unzip -o chromedriver-mac-arm64.zip "chromedriver-mac-arm64/chromedriver" -d .
mv chromedriver-mac-arm64/chromedriver ./chromedriver_mac_arm64
rm -rf ./chromedriver-mac-arm64

echo "Extracting Mac x64 ChromeDriver and renaming to chromedriver_mac_x64..."
unzip -o chromedriver-mac-x64.zip "chromedriver-mac-x64/chromedriver" -d .
mv chromedriver-mac-x64/chromedriver ./chromedriver_mac_x64
rm -rf ./chromedriver-mac-x64

# Clean up the downloaded zip files
echo "Cleaning up downloaded zip files..."
rm chromedriver-linux64.zip
rm chromedriver-mac-arm64.zip
rm chromedriver-mac-x64.zip

# Tell user the next step
echo ""
echo "Now update package.json with the new ChromeDriver version: ${CHROME_VERSION} and run 'npm install' to update the dependencies."
echo ""