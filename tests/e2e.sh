#!/usr/bin/env bash

set -e

# Make sure script runs from project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "${PROJECT_ROOT}"

# create a url file
cat <<URLS > base_urls/visit/e2e.csv
url,sector
https://example.com,e2e
URLS

# create a config file
cat config/config_default.json | jq '
  .audit_name = "e2e" |
  .max_links_per_domain = 3 |
  .filter_to_urls = ["example.com"] |
  .audit_plugins |= map_values(.enabled = true)
' > config/config_e2e.json

# make sure the "results" directory exists
mkdir -p results

bin/run config_e2e.json
