#!/usr/bin/env bash

set -e

# create a url file
cat <<URLS > base_urls/visit/e2e.csv
organisation,url,sector
e2e,https://example.com,e2e
URLS

# create a config file
cat config/config_default.json | jq '
  .max_links_per_domain = 3 |
  .filter_to_organisations = ["e2e"] |
  .filter_to_urls = ["example.com"]
' > config/config_e2e.json

# make sure the "results" directory exists
mkdir -p results

# make sure the package-lock.json exists
npm i --package-lock-only

docker build \
  --iidfile /tmp/cwac_image_id \
  --build-arg USER_ID=$(id -u) \
  --build-arg GROUP_ID=$(id -g) \
  .

docker run --rm \
  --mount "type=bind,src=./config,dst=/cwac/config" \
  --mount "type=bind,src=./base_urls,dst=/cwac/base_urls" \
  --mount "type=bind,src=./results,dst=/cwac/results" \
  -e CHROME_EXTRA_ARGS='--no-sandbox,--disable-dev-shm-usage' \
  $(cat /tmp/cwac_image_id) .venv/bin/python -u cwac.py config_e2e.json
