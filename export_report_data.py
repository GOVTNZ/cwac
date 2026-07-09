"""export_report_data.py.

This file generates report CSV data that is stored in ./reports/.
The data is generated from the raw data in ./results/.
To configure the export, edit export_report_data_config.json.
"""

import json
import os
import re
import sqlite3
import sys
from typing import Any, Callable, cast

import pandas as pd


class DataExporter:
  """Outputs CSV data from ./results/ to ./reports/."""

  def __init__(self, results_folder_name: str, use_inline_config: bool) -> None:
    """Init vars."""
    print(f'Processing ./results/{results_folder_name}')

    self.results_path = './results/' + results_folder_name

    # ensure the results path actually exists
    if not os.path.exists(self.results_path):
      raise FileNotFoundError(f'Input path {self.results_path} does not exist.')

    self.config = self.import_config_file(use_inline_config)
    self.output_prefix = self.config['output_filename_prefix']
    self.iterate_export_formats()

  def __build_results_path(self, sub: str) -> str:
    if sub in ('', '.', '..') or '..' in sub or '/' in sub or '\\' in sub:
      raise ValueError('filename must be a simple path without path separators or consecutive dots')
    return os.path.join(self.results_path, sub)

  # noinspection PyDefaultArgument
  def sort_with_default(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Sort the data frame by the given columns in descending order followed by default columns for consistency."""
    ascending = [False] * len(columns) + [True, True, True]
    columns = list(
      filter(
        lambda key: key in df.columns,
        columns + ['organisation', 'base_url', 'url'],
      )
    )

    return df.sort_values(by=columns, ascending=ascending[0 : len(columns)])

  def export_raw_data(self, input_filename: str, output_filename: str) -> None:
    """Export the raw data from the input_filename to the output_filename.

    Args:
        input_filename (str): The input filename.
        output_filename (str): The output filename.
    """
    # handle CSV files with data frames so that they can be sorted
    if input_filename.endswith('.csv'):
      df = self.import_audit_csv_to_df(input_filename)
      df = self.sort_with_default(df, [])

      df.to_csv(self.__build_results_path(self.output_prefix + output_filename), index=False)

      return

    with (
      open(self.__build_results_path(input_filename), 'r', encoding='utf-8-sig') as input_file,
      open(self.__build_results_path(self.output_prefix + output_filename), 'w', encoding='utf-8-sig') as output_file,
    ):
      output_file.write(input_file.read())

  def iterate_export_formats(self) -> None:
    """Iterate through the export formats."""
    for export_format in self.config['export_formats']:
      # if 'enabled' is False, skip the export format
      if not export_format['enabled']:
        print(f'Skipping {export_format["export_type"]} for {export_format["output_filename"]}')
        continue

      # print(f"Exporting {export_format['export_type']} to {export_format['output_filename']}")
      print(f'Exporting {export_format["export_type"]} to {self.results_path}')

      # Check if export_format["input_filename"] exists
      if 'input_filename' in export_format and not os.path.exists(
        self.__build_results_path(export_format['input_filename'])
      ):
        print(f'WARNING: File {self.__build_results_path(export_format["input_filename"])} does not exist.')
        continue

      if export_format['export_type'] == 'raw_data':
        self.export_raw_data(
          input_filename=export_format['input_filename'],
          output_filename=export_format['output_filename'],
        )

      if export_format['export_type'] == 'generate_axe_core_template_aware_file':
        # Run the axe-core template-aware algorithm
        # to generate the template-aware CSV
        self.run_axe_core_audit_template_aware(export_format['output_filename'])

  def import_audit_csv_to_df(self, input_filename: str) -> pd.DataFrame:
    """Import the audit CSV file to a DataFrame."""
    audit_df = pd.read_csv(self.__build_results_path(input_filename))
    return audit_df

  def import_config_file(self, use_inline_config: bool) -> dict[str, Any]:
    """Import the configuration file.

    If `use_inline_config` is true then the configuration will be imported from the
    "reporting" configuration within the input results config.json.

    Otherwise, the `export_report_data_config.json` file will be used.
    """
    filename = self.__build_results_path('config.json') if use_inline_config else 'export_report_data_config.json'

    with open(filename, 'r', encoding='utf-8-sig') as file:
      config = cast(dict[str, Any], json.load(file))

    if not use_inline_config:
      return config

    reporting = config.get('reporting')
    if not isinstance(reporting, dict):
      raise KeyError('config.json has non-object "reporting" key')
    return reporting

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
    zero_count_rows = input_df[input_df['num_issues'] == 0]

    # Remove the zero count rows from the input_df
    no_zero_count_df = input_df[input_df['num_issues'] != 0]

    # Group the data
    grouped_df = no_zero_count_df.groupby(groupby_cols)

    # Generate the aggregation dictionary
    agg_dict = {'num_issues': 'sum'}

    # Add in 'first' for all other columns
    for col in input_df.columns:
      if col not in agg_dict and col not in groupby_cols:
        agg_dict[col] = 'first'

    # Aggregate the data
    agg_df = grouped_df.agg(agg_dict)

    # Reset the index
    agg_df = agg_df.reset_index()

    # Concatenate the zero count rows with the agg data
    agg_df = pd.concat([agg_df, zero_count_rows])

    # Generate column for the number of pages impacted by an issue
    agg_df['num_pages'] = agg_df.apply(lambda row: agg_df[agg_df['issue_id'] == row.issue_id]['url'].nunique(), axis=1)
    agg_df.reset_index()

    return agg_df

  def run_axe_core_audit_template_aware(self, output_filename: str):
    """Combine repeated axe-core issues.

    Used for detecting template-level errors.

    Args:
        output_filename (str): The output filename.
    """
    # Read the CSV file into a list of dicts
    file_path = self.__build_results_path('axe_core_audit.csv')

    # If file doesn't exist, return
    if not os.path.exists(file_path):
      raise FileNotFoundError(f'File {file_path} does not exist.')

    # Read the CSV file into a DataFrame
    data_frame = pd.read_csv(file_path)

    # Get and update the column order for the page count column
    processed_column_order = list(data_frame.columns)
    processed_column_order.insert(processed_column_order.index('num_issues'), 'num_pages')

    # Group and aggregate the data
    data_frame = self.template_aware_algorithm(
      input_df=data_frame,
      groupby_cols=['base_url', 'id', 'html', 'viewport_size'],
    )

    data_frame = self.sort_with_default(data_frame, ['num_issues'])

    # Write the data to CSV file with original column order
    data_frame.to_csv(
      self.__build_results_path(self.output_prefix + output_filename),
      index=False,
      columns=list(processed_column_order),
    )


if __name__ == '__main__':

  def resolve_results_folder_name() -> str:
    """Resolve the results folder name when being invoked directly."""
    if len(sys.argv) > 1:
      return sys.argv[1]

    # get all the directories in the results folder, sorted naturally in
    # ascending order so that the latest results will be the last item
    convert: Callable[[str], int | str] = lambda text: int(text) if text.isdigit() else text
    existing_results = sorted(
      [d for d in os.listdir('./results') if os.path.isdir(f'./results/{d}')],
      key=lambda key: [convert(c) for c in re.split('([0-9]+)', key)],
    )

    if len(existing_results) == 0:
      raise ValueError('could not determine latest results folder - have you run an audit?')
    return existing_results[-1]

  exporter = DataExporter(resolve_results_folder_name(), False)
