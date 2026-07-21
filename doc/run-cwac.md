# Running CWAC

1. Ensure you have completed the setup instructions in [Installing CWAC](./install.md).
2. Review [Configuring CWAC](./audit-config.md) to create your desired scan configuration (or just use the defaults).

Once the configuration files are set up, CWAC can be run by executing:

```bash
# You need to have the Python venv set up in your shell. If you have not already
# done this then run
source .venv/bin/activate

# uses ./config/config_default.json as its configuration source.
python cwac.py

# To specify a config file for CWAC:
# This will cause CWAC to load `./config/config_custom.json` instead of
# `config_default.json`.
python cwac.py config_custom.json
```

> [!WARNING]
> JSON configuration files must always be located in the `./config/` directory.
