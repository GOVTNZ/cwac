# Running CWAC

We recommend using CWAC with [Docker](https://www.docker.com/get-started/).

> [!WARNING]
>
> While you can run the tool without Docker and on OSs other than Linux, there
> are edge cases that can prevent some of the audits from running correctly.
>
> For example, the current version of Chrome for Testing used by the tool has a
> hard-coded minimum screen width of 500 px when on macOS. This means that the
> [Reflow audit](https://github.com/GOVTNZ/cwac/blob/main/doc/audits/reflow-audit.md)
> cannot run on that OS.

Once you have the codebase cloned locally and Docker set up, you can use the
`bin/run` script to run the tool.

This will automatically build the image and run the tool with any arguments you
provide:

```shell
# run the tool with the default configuration
bin/run

# run the tool with a custom configuration
bin/run my_custom_config.json
```

> [!WARNING]
>
> JSON configuration files must always be located in the `./config/` directory.
