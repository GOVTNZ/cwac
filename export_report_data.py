"""export_report_data.py.

This file generates report CSV data that is stored in ./reports/.
The data is generated from the raw data in ./results/.
To configure the export, edit export_report_data_config.json.
"""

import json
import os
import sqlite3
from datetime import date
from typing import Any, cast

import pandas as pd

TODAY = str(date.today())


class DataExporter:
    """Outputs CSV data from ./results/ to ./reports/."""

    def __init__(self) -> None:
        """Init vars."""
        self.config = self.import_config_file()
        self.input_path = "./results/" + self.config["input_results_folder_name"] + "/"
        self.output_path = "./reports/" + self.config["output_report_name"] + "/"
        # assert the input_path exists
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input path {self.input_path} does not exist.")
        # create ouptut folder if it doesn't exist
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        self.iterate_export_formats()

    def get_num_unique_pages_scanned(self, df: pd.DataFrame) -> pd.DataFrame:
        """Returns a DF with num of unique pages scanned for each base_url.

        Args:
            df (pd.DataFrame): The input DataFrame

        Returns:
            pd.DataFrame: The resulting DataFrame
        """
        # Create a new sqlite3 connection to count how many pages scanned
        page_count_conn = sqlite3.connect(":memory:")

        # Get a sqlite3 db of the data frame as it should have all the unique urls scanned
        df.to_sql("cwac_table", page_count_conn, index=False)

        # Query how many unique 'url' values each 'base_url' has
        url_count_query = """
        SELECT base_url, COUNT(DISTINCT url) as num_pages_scanned
        FROM cwac_table
        GROUP BY base_url
        """
        # Run the query
        url_count_result = page_count_conn.execute(url_count_query).fetchall()

        # Convert the result to a DataFrame
        url_count_df = pd.DataFrame(url_count_result, columns=["base_url", "num_pages_scanned"])

        return url_count_df

    def generate_axe_core_leaderboard(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generates the axe-core leaderboard dataframe."""
        # Generate the SQL query for the axe-core template aware report
        query = self.generate_axe_core_template_aware_query()

        # Convert df to sqlite3 in-mem db
        leaderboard_conn = sqlite3.connect(":memory:")

        # Write the data to the in-memory database
        df.to_sql("cwac_table", leaderboard_conn, index=False)

        # Run query with conn.execute
        leaderboard = leaderboard_conn.execute(query).fetchall()

        # Convert the result to a DataFrame
        url_count_df = self.get_num_unique_pages_scanned(df)

        # Convert results to DataFrame
        leaderboard_df = pd.DataFrame(leaderboard, columns=["organisation", "base_url", "num_issues"])

        # Add the 'num_pages_scanned' column to the leaderboard_df
        leaderboard_df = pd.merge(leaderboard_df, url_count_df, on="base_url")

        # Add a column of 'count' / 'num_pages_scanned' to the DataFrame
        leaderboard_df["average_count"] = (leaderboard_df["num_issues"] / leaderboard_df["num_pages_scanned"]).round(2)

        # Sort df on 'average_count' in descending order
        leaderboard_df = leaderboard_df.sort_values(by="average_count", ascending=False)

        # Add rank column
        # leaderboard_df["rank"] = leaderboard_df["average_count"].rank(method="dense", ascending=True)

        # Ensure "rank" is an integer
        # leaderboard_df["rank"] = leaderboard_df["rank"].astype(int)

        # Add percentile column
        leaderboard_df["percentile"] = (leaderboard_df["average_count"].rank(pct=True) * 100).round(2)

        # Rename columns to be more descriptive
        leaderboard_df = leaderboard_df.rename(columns={"average_count": "average_num_issues_per_page"})

        # Reorder so num_issues and average_num_issues_per_page are next to each other
        leaderboard_df = leaderboard_df[
            [
                "organisation",
                "base_url",
                "num_pages_scanned",
                "num_issues",
                "average_num_issues_per_page",
                "percentile",
            ]
        ]

        return leaderboard_df

    def generate_leaderboard(self, query: str, input_df: pd.DataFrame) -> pd.DataFrame:
        """Generates a leaderboard by performing the query on the input_df.

        Args:
            query (str): SQL query to perform on input_df
            input_df (pd.DataFrame): Input DataFrame

        Returns:
            pd.DataFrame: The resulting leaderboard DataFrame
        """
        # Make a sqlite3 connection
        conn = sqlite3.connect(":memory:")

        # Write input_df to the in-memory database
        input_df.to_sql("cwac_table", conn, index=False)

        # Run query
        leaderboard = conn.execute(query).fetchall()

        # Get columns from leadeboard
        columns = conn.execute(query).description

        # Convert to df and preserve columns
        leaderboard_df = pd.DataFrame(leaderboard, columns=[col[0] for col in columns])

        # Convert the result to a DataFrame
        url_count_df = self.get_num_unique_pages_scanned(input_df)

        # Merge the url_count_df with the leaderboard_df
        leaderboard_df = pd.merge(leaderboard_df, url_count_df, on="base_url")

        # Add average issue count per page (if it has a 'count' column)
        if "count" in leaderboard_df.columns:
            leaderboard_df["average_count"] = (leaderboard_df["count"] / leaderboard_df["num_pages_scanned"]).round(2)
            # Sort by 'average_count'
            leaderboard_df = leaderboard_df.sort_values(by="average_count", ascending=False)

        return leaderboard_df

    def export_raw_data(self, input_filename: str, output_filename: str) -> None:
        """Export the raw data from the input_filename to the output_filename.

        Args:
            input_filename (str): The input filename.
            output_filename (str): The output filename.
        """
        with (
            open(self.input_path + input_filename, "r", encoding="utf-8-sig") as input_file,
            open(self.output_path + output_filename, "w", encoding="utf-8-sig") as output_file,
        ):
            output_file.write(input_file.read())

    def iterate_export_formats(self) -> None:
        """Iterate through the export formats."""
        axe_core_template_aware_df: pd.DataFrame | None = None

        for export_format in self.config["export_formats"]:
            # if 'enabled' is False, skip the export format
            if not export_format["enabled"]:
                print(f"Skipping {export_format['export_type']} for {export_format['output_filename']}")
                continue

            # print(f"Exporting {export_format['export_type']} to {export_format['output_filename']}")
            print(f"Exporting {export_format['export_type']} to {self.config['output_report_name']}")

            # Perform string subs for output filename (include output_report_name in all files)
            export_format["output_filename"] = export_format["output_filename"].replace("[output_report_name]", TODAY)
            # Check if export_format["input_filename"] exists
            if "input_filename" in export_format and not os.path.exists(
                self.input_path + export_format["input_filename"]
            ):
                print(f"WARNING: File {self.input_path + export_format['input_filename']} does not exist.")
                continue

            if export_format["export_type"] == "leaderboard":
                output_df = self.generate_leaderboard(
                    query=export_format["query"],
                    input_df=self.import_audit_csv_to_df(export_format["input_filename"]),
                )

                # Write leaderboard to CSV
                output_df.to_csv(
                    self.output_path + export_format["output_filename"],
                    index=False,
                )

            if export_format["export_type"] == "raw_data":
                self.export_raw_data(
                    input_filename=export_format["input_filename"],
                    output_filename=export_format["output_filename"],
                )

            if export_format["export_type"] == "generate_axe_core_template_aware_file":
                # Run the axe-core template-aware algorithm
                # to generate the template-aware CSV
                axe_core_template_aware_df = self.run_axe_core_audit_template_aware()
                continue

            if export_format["export_type"] == "axe_core_template_aware_leaderboard":
                if axe_core_template_aware_df is None:
                    raise ValueError(
                        "The generate_axe_core_template_aware_file export must happen before"
                        " the axe_core_template_aware_leaderboard export can run"
                    )

                # Generate the axe-core leaderboard
                leaderboard_df = self.generate_axe_core_leaderboard(axe_core_template_aware_df)
                # Write the leaderboard to a CSV file
                leaderboard_df.to_csv(
                    self.output_path + export_format["output_filename"],
                    index=False,
                )

    def import_audit_csv_to_df(self, input_filename: str) -> pd.DataFrame:
        """Import the audit CSV file to a DataFrame."""
        audit_df = pd.read_csv(self.input_path + input_filename)
        return audit_df

    def import_config_file(self) -> dict[str, Any]:
        """Import export_report_data_config.json."""
        with open("export_report_data_config.json", "r", encoding="utf-8-sig") as file:
            config = cast(dict[str, Any], json.load(file))
        return config

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
        agg_dict = {"num_items": "sum"}

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

    def run_axe_core_audit_template_aware(self) -> pd.DataFrame:
        """Combine repeated axe-core issues.

        Used for detecting template-level errors.

        Args:
            export_path (str): The path to the audit folder.
        """
        # Read the CSV file into a list of dicts
        file_path = self.input_path + "/axe_core_audit.csv"

        # If file doesn't exist, return
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} does not exist.")

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
            self.input_path + "/axe_core_audit_template_aware.csv",
            index=False,
            columns=list(original_column_order),
        )

        return data_frame

    def generate_axe_core_template_aware_query(
        self,
    ) -> str:
        """Generate the SQL query for the axe-core template aware report."""
        query = """
             SELECT organisation, base_url, COUNT(*) as num_count
                    FROM cwac_table
                    WHERE count > 0
                    AND "best-practice" = 'No'
                    GROUP BY base_url
                    UNION
                    SELECT organisation, base_url, count
                    FROM cwac_table
                    WHERE count = 0
                    AND "best-practice" = 'No'
                    AND base_url NOT IN (
                        SELECT base_url
                        FROM cwac_table
                        WHERE count > 0
                        AND "best-practice" = 'No'
                        GROUP BY base_url
                    )
                    ORDER BY num_count DESC
                """
        return query


if __name__ == "__main__":
    exporter = DataExporter()
