"""Classes and functions to output data to files, or stdout."""

import csv
import logging
import threading
import time
from typing import Any, ClassVar

import pandas as pd

from config import Config

logger = logging.getLogger('cwac')


class CSVWriter:
  """Simple writer for CSV files."""

  # A dict of file paths that map to locks to
  # prevent multiple threads writing to the same file
  file_locks: ClassVar[dict[str, threading.Lock]] = {}

  # A lock to prevent multiple threads writing to file_locks dict
  lock_for_file_locks = threading.Lock()

  def _get_file_lock(self, path: str) -> threading.Lock:
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

  def append_rows(self, path: str, *rows: dict[Any, Any]) -> None:
    """Append one or more rows to a CSV file.

    Args:
        path (str): path to file
        *rows (dict[str, Any]): one or more rows of data
    """
    if not rows:
      return

    keys = None
    write_header = False

    with self._get_file_lock(path):
      try:
        # attempt to preserve the header order if the file already exists
        with open(path, encoding='utf-8-sig') as csvfile:
          keys = csv.DictReader(csvfile).fieldnames
      except FileNotFoundError:
        write_header = True

      if keys is None:
        keys = list(rows[0].keys())

      with open(path, 'a', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        if write_header:
          writer.writeheader()
        writer.writerows(rows)


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
    'Te Pūnaha Matihiko | Government Digital Delivery Agency',
  )
  print_log(f'Run time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
  print_log('*' * 80)
  print_log('Configuration')
  print_log(f'Audit name: {config.audit_name}')
  print_log('Viewport sizes:')
  for viewport_name, viewport_size in config.viewport_sizes.items():
    print_log(f'    {viewport_name}: {viewport_size}')
  for audit_plugin in config.audit_plugins.values():
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
  csv_writer.append_rows(
    f'./results/{config.audit_name}/progress.csv',
    {
      'time': time.time(),
      'iteration': iteration,
      'total': total,
      'speed': f'{speed:.2f}',
      'percent': percent,
      'elapsed': f'{elapsed}',
      'remaining': f'{time_est}',
    },
  )

  # Print New Line on Complete
  if iteration == total:
    print()


def generate_axe_core_template_aware_results(audit_name: str) -> None:
  """Derive new CSV from axe-core results with added frequency stats.

  Process axe-core audit results, attempting to identify issues with a common
  cause by searching for issues with a similar HTML structure repeated across
  multiple pages. These issues are extracted to a new CSV file for easier
  analysis.

  Issues are grouped by the following fields:
    - base_url: The organization/domain being audited
    - id: The axe-core rule ID (e.g., 'color-contrast', 'image-alt')
    - html: The opening HTML code of the problem element (first 100 chars)
    - viewport_size: The screen size tested (mobile vs desktop issues may differ)

  Extra fields are added to each group:
    - num_issues: No. of issues with same `id` and similar HTML structure
    - num_pages: No. of distinct URLs with the same `id` (axe-core rule violation name)

  Each group becomes a single row in the output CSV. The output is written to
  `axe_core_audit_template_aware.csv` for easier analysis.

  Args:
      audit_name (str): Name of axe-core audit. `results/{audit_name}/axe_core_audit.csv` must exist.

  Returns:
      None. Writes results to results/{audit_name}/axe_core_audit_template_aware.csv
  """
  results_path = f'./results/{audit_name}'

  # Read the raw axe-core audit results into a DataFrame
  data_frame = pd.read_csv(f'{results_path}/axe_core_audit.csv')

  # The generated CSV will have the same columns as the input, plus 'num_pages'
  # (placed before 'num_issues') to indicate how many distinct pages share the
  # same issue.
  processed_column_order = list(data_frame.columns)
  processed_column_order.insert(processed_column_order.index('num_issues'), 'num_pages')

  # Aggregate issues at the template level, combining duplicate issues found
  # on different pages but with identical HTML element structure
  data_frame = template_aware_algorithm(
    input_df=data_frame,
    groupby_cols=['base_url', 'id', 'html', 'viewport_size'],
  )

  # We want to present the most repeated (and therefore likely template-wide)
  # issues first, as these are the most critical to address.
  data_frame = data_frame.sort_values(
    by=['num_issues', 'base_url', 'url'],
    ascending=[False, True, True],
  )

  # Write the aggregated results to CSV file, preserving the prepared column order
  data_frame.to_csv(
    f'{results_path}/axe_core_audit_template_aware.csv',
    index=False,
    columns=list(processed_column_order),
    encoding='utf-8-sig',
  )


def template_aware_algorithm(input_df: pd.DataFrame, groupby_cols: list[str]) -> pd.DataFrame:
  """Update the given DataFrame with metrics columns.

  The metrics columns are:

  1. `num_issues` (WARNING: this function changes column meaning)
    - This column already exists in `input_df`. This function re-uses the column
    but now the value is the count of all issues with identical values for all
    columns in `groupby_cols`. For example, if the groupby_cols are:
      ['base_url', 'id', 'html', 'viewport_size']
    then `num_issues` will be the count of all rows in `input_df` that have the
    same values for those four columns.
  2. `num_pages`
    - A new column added by this function.
    - It's value is the count of distinct URLs which have the same `issue_id` as the current row.

  Args:
      input_df (pd.DataFrame): Raw axe-core audit results.
        Expected columns: base_url, id, html, viewport_size, num_issues,
        issue_id, url, etc.
      groupby_cols (list[str]): Rows in `input_df` with the same values for
        these column names are put in the same group.

  Returns:
      pd.DataFrame: Includes all columns from `input_df` as well as the mertrics columns:
        1. -num_issues (WARNING: this function changes column meaning)
          - Count of all issues with identical values for all columns in `groupby_cols`
        2. num_pages
          - Count of distinct URLs which have the same `issue_id` as the current row.
  """
  # Select pages with no issues. These are preserved unchanged.
  zero_count_rows = input_df[input_df['num_issues'] == 0]

  # Select only the rows where num_issues is not zero, as these are the ones we
  # want to aggregate
  no_zero_count_df = input_df[input_df['num_issues'] != 0]

  # Create groups within the DataFrame based on the values in the specified
  # columns.
  grouped_df = no_zero_count_df.groupby(groupby_cols)

  # Now we use aggregation to reduce each group to a single row.  We define an
  # aggregation (as a Dict) to tell Pandas how to reduce each column.  For the
  # num_issues column, we sum the counts. For all other columns, we take the
  # first occurrence in each group.
  agg_dict = {'num_issues': 'sum'}
  for col in input_df.columns:
    if col not in agg_dict and col not in groupby_cols:
      agg_dict[col] = 'first'
  # agg_dict example: {'num_issues': 'sum', 'base_url': 'first', 'id': 'first', ...}

  # Apply aggregation to reduce each group to a single row
  agg_df = grouped_df.agg(agg_dict)

  # Resetting the index of the DataFrame to ensure that the groupby columns are
  # treated as regular columns rather than index levels. This is important for
  # further processing and for writing the DataFrame to CSV.
  agg_df = agg_df.reset_index()

  # Add back in the rows with no issues which are passed through unchanged.
  agg_df = pd.concat([agg_df, zero_count_rows])

  # Update the whole `num_pages` column in the DataFrame. For each row, the
  # right-hand side calculates:
  #
  # 1. Find all rows with the same issue_id as the current row.
  # 2. Count how many distinct url values are in that set.
  # 3. Put that count into num_pages for that row.
  #
  # So the effect is: every row gets a page-count showing how widely that issue
  # appears across different pages.
  agg_df['num_pages'] = agg_df.apply(lambda row: agg_df[agg_df['issue_id'] == row.issue_id]['url'].nunique(), axis=1)

  # Reset the index of the final DataFrame to ensure a clean output
  agg_df.reset_index()

  return agg_df
