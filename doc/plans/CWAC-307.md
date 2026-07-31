# CWAC-307: Upgrade to latest stable Chrome

## Background

We want to be on as recent as possible stable _Chrome for Testing_ version so
that cwac checks are run in a browser similar to the one users will use to
replicate the findings.

## Key Considerations

### Remove the existing partial support for Intel based macs

The `drivers/` directory had a binary for x64 Intel macs but cwac itself never
supported loading it in [config.py](../../config.py). This ticket will not
attempt to add support Intel based macs.

### Stop committing the chromedriver binaries to the repo.

Each chromedriver binary is ~20MB. If we continue to commit these to the git
repo then the repo will increase in size by ~40MB on every Chrome upgrade. This
will make working with the repo increasingly annoying.

This ticket will start using npm puppeteer package for chromedriver downloads,
similarly to how we already do for Chrome downloads.  After this ticket lands,
running `npm install` will install both Chrome and chromedriver. Nothing changes
in terms of setting up the repo for new users.

## Steps for future upgrades

You can find the latest _Chrome for Testing_ version manually by visiting
https://googlechromelabs.github.io/chrome-for-testing/ or programmatically via:
```bash
curl --silent https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | jq -r '.channels.Stable.version'
```

The steps to upgrade are:

1. Run the command above (or manually visit site) to get latest stable _Chrome for Testing_.
2. Update `pacakge.json` with the new version.
3. Run `npm install` to download _Chrome for Testing_ and _Chromedriver_
   binaries corresponding to the new version from `package.json`. The binaries
   are downloaded to `chrome/` and `chromedriver/` respectively.
4. Run the `tests/e2e.sh` script to verify that the new Chromedriver works in the Docker container.

## Open Considerations

None.

## Closed Considerations

There are a number of performance optimisations we could consider for our `Dockerfile`. Those are out of scope for this ticket.
