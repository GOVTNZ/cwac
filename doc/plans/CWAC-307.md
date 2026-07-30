# CWAC-307: Upgrade to latest stable Chrome

## Background

We want to be on as recent as possible stable _Chrome for Testing_ version so
that cwac checks are run in a browser similar to the one users will use to
replicate the findings.

## Key Considerations

You can find the latest _Chrome for Testing_ version manually by visiting
https://googlechromelabs.github.io/chrome-for-testing/ or programatically via:

```bash
curl --silent https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | jq -r '.channels.Stable.version'
```

The steps to upgrade are:

1. Update to latest chromedriver. This is automated in `scripts/upgrade-chromedriver.sh` which you can use as a guide if you wish to do the upgrade manually.
2. Update `pacakge.json` with the new chromedriver version.
3. Run `npm install` to download _Chrome for Testing_ binaries corresponding to the new chromedriver version from `package.json`. The new binaries are downloaded to `chrome/`
4. Run the `scripts/selenium_smoke_test.py` script to verify that the new Chromedriver works on your local machine.
4. Run the `tests/e2e.sh` script to verify that the new Chromedriver works in the Docker container.

## Open Considerations

### Remove x64 mac chromedriver

We can stop downloading the x64 mac chromedriver at some point.

Apple stopped selling their last x64 (Intel) based mac - the Mac Pro - in 2023.
However that computer was extremely expensive and therefore fairly niche.
Apple stopped selling intel based versions of their popeular machines (laptops) in 2020.
As time goes on, the chances of someone wanting to run cwac on an intel based mac reduces.

The wins for doing this are:

1. Removes 18MB from the repo and docker image
2. Slight simplification of the chromedriver upgrade process

Doing this deprecation as part of this ticket could make sense if we are happy with the timing.

### Should we be checking chromedriver versions into the repo?

Each one is ~20MB and we have 3 so ~60MB added every time we upgrade a version. Feels like something that will make us sad as the years go on.

The downside of not checking them in is that the user has to run an extra script on first setup.

## Closed Considerations

There are a number of performance optimisations we could consider for our `Dockerfile`. Those are out of scope for this ticket.
