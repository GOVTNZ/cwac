"""Classes and functions to output data to files, or stdout."""

import csv
import logging
import os
import threading
import time
from typing import Any

import pandas as pd

from config import Config

# pylint: disable=too-many-locals

logger = logging.getLogger('cwac')


class CSVWriter:
  """Simple writer for CSV files."""

  # A dict of file paths that map to locks to
  # prevent multiple threads writing to the same file
  file_locks: dict[str, threading.Lock] = {}

  # A lock to prevent multiple threads writing to file_locks dict
  lock_for_file_locks = threading.Lock()

  def __init__(self) -> None:
    """Init variables."""
    self.rows: list[dict[Any, Any]] = []

  def get_file_lock(self, path: str) -> threading.Lock:
    """Get a lock for a file.

    Args:
        path (str): path to file

    Returns:
        threading.Lock: a lock for the file
    """
    with CSVWriter.lock_for_file_locks:
      if path not in CSVWriter.file_locks:
        CSVWriter.file_locks[path] = threading.Lock()
      return CSVWriter.file_locks[path]

  def read_csv(self, path: str) -> list[dict[Any, Any]]:
    """Read a CSV file as a list of dictionaries.

    Args:
        path (str): path to CSV file

    Returns:
        list[dict[Any, Any]]: list of dictionaries
    """
    with self.get_file_lock(path), open(path, 'r', encoding='utf-8-sig') as csvfile:
      reader = csv.DictReader(csvfile)
      rows = list(reader)
    return rows

  def add_row(self, row: dict[Any, Any]) -> None:
    """Add a row to the CSV row buffer.

    Args:
        row (dict[Any, Any]): A dictionary of row contents
    """
    self.rows.append(row)

  def add_rows(self, rows: list[dict[Any, Any]]) -> None:
    """Add a list of rows to the CSV row buffer.

    Args:
        rows (list[dict[Any, Any]]): list of rows of data
    """
    for row in rows:
      self.rows.append(row)

  def write_csv_file(self, path: str, overwrite: bool = False) -> bool:
    """Write data to a CSV file.

    Args:
        path (str): path to write data
        overwrite (bool): overwrite existing file

    Returns:
        bool: True if write successful, else False
    """
    if not self.rows:
      return False

    keys = self.rows[0].keys()

    with self.get_file_lock(path):
      file_exists = False if overwrite else os.path.exists(path)
      file_mode = 'w' if overwrite else 'a'
      with open(path, file_mode, encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        if not file_exists:
          writer.writeheader()
        writer.writerows(self.rows)

    self.rows = []

    return True


def output_init_message(config: Config) -> None:
  """Print the initial message to stdout and the log."""

  def print_log(*message: str) -> None:
    """Print a message and write to the log file.

    Args:
        message (str): message to print
    """
    for line in message:
      print(line)
      logger.info(line)

  print_log(
    '*' * 80,
    'Centralised Web Accessibility Checker (CWAC)',
    'Te Tari Taiwhenua | Department of Internal Affairs',
  )
  print_log(f'Run time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
  print_log('*' * 80)
  print_log('Configuration')
  print_log(f'Audit name: {config.audit_name}')
  print_log('Viewport sizes:')
  for viewport_name, viewport_size in config.viewport_sizes.items():
    print_log(f'    {viewport_name}: {viewport_size}')
  for _, audit_plugin in config.audit_plugins.items():
    print_log(f'Audit plugin: {audit_plugin["class_name"]}')
    for setting_key, setting_value in audit_plugin.items():
      if setting_key == audit_plugin['class_name']:
        continue
      print_log(f'    {setting_key}: {setting_value}')
  print_log(f'Headless: {config.headless}')
  print_log(f'Thread count: {config.thread_count}')
  print_log(f'Browser: {config.browser}')
  print_log(f'Filter to orgs: {config.filter_to_organisations}')
  print_log(f'Filter to urls: {config.filter_to_urls}')
  print_log(f'Max links per domain: {config.max_links_per_domain}')
  print_log(f'Chrome binary location: {config.chrome_binary_location}')
  print_log(f'Chrome driver location: {config.chrome_driver_location}')
  print_log(f'User agent: {config.user_agent}')
  print_log(f'User agent product token: {config.user_agent_product_token}')
  print_log(f'Follow robots.txt: {config.follow_robots_txt}')
  print_log(f'Script timeout: {config.script_timeout} seconds')
  print_log(f'Page load timeout: {config.page_load_timeout} seconds')
  print_log(f'Delay between page_loads: {config.delay_between_page_loads} seconds')
  print_log(f'Delay between viewports: {config.delay_between_viewports} seconds')
  print_log(f'Delay after page load: {config.delay_after_page_load} seconds')
  print_log(f'Only allow HTTPS: {config.only_allow_https}')
  print_log(f'Perform header checks: {config.perform_header_check}')
  print_log(f'Shuffle base urls: {config.shuffle_base_urls}')
  print_log(f'Base urls visit path: {config.base_urls_visit_path}')
  print_log(f'Recording unexpected response codes: {config.record_unexpected_response_codes}')
  print_log('*' * 80)


def generate_time_str_from_mins(mins: float) -> str:
  """Generate a time string from minutes.

  Args:
      mins (float): minutes

  Returns:
      str: time string
  """
  hours = mins / 60
  mins = mins % 60
  return f'{int(hours)}h {int(mins)}m'


def print_progress_bar(
  config: Config,
  iteration: int,
  total: int,
  start_time: float = 1,
) -> None:
  """Call in a loop to create terminal progress bar.

  Args:
      config (Config): config object
      iteration (int): current iteration
      total (int): total iterations
      start_time (float): time the program started
  """
  length: int = 20
  decimals: int = 1

  try:
    percentage_calc = 100 * (iteration / float(total))
  except ZeroDivisionError:
    percentage_calc = 0

  percent = ('{0:.' + str(decimals) + 'f}').format(percentage_calc)

  try:
    filled_length = int(length * iteration // total)
  except ZeroDivisionError:
    filled_length = 0
  progress_bar = '█' * filled_length + '-' * (length - filled_length)
  speed = iteration / (time.time() - start_time)
  if speed == 0:
    speed = 0.0001
  elapsed = generate_time_str_from_mins((time.time() - start_time) / 60)
  time_est = generate_time_str_from_mins((total - iteration) / speed / 60)
  output = f'|{progress_bar}| {percent}% p:{iteration}/{total} v:{speed:.2f}p/s t:{elapsed}  t-:{time_est}'
  print(output + '      ')

  # Write progress data to CSV file
  csv_writer = CSVWriter()

  output_row = {
    'time': time.time(),
    'iteration': iteration,
    'total': total,
    'speed': f'{speed:.2f}',
    'percent': percent,
    'elapsed': f'{elapsed}',
    'remaining': f'{time_est}',
  }

  csv_writer.add_row(output_row)

  csv_writer.write_csv_file(f'./results/{config.audit_name}/progress.csv')

  # Print New Line on Complete
  if iteration == total:
    print()


def generate_axe_core_template_aware_results(audit_name: str) -> None:
  """Combine repeated axe-core issues.

  Used for detecting template-level errors.

  Args:
      audit_name (str): The name of the audit that was just run
  """

  def sort_with_default(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Sort the data frame by the given columns in descending order followed by default columns for consistency."""
    ascending = [False] * len(columns) + [True, True, True]
    columns = list(
      filter(
        lambda key: key in df.columns,
        columns + ['organisation', 'base_url', 'url'],
      )
    )

    return df.sort_values(by=columns, ascending=ascending[0 : len(columns)])

  def template_aware_algorithm(input_df: pd.DataFrame, groupby_cols: list[str]) -> pd.DataFrame:
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

  results_path = f'./results/{audit_name}'

  # Read the CSV file into a DataFrame
  data_frame = pd.read_csv(f'{results_path}/axe_core_audit.csv')

  # Get and update the column order for the page count column
  processed_column_order = list(data_frame.columns)
  processed_column_order.insert(processed_column_order.index('num_issues'), 'num_pages')

  # Group and aggregate the data
  data_frame = template_aware_algorithm(
    input_df=data_frame,
    groupby_cols=['base_url', 'id', 'html', 'viewport_size'],
  )

  data_frame = sort_with_default(data_frame, ['num_issues'])

  # Write the data to CSV file with original column order
  data_frame.to_csv(
    f'{results_path}/axe_core_audit_template_aware.csv',
    index=False,
    columns=list(processed_column_order),
  )
