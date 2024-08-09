# cwac-report
Website to display Centralised Web Accessibility Checker (CWAC) reports.

Built with Jekyll.

## Installation
1. Get Jekyll. Follow the installation instructions here: https://jekyllrb.com/docs/
2. Clone the repository
2. In a terminal, `cd` to the `cwac-report` directory

## Usage instructions

### Setup
- `cd` to `cwac-report` directory
- run `npm install`
- run `bundle install`

### Generating data
To generate data for usage in `cwac-report`: 
- If you haven't already, run a scan using `cwac` - its data will appear in `/cwac/results/` 
- In a terminal, `cd` to the `cwac` folder
- ensure the terminal prompt starts with `(.venv)`
   - if it doesn't, run the command `source .venv/bin/activate`
- In `cwac`, open `export_data_to_cwac_report_config.json` and set the `audit_data_source` property to a valid folder name within `/cwac/results/` - this will be where it gets results data from.
- In `cwac`, run `python export_data_to_cwac_report.py` - this file takes `cwac` raw data (from a folder specified in the previous step), and generates charts, and performs data queries and analysis. It places data into the `cwac-report` folder automatically.

### Configuration
- In `cwac`, there is a configuration file called `export_data_to_cwac_report_config.json`.
- Each entry in this JSON file corresponds to a 'chart' that will be visible in the final `cwac-report` output website.
- Field descriptions:
    - "report_type": can be: "disabled", "per_organisation", or "general". "disabled" skips that chart type, "general" will create a chart that provides an overview of all organisations specified within the `target_urls` of the CWAC scan, and "per_organisation" will generate a chart for each individual organisation in the data.
    - "file_name": specifies which raw data CSV file will be used for generating the chart. These files are stored in `cwac/results/[folder_name]` by default.
    - "chart_name": the name of the chart
    - "description" the description of the chart
    - "x_axis_title" the x-axis label string on the chart
    - "y_axis_title": the y-axis label string on the chart
    - "sql_query": a SQLite query used to get the data for the chart; this query is performed upon the data inside of "file_name" CSV.
        - NOTE: "sql_query" also has one 'special' value: "AxeCoreAuditTemplateAware". This is used to generate AxeCoreAuditTemplateAware charts, because the query is too complex to write within the config file, and is generated programmatically.
    - "query_table_x_key": column name for the "x" column of the data
    - "query_table_y_key": column name for the "y" column of the data

### Serving
1. Serve `cwac-report` by executing `bundle exec jekyll serve -o`. It may take several minutes to generate the website - be patient.
2. Or, if you just want to build self-contained HTML files of the reports, run `jekyll build`. The self-contained HTML report files will be in the `_site` folder.

