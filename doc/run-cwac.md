# Running CWAC

We recommend running CWAC in docker.

It is technically possible to run CWAC on other platforms but we do not
recommend it because there are annoying edge-cases. For example, as of this
writing, the latest Chrome for Testing (151.0.7922.71) has a hard-coded minimum
screen width of 500 px. This means that the
[Reflow audit](./audits/reflow-audit.md) cannot run.

The instructions below focus on first-time users. If you are already familiar
with docker then you'll probably want to skip to our
[Docker compose file](../compose.yml).

First install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
Now you should have the `docker` command available in your shell.

```bash
docker --version

# clone this project
git clone https://github.com/GOVTNZ/cwac.git

# change dir to root of this project
cd path/to/cwac

Review [Configuring CWAC](./audit-config.md) to create your desired scan
configuration (or just use the defaults).

# Build and run the container using default options.
# Use default config (./config/config_default.json)
docker compose up

# use a specific config (./config/config_my_custom_config.json)
CWAC_CONFIG=config_my_custom_config.json docker compose up
```

> [!WARNING]
>
> JSON configuration files must always be located in the `./config/` directory.
