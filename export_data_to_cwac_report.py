"""export_data_to_cwac_report.py.

This script takes CWAC results data and generates
charts/CSVs/JSON for use in the cwac-report Jekyll
website (which is used for HTML presentation of
CWAC data for general audiences).

Instructions:
1. Run the CWAC scan
2. Get the folder name of relevant scan data in /results
3. Edit export_data_to_cwac_report_config.json to specify the
    folder name of the scan data
5. Optionally, edit the charts that are generated in the config
6. Run this script (data will be placed in the cwac-report folder)
7. Run the cwac-report Jekyll website to view the data

For better instructions, look at the READMEs.
"""

# pylint: disable=too-many-locals, too-many-arguments
# pylint: disable=too-many-statements, too-many-branches
# pylint: disable=too-many-nested-blocks, too-many-lines
import base64
import contextlib
import csv
import datetime
import io
import json
import os
import shutil
import sqlite3
import sys
import urllib
import uuid
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from numpy.typing import NDArray


class DataAnalysis:
    """Generates charts and tables for cwac-report."""

    def __init__(self) -> None:
        """Init vars."""
        print("Generating data for cwac-report...")
        self.sample_size = 0
        self.report_json_path = "./cwac-report/_data/"
        self.report_render_path = "./cwac-report/charts/"

        # Read the report config file from cwac_report_config.json
        with open("export_data_to_cwac_report_config.json", "r", encoding="utf-8") as config_file:
            file_data = json.load(config_file)
            self.audit_charts = file_data["charts_to_render"]

            # Ensure audit_data_source will not result in traversal
            # outside of the results folder

            # If audit_data_source contains a / or \, it could be dangerous
            if "/" in file_data["audit_data_source"] or "\\" in file_data["audit_data_source"]:
                raise ValueError("audit_data_source cannot contain / or \\")

            # Iterate charts_to_render and sanitise file_name
            for chart in self.audit_charts:
                # If file_name contains a / or \, it could be dangerous
                if "/" in chart["file_name"] or "\\" in chart["file_name"]:
                    raise ValueError("file_name cannot contain / or \\")

            self.audit_data_source = "./results/" + file_data["audit_data_source"]

            # Query the user to see what viewport_size they want
            # to use for the report
            self.viewport_size = self.viewport_size_selector()

            # Run axe_core_audit_template_aware
            self.run_axe_core_audit_template_aware(audit_path=self.audit_data_source)

    def slugify_filename(self, filename: str) -> str:
        """Slugifies a filename with underscores etc.

        Args:
            filename (str): The filename to slugify.

        Returns:
            str: The slugified filename.
        """
        # Remove non-alphanumeric characters
        filename = "".join([char for char in filename if char.isalnum() or char in [" ", "_"]])
        filename = filename.replace(" ", "_")
        filename = filename.lower()
        return filename

    def get_short_url(self, url: str) -> str:
        """Get the short URL from a long URL.

        A short URL removes https://www etc, but keeps the path

        Args:
            url (str): The long URL to shorten.
        """
        parsed_url = urllib.parse.urlparse(url)
        short_url = parsed_url.netloc + parsed_url.path
        if short_url.startswith("www."):
            short_url = short_url[4:]
        if short_url.endswith("/"):
            short_url = short_url[:-1]

        if len(short_url) > 45:
            short_url = short_url[:45] + "..."

        return short_url

    def get_short_urls_of_list(self, urls: list[str]) -> list[str]:
        """Get the short URL from a long URL.

        A short URL removes https://www etc, but keeps the path

        Args:
            urls list[str]: A list of long URLs to shorten.

        Returns:
            list[str]: A list of short URLs.
        """
        short_urls: list[str] = []
        for key in urls:
            short_urls.append(self.get_short_url(key))
        return short_urls

    def convert_list_of_dict_to_dict(
        self,
        list_of_dict: list[dict[str, Any]],
        key: str,
        value: str,
    ) -> dict[str, Any]:
        """Convert a list of dicts to a dict.

        Args:
            list_of_dict (list[dict[str, Any]]): A list of dicts.
            key (str): The key to use for the new dict.
            value (str): The value to use for the new dict.
        """
        new_dict: dict[str, Any] = {}
        for item in list_of_dict:
            new_dict[item[key]] = item[value]
        return new_dict

    def generate_horizontal_bar_chart(
        self,
        chart_name: str,
        x_y_labels: tuple[str, str],
        count_sums: dict[str, Any],
        dark_mode: bool,
    ) -> str:
        """Create a horizontal bar chart, and returns SVG string.

        Args:
            chart_name (str): The name of the chart.
            x_y_labels (tuple[str, str]): The x and y labels.
            count_sums (dict[str, Any]): Data for chart
            dark_mode (bool): Whether to use dark mode.

        Returns:
            str: The base64 SVG string of the chart.
        """
        print(f"Generating horizontal bar chart for {chart_name}...")

        raw_keys = self.get_short_urls_of_list(list(count_sums.keys()))
        raw_values = list(count_sums.values())

        # Cast values to int
        raw_values = [int(value) for value in raw_values]

        # Sort values and keys
        values, keys = zip(*sorted(zip(raw_values, raw_keys), reverse=True))

        # Cast values to list[int]
        int_values = list(values)

        # Set the chart height based on the number of items
        plt.figure(figsize=(10, 1.3 + len(keys) * 0.25))

        if dark_mode:
            plt.rcParams["text.color"] = "white"
            plt.rcParams["axes.labelcolor"] = "white"
            plt.rcParams["xtick.color"] = "white"
            plt.rcParams["ytick.color"] = "white"
            plt.rcParams["axes.edgecolor"] = "white"
            plt.rcParams["axes.facecolor"] = "black"
            plt.rcParams["figure.facecolor"] = "black"
            plt.rcParams["savefig.facecolor"] = "black"
            plt.rcParams["figure.edgecolor"] = "black"
        else:
            plt.rcParams["text.color"] = "black"
            plt.rcParams["axes.labelcolor"] = "black"
            plt.rcParams["xtick.color"] = "black"
            plt.rcParams["ytick.color"] = "black"
            plt.rcParams["axes.edgecolor"] = "black"
            plt.rcParams["axes.facecolor"] = "white"
            plt.rcParams["figure.facecolor"] = "white"
            plt.rcParams["savefig.facecolor"] = "white"
            plt.rcParams["figure.edgecolor"] = "white"

        # Define a custom colormap that goes from yellow to red
        colors = [(1, 1, 0), (1, 0.64, 0), (1, 0, 0)]

        cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list("", colors)  # type: ignore

        # Define a function to map values to colors
        def map_values_to_colors(values: list[int]) -> NDArray[np.float64]:
            colors = np.zeros((len(values), 4))
            for i, value in enumerate(values):
                colors[i] = cmap((value) / (np.max(values)))
            return colors

        # Map the values to colors
        mapped_colors = map_values_to_colors(int_values)

        # creating the bar plot with color gradient and black outlines
        edge_color = "white" if dark_mode else "black"
        barh_container = plt.barh(
            keys,
            int_values,
            tick_label=keys,
            color=mapped_colors,
            edgecolor=edge_color,
        )

        # Set bar width to fill the chart space
        plt.gca().set_ylim(-1, len(int_values) * 1.001)

        # Flip the y axis
        plt.gca().invert_yaxis()

        plt.ylabel(x_y_labels[0], fontdict={"fontweight": "bold"})
        plt.xlabel(x_y_labels[1], fontdict={"fontweight": "bold"})
        plt.title(
            chart_name,
            pad=20,
            fontdict={"fontsize": 15, "fontweight": "bold"},
        )
        plt.yticks(ha="right")

        # Use plt.bar_label to add y labels to the bars with padding
        # with 1 decimal place IF the values are floats
        if isinstance(int_values[0], float):
            labels = [f"{value:.1f}" for value in int_values]
        else:
            labels = [str(value) for value in int_values]

        # bar_label with red backgeround colour
        plt.bar_label(barh_container, labels=labels, padding=3)

        plt.margins(x=0.1)

        # add horizontal gridlines to the plot
        plt.grid(axis="x", linestyle="--", alpha=0.6)
        plt.tight_layout()

        # Get the chart as an SVG string using io
        svg_file = io.StringIO()
        plt.savefig(svg_file, format="svg")
        svg_file.seek(0)
        svg_string = svg_file.getvalue()
        svg_file.close()

        # Close the plot
        plt.close()

        # Convert svg_string into base64 into utf-8
        return base64.b64encode(svg_string.encode("utf-8")).decode("utf-8")

    def template_aware_algorithm(self, input_df: pd.DataFrame, groupby_cols: list[str]) -> pd.DataFrame:
        """Template aware algorithm - finds template-level issues.

        Uses pandas to group/aggregate axe-core data to show template
        level issues within websites.

        Args:
            input_df (pd.DataFrame): The input dataframe.
            groupby_cols (list[str]): The columns to group by.

        Returns:
            pd.DataFrame: The grouped and aggregated dataframe.
        """
        # Collect all rows where count is 0
        zero_count_rows = input_df[input_df["count"] == 0]

        # Remove the zero count rows from the input_df
        no_zero_count_df = input_df[input_df["count"] != 0]

        # Group the data
        grouped_df = no_zero_count_df.groupby(groupby_cols)

        # Generate the aggregation dictionary
        agg_dict = {"count": "sum"}

        # Add in 'first' for all other columns
        for col in input_df.columns:
            if col not in agg_dict and col not in groupby_cols:
                agg_dict[col] = "first"

        # Aggregate the data
        agg_df = grouped_df.agg(agg_dict)

        # Reset the index
        agg_df = agg_df.reset_index()

        # Concatenate the zero count rows with the agg data
        agg_df = pd.concat([agg_df, zero_count_rows])

        # Sort the data
        agg_df = agg_df.sort_values(by="count", ascending=False)

        return agg_df

    def run_axe_core_audit_template_aware(self, audit_path: str) -> None:
        """Combine repeated axe-core issues.

        Used for detecting template-level errors.

        Args:
            audit_path (str): The path to the audit folder.
        """
        # Read the CSV file into a list of dicts
        file_path = audit_path + "/axe_core_audit.csv"

        # If file doesn't exist, return
        if not os.path.exists(file_path):
            return

        # Read the CSV file into a DataFrame
        data_frame = pd.read_csv(file_path)

        # Get original column order for later use
        original_column_order = data_frame.columns

        # Group and aggregate the data
        data_frame = self.template_aware_algorithm(
            input_df=data_frame,
            groupby_cols=["base_url", "id", "html", "viewport_size"],
        )

        # Write the data to CSV file with original column order
        data_frame.to_csv(
            audit_path + "/axe_core_audit_template_aware.csv",
            index=False,
            columns=list(original_column_order),
        )

    def generate_axe_core_template_aware_query(
        self,
    ) -> str:
        """Generate the SQL query for the axe-core template aware report."""
        # Ensure it selects rows where best-practice is No
        query = """
             SELECT base_url, COUNT(*) as num_count
                    FROM cwac_table
                    WHERE count > 0
                    AND organisation LIKE :organisation
                    AND viewport_size LIKE :viewport_size
                    AND "best-practice" = 'No'
                    GROUP BY base_url
                    UNION
                    SELECT base_url, count
                    FROM cwac_table
                    WHERE count = 0
                    AND organisation LIKE :organisation
                    AND viewport_size LIKE :viewport_size
                    AND "best-practice" = 'No'
                    AND base_url NOT IN (
                        SELECT base_url
                        FROM cwac_table
                        WHERE count > 0
                        AND organisation LIKE :organisation
                        AND viewport_size LIKE :viewport_size
                        AND "best-practice" = 'No'
                        GROUP BY base_url
                    )
                    ORDER BY num_count DESC
                """
        return query

    def generate_general_report(self) -> None:
        """Generate the HTML report."""
        chart_metadata = []
        # Iterate through the chart types in self.audit_charts
        for _, chart_info in enumerate(self.audit_charts):
            if chart_info["report_type"] != "general":
                continue

            # If the query is AxeCoreAuditTemplateAware,
            # use the sum_rows_with_equal_specified_keys
            # instead of the normal query
            if chart_info["sql_query"] == "AxeCoreAuditTemplateAware":
                chart_info["file_name"] = "axe_core_audit_template_aware.csv"
                chart_info["sql_query"] = self.generate_axe_core_template_aware_query()

            try:
                chunk_size = 10**6
                print("reading ", chart_info["file_name"])
                data_frame_iterator = pd.read_csv(
                    self.audit_data_source + "/" + chart_info["file_name"],
                    chunksize=chunk_size,
                    header=0,
                )
                data_frame = pd.concat(data_frame_iterator, ignore_index=True)
            except FileNotFoundError:
                print("Could not find file: " + self.audit_data_source + "/" + chart_info["file_name"])
                continue

            # Generate base64 CSV file from the dataframe
            csv_file = data_frame.to_csv(index=False)
            csv_file_bytes = csv_file.encode("utf-8")
            raw_data = base64.b64encode(csv_file_bytes).decode("utf-8")

            # Connect to an in-memory database
            conn = sqlite3.connect(":memory:")

            # Write the dataframe to the database
            data_frame.to_sql("cwac_table", conn, index=False)

            # Print the file that was read
            print("File read: " + chart_info["file_name"])

            # Execute the SQL query
            try:
                # The 'organisation' parameter is a % wildcard
                # because we want to get all organisations in
                # the general report
                cursor = conn.execute(
                    chart_info["sql_query"],
                    {"organisation": "%", "viewport_size": self.viewport_size},
                )
            except sqlite3.OperationalError as error:
                print("Error: ", error)
                continue

            # Get the results of the query
            count_sums = cursor.fetchall()

            # Close the connection
            conn.close()

            # Convert list of tuples into list of dicts
            table_output = []
            table_headers = [
                chart_info["query_table_x_key"],
                chart_info["query_table_y_key"],
            ]
            for row in count_sums:
                zipped = dict(zip(table_headers, row))
                table_output.append(zipped)

            # Reformat the table so it can be used for matplotlib
            try:
                keys = list(table_output[0].keys())
            except IndexError:
                print("No data to generate chart.")
                continue
            final_output = self.convert_list_of_dict_to_dict(table_output, keys[0], keys[1])

            chart_light_base64 = self.generate_horizontal_bar_chart(
                chart_name=chart_info["chart_name"],
                x_y_labels=(
                    chart_info["x_axis_title"],
                    chart_info["y_axis_title"],
                ),
                count_sums=final_output,
                dark_mode=False,
            )
            chart_dark_base64 = self.generate_horizontal_bar_chart(
                chart_name=chart_info["chart_name"],
                x_y_labels=(
                    chart_info["x_axis_title"],
                    chart_info["y_axis_title"],
                ),
                count_sums=final_output,
                dark_mode=True,
            )

            # Remove .csv from the end of chart_info["file_name"]
            # This gives us the original name of the CWAC data inside
            # /results
            audit_type = chart_info["file_name"][:-4]

            chart_metadata.append(
                {
                    "sectionHeading": chart_info["chart_name"],
                    "auditType": audit_type,
                    "description": chart_info["description"],
                    "organisation": "AoG",
                    "chartTitle": chart_info["chart_name"],
                    "chartImageLight": chart_light_base64,
                    "chartImageDark": chart_dark_base64,
                    "tableData": table_output,
                    "rawData": raw_data,
                }
            )

        report_data = {
            "report_generation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uuid": str(uuid.uuid4()),
            "chart_sections": chart_metadata,
        }

        with open(self.report_json_path + "report.json", "w", encoding="utf-8") as report_file:
            report_file.write(json.dumps(report_data))

    def generate_anti_bot_data(self, organisation: str) -> dict[str, str]:
        """Generate a dict of URLs that got blocked by anti-bot measures.

        Args:
            organisation (str): The organisation to generate data for.

        Returns:
            dict[str, str]: key: url, value: reason it was blocked
        """
        # Check if the file exists
        if not os.path.exists(self.audit_data_source + "/anti_bot.csv"):
            return {}
        # Load anti_bot.csv as SQLite database
        conn = sqlite3.connect(":memory:")
        data_frame = pd.read_csv(self.audit_data_source + "/anti_bot.csv")
        data_frame.to_sql("anti_bot_table", conn, index=False)

        # Get the data for the organisation
        cursor = conn.execute(
            """
                SELECT domain,anti_bot_check
                FROM anti_bot_table
                WHERE organisation LIKE :organisation
                AND viewport_size LIKE :viewport_size
            """,
            {
                "organisation": organisation,
                "viewport_size": self.viewport_size,
            },
        )

        # Get the results of the query
        anti_bot_raw_data = cursor.fetchall()

        # Convert list of tuples into list of dicts
        table_output = []
        table_headers = ["domain", "anti_bot_check"]
        for row in anti_bot_raw_data:
            zipped = dict(zip(table_headers, row))
            table_output.append(zipped)

        # Convert to a dict
        anti_bot_data = self.convert_list_of_dict_to_dict(table_output, "domain", "anti_bot_check")

        # Close the connection
        conn.close()

        return anti_bot_data

    def generate_template_aware_chart_data(
        self, organisation: str, viewport_size: str, df: pd.DataFrame
    ) -> list[tuple[str, int]]:
        """Create the data for the template-aware axe-core chart.

        Args:
            organisation (str): The organisation to generate data for.
            viewport_size (str): The viewport size to generate data for.
            df (pd.DataFrame): The dataframe to generate data from.

        Returns:
            list[tuple[str, int]]: The data for the chart.
        """
        # Filter the df to the organisation specified
        df = df[df["organisation"] == organisation]

        # Get the unique base_urls
        base_urls = df["base_url"].unique()

        working_output = {}

        # Iterate through the base_urls
        for base_url in base_urls:
            # Count the number of rows with count > 0 and best-practice = 'No'
            # for the base_url

            # Get the number of rows with count > 0 and best-practice = 'No'
            # for the base_url
            count = len(
                df[
                    (df["base_url"] == base_url)
                    & (df["count"] > 0)
                    & (df["best-practice"] == "No")
                    & (df["viewport_size"] == viewport_size)
                ]
            )

            # Add the count to the working_output dict
            working_output[base_url] = count

        # Output for charts must be a list of tuples
        final_output = []

        for base_url, value in working_output.items():
            final_output.append((base_url, value))

        # Sort descending by count
        final_output = sorted(final_output, key=lambda x: x[1], reverse=True)

        return final_output

    def generate_per_organisation_reports(self) -> None:
        """Generate data on a per-org basis."""
        # Delete all files within _data/organisations
        # so that we can generate new ones
        for file in os.listdir(self.report_json_path + "organisations/"):
            if file.endswith(".json"):
                os.remove(self.report_json_path + "organisations/" + file)

        # Store set of viewport sizes for each org
        viewport_sizes: dict[str, set[str]] = {}

        # Iterate through the chart types in self.audit_charts
        for _, chart_info in enumerate(self.audit_charts):
            if chart_info["report_type"] != "per_organisation":
                continue

            print("Output for: " + chart_info["chart_name"])

            if chart_info["sql_query"] == "AxeCoreAuditTemplateAware":
                chart_info["file_name"] = "axe_core_audit_template_aware.csv"

            # Read the CSV file into sqlite3
            try:
                data_frame = pd.read_csv(self.audit_data_source + "/" + chart_info["file_name"])
            except FileNotFoundError:
                print("Could not find file: " + self.audit_data_source + "/" + chart_info["file_name"])
                continue

            # Connect to an in-memory database
            conn = sqlite3.connect(":memory:")

            # Write the dataframe to the database
            data_frame.to_sql("cwac_table", conn, index=False)

            # Print the file that was read
            print("File read: " + chart_info["file_name"])

            # Get unique organisations from the CSV
            cursor = conn.execute(
                "SELECT DISTINCT organisation FROM cwac_table WHERE viewport_size LIKE :viewport_size",
                {"viewport_size": self.viewport_size},
            )

            # Get the results of the query
            organisation_rows = cursor.fetchall()

            # Iterate through the organisations
            for _, organisation_row in enumerate(organisation_rows):
                organisation = organisation_row[0]

                # Skip blank organisations and header row
                if organisation in ["", "organisation"]:
                    continue

                path_to_page_data = (
                    self.report_json_path + "organisations/" + self.slugify_filename(organisation) + ".json"
                )

                # If file exists, read it
                if os.path.exists(path_to_page_data):
                    with open(path_to_page_data, "r", encoding="utf-8") as page_data_file:
                        page_data = json.load(page_data_file)
                else:
                    # Store per-org page data for Jekyll
                    page_data = {"organisation": organisation, "charts": []}

                # Escape single quotes in org name
                organisation_escaped = organisation.replace("'", "''")

                print("Generating report for: " + organisation)

                query = chart_info["sql_query"]

                subs = {
                    "organisation": organisation_escaped,
                    "viewport_size": self.viewport_size,
                }

                # Execute query (unless it's a template-aware axe-core result)
                if chart_info["sql_query"] == "AxeCoreAuditTemplateAware":
                    count_sums = self.generate_template_aware_chart_data(
                        organisation=organisation,
                        viewport_size=self.viewport_size,
                        df=data_frame,
                    )
                else:
                    try:
                        # Execute the query (prepared statement)
                        cursor = conn.execute(query, subs)
                    except sqlite3.OperationalError as exception:
                        print("SQL query failed: " + str(exception))
                        continue

                    # Get the results of the query
                    count_sums = cursor.fetchall()

                # Convert list of tuples into list of dicts
                table_output = []
                table_headers = [
                    chart_info["query_table_x_key"],
                    chart_info["query_table_y_key"],
                ]
                for row in count_sums:
                    zipped = dict(zip(table_headers, row))
                    table_output.append(zipped)

                # Reformat the table so it can be used for matplotlib
                try:
                    keys = list(table_output[0].keys())
                except IndexError:
                    print("No data to generate chart.")
                    continue
                final_output = self.convert_list_of_dict_to_dict(table_output, keys[0], keys[1])

                # Get the raw CWAC audit data for the organisation
                cursor = conn.execute(
                    "SELECT * FROM cwac_table "
                    "WHERE organisation LIKE :organisation "
                    "AND viewport_size LIKE :viewport_size",
                    subs,
                )
                raw_data_table = cursor.fetchall()

                # Convert raw_data into a CSV string
                # Convert the query result into a CSV string
                csv_buffer = io.StringIO()

                csv_writer = csv.writer(csv_buffer)

                # Write the header row
                csv_writer.writerow([i[0] for i in cursor.description])

                # Write the data rows
                for row in raw_data_table:
                    csv_writer.writerow(row)

                raw_data_csv = csv_buffer.getvalue()

                # Convert CSV string to base64 string
                raw_data = base64.b64encode(raw_data_csv.encode("utf-8")).decode("utf-8")

                # Get viewport sizes that tests occurred at
                cursor = conn.execute(
                    """
                        SELECT DISTINCT viewport_size
                        FROM cwac_table
                        WHERE organisation LIKE :organisation
                        AND viewport_size LIKE :viewport_size
                    """,
                    subs,
                )

                # Get the results of the query
                viewport_sizes_raw = cursor.fetchall()

                # Reformat the viewport sizes
                formatted_viewport_sizes = [json.loads(size[0].replace("'", '"')) for size in viewport_sizes_raw]

                # Iterate through viewport sizes and cast to str
                # and add to viewport_sizes dict with org as key
                for viewport_size in formatted_viewport_sizes:
                    if organisation not in viewport_sizes:
                        viewport_sizes[organisation] = set()
                    viewport_sizes[organisation].add(str(viewport_size))

                if len(viewport_sizes_raw) > 1:
                    print(
                        "WARNING: More than one viewport size found for " + organisation,
                        viewport_sizes_raw,
                    )
                    print("Resulting output:", viewport_sizes)

                # Append charts to page_data

                # Remove .csv from the end of chart_info["file_name"]
                # This gives us the original name of the CWAC data inside
                # /results
                audit_type = chart_info["file_name"][:-4]

                chart_data = {
                    "chartTitle": chart_info["chart_name"],
                    "description": chart_info["description"],
                    "tableData": table_output,
                    "auditType": audit_type,
                    "organisation": organisation,
                    "rawData": raw_data,
                }

                chart_light_base64 = self.generate_horizontal_bar_chart(
                    chart_name=chart_info["chart_name"],
                    x_y_labels=(
                        chart_info["x_axis_title"],
                        chart_info["y_axis_title"],
                    ),
                    count_sums=final_output,
                    dark_mode=False,
                )
                chart_dark_base64 = self.generate_horizontal_bar_chart(
                    chart_name=chart_info["chart_name"],
                    x_y_labels=(
                        chart_info["x_axis_title"],
                        chart_info["y_axis_title"],
                    ),
                    count_sums=final_output,
                    dark_mode=True,
                )
                chart_data["chartImageLight"] = chart_light_base64
                chart_data["chartImageDark"] = chart_dark_base64

                page_data["charts"].append(chart_data)

                # Generate anti_bot data
                anti_bot_data = self.generate_anti_bot_data(organisation=organisation)

                # Add anti_bot_data to page_data
                page_data["anti_bot_data"] = anti_bot_data

                # Write page_data as JSON
                with open(
                    path_to_page_data,
                    "w",
                    encoding="utf-8",
                ) as page_data_file:
                    page_data_file.write(json.dumps(page_data))

                # Additionally, add an item to the Jekyll "Collection"
                # to generate per-org pages
                collection_path = self.report_json_path + "../_organisations/"

                # Convert the page_data into YAML "collection" item
                # for Jekyll
                collection_item = {
                    "title": organisation,
                    "layout": "organisation",
                    "organisation": organisation,
                    "viewport_sizes": str(list(viewport_sizes[organisation])),
                    "json_filename": self.slugify_filename(organisation) + ".json",
                    "report_generation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "uuid": str(uuid.uuid4()),
                }

                # Write the collection item as YAML
                with open(
                    collection_path + self.slugify_filename(organisation) + ".md",
                    "w",
                    encoding="utf-8",
                ) as collection_file:
                    collection_file.write("---\n")
                    collection_file.write(yaml.dump(collection_item))
                    collection_file.write("---\n")

            # Close the connection
            conn.close()

    def clear_data_from_cwac_report(self) -> None:
        """Clear out data/files in cwac-report directory."""
        cwac_report_path = "./cwac-report/"
        file_1 = cwac_report_path + "_data/report.json"
        org_json_files = cwac_report_path + "_data/organisations/"
        organisation_stubs = cwac_report_path + "_organisations/"

        # Delete the report.json file
        with contextlib.suppress(FileNotFoundError):
            os.remove(file_1)

        # Delete the contents of the organisations directory
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(org_json_files)

        # Delete the contents of the _organisations directory
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(organisation_stubs)

        # Create the organisations directory
        with contextlib.suppress(FileExistsError):
            os.mkdir(org_json_files)

        # Create the _organisations directory
        with contextlib.suppress(FileExistsError):
            os.mkdir(organisation_stubs)

    def viewport_size_selector(self) -> str:
        """Asks user to select viewport to generate report for.

        Returns:
            str: The selected viewport size.
        """
        viewports_encountered = set()
        print("Reading data to determine viewport sizes...")

        # Iterate through the chart types in self.audit_charts
        for _, chart_info in enumerate(self.audit_charts):
            if chart_info["sql_query"] == "AxeCoreAuditTemplateAware":
                chart_info["file_name"] = "axe_core_audit_template_aware.csv"

            # Read the CSV file into dataframe
            try:
                data_frame = pd.read_csv(self.audit_data_source + "/" + chart_info["file_name"])
            except FileNotFoundError:
                print("Could not find file: " + self.audit_data_source + "/" + chart_info["file_name"])
                continue

            # Check if data_frame has viewport_size column
            if "viewport_size" not in data_frame.columns:
                continue
            # Get unique viewport_size from the dataframe
            viewport_sizes = data_frame["viewport_size"].unique()

            # Iterate through the viewport_sizes
            for viewport_size in viewport_sizes:
                # Add to set
                viewports_encountered.add(viewport_size)

        # If there is only one viewport size, return it
        if len(viewports_encountered) == 1:
            return str(list(viewports_encountered)[0])

        # Parse viewports set to a list of dicts
        viewports_sorted = []
        for viewport in viewports_encountered:
            viewports_sorted.append(json.loads(viewport.replace("'", '"')))

        # Sort the viewports by lowest 'width' value
        viewports_sorted = sorted(viewports_sorted, key=lambda k: k["width"])

        # If there are multiple viewport sizes, ask the user to select one
        print("-" * 80)
        print("Viewport scan complete.")
        print("Multiple viewport sizes found in CWAC data.")
        print("cwac-report only supports one viewport size at a time.")
        print("Please select a viewport size to generate a report for:")

        for i, viewport_size in enumerate(viewports_sorted):
            print(f"\t{i + 1}:", viewport_size)

        # Get user input
        user_input_str = input("Please enter a number: ")
        user_input_int = 1

        # Validate user input
        try:
            user_input_int = int(user_input_str) - 1
        except ValueError:
            print("Invalid input.")
            sys.exit(1)

        # If user input is out of range, exit
        if user_input_int < 0 or user_input_int > len(viewports_sorted) - 1:
            print("Invalid input.")
            sys.exit(1)

        selected = viewports_sorted[user_input_int]
        print("You selected: ", selected)

        # Cast the selected option back to a single-quoted value string
        final_selection = json.dumps(selected).replace('"', "'")

        # Return the selected viewport size
        return final_selection


if __name__ == "__main__":
    analysis = DataAnalysis()
    analysis.clear_data_from_cwac_report()
    analysis.generate_general_report()
    analysis.generate_per_organisation_reports()
