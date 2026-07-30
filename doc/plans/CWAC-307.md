# CWAC-307: Upgrade to latest stable Chrome

## Background

We want to be on a recent _Chrome for Testing_ version so that cwac checks are
run in a browser similar to the one users will use to replicate the findings.

## Key Considerations

You can find the latest _Chrome for Testing_ version manually by visiting
https://googlechromelabs.github.io/chrome-for-testing/ or programatically via:

```bash
curl --silent https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | jq -r '.channels.Stable.version'
```

The steps to upgrade are:

1. Update to latest chromedriver. This is automated in `scripts/upgrade-chrome.sh` which you can use as a guide if you wish to do the upgrade manually.
2. Update `pacakge.json` with the new chromedriver version.
3. Run `npm install` to download the corresponding _Chrome for Testing_ binaries to `chrome/`
4. Run the `scripts/chromedriver_smoketest.py` script to verify that the new Chromedriver works ok on your current OS and CPU architecture.
5. Build and run the docker image. Then run the smoke test script inside the docker container to verify it works there.

    ```bash
    # build and run the docker image
    your-local-machine$ docker build -t cwac:test-upgraded-chrome.
    your-local-machine$ docker run --rm -it cwac:test-upgraded-chrome bash

    # inside the image, run the smoke check script
    docker-image$ python --version
    docker-image$ python selenium_smoke_test.py
    ```

## Open Considerations

None.

## Closed Considerations

There are a number of performance optimisations we could consider for our `Dockerfile`. Those are out of scope for this ticket.
