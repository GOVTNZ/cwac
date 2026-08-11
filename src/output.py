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

RAW_DATA_SHEET_NAME = 'Raw Data'
STATISTICS_SHEET_NAME = 'Statistics'
RAW_DATA_TABLE_NAME = 'AxeRawData'


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
    'Te Pūnaha Matihiko | Government Digital Delivery Agency',
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

  data_frame = data_frame.sort_values(
    by=['num_issues', 'organisation', 'base_url', 'url'],
    ascending=[False, True, True, True],
  )

  # Write the data to CSV file with original column order
  data_frame.to_csv(
    f'{results_path}/axe_core_audit_template_aware.csv',
    index=False,
    columns=list(processed_column_order),
    encoding='utf-8-sig',
  )


def generate_axe_core_xlsx_results(audit_name: str) -> None:
  """Generate an XLSX report for axe-core results.

  Args:
      audit_name (str): The name of the audit that was just run
  """

  results_path = f'./results/{audit_name}'
  csv_path = f'{results_path}/axe_core_audit.csv'
  xlsx_path = f'{results_path}/axe_core_audit.xlsx'
  data_frame = pd.read_csv(csv_path)
  data_frame = data_frame.fillna('')

  with pd.ExcelWriter(
    xlsx_path,
    engine='xlsxwriter',
    engine_kwargs={
      'options': {
        'strings_to_formulas': False,
        'strings_to_urls': False,
      },
    },
  ) as writer:
    data_frame.to_excel(writer, sheet_name=RAW_DATA_SHEET_NAME, index=False)

    workbook: Any = writer.book
    raw_data_sheet: Any = writer.sheets[RAW_DATA_SHEET_NAME]
    statistics_sheet = workbook.add_worksheet(STATISTICS_SHEET_NAME)
    writer.sheets[STATISTICS_SHEET_NAME] = statistics_sheet

    header_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1', 'border': 1})
    section_header_format = workbook.add_format({'bold': True, 'font_size': 12})
    label_format = workbook.add_format({'bold': True})
    integer_format = workbook.add_format({'num_format': '#,##0'})

    raw_data_sheet.freeze_panes(1, 0)
    raw_data_sheet.autofit(300)
    raw_data_sheet.add_table(
      0,
      0,
      len(data_frame),
      len(data_frame.columns) - 1,
      {
        'name': RAW_DATA_TABLE_NAME,
        'style': 'Table Style Medium 2',
        'columns': [{'header': column_name} for column_name in data_frame.columns],
      },
    )

    summary_formulas = [
      ('Total result rows', f'=COUNTA({RAW_DATA_TABLE_NAME}[audit_type])'),
      ('Total issue count', f'=SUM({RAW_DATA_TABLE_NAME}[num_issues])'),
      ('Rows with issues', f'=COUNTIF({RAW_DATA_TABLE_NAME}[num_issues],">0")'),
      ('Rows with zero issues', f'=COUNTIF({RAW_DATA_TABLE_NAME}[num_issues],0)'),
    ]

    statistics_sheet.set_column('A:A', 30)
    statistics_sheet.set_column('B:B', 18, integer_format)
    statistics_sheet.set_column('D:E', 18)
    statistics_sheet.write('A1', 'Axe-core statistics', section_header_format)

    for row_index, (label, formula) in enumerate(summary_formulas, start=2):
      statistics_sheet.write_string(row_index - 1, 0, label, label_format)
      statistics_sheet.write_formula(row_index - 1, 1, formula, integer_format)

    impact_labels = ['critical', 'serious', 'moderate', 'minor', '']
    statistics_sheet.write('A8', 'Issue count by impact', section_header_format)
    statistics_sheet.write_row('A9', ['Impact', 'Count'], header_format)
    for row_index, impact_label in enumerate(impact_labels, start=10):
      display_label = impact_label if impact_label else 'blank'
      criteria = '""' if impact_label == '' else f'"{impact_label}"'
      statistics_sheet.write_string(row_index - 1, 0, display_label)
      statistics_sheet.write_formula(
        row_index - 1,
        1,
        f'=COUNTIF({RAW_DATA_TABLE_NAME}[impact],{criteria})',
        integer_format,
      )

    best_practice_labels = ['Yes', 'No']
    statistics_sheet.write('A16', 'Issue count by best-practice flag', section_header_format)
    statistics_sheet.write_row('A17', ['Best-practice', 'Count'], header_format)
    for row_index, best_practice_label in enumerate(best_practice_labels, start=18):
      statistics_sheet.write_string(row_index - 1, 0, best_practice_label)
      statistics_sheet.write_formula(
        row_index - 1,
        1,
        f'=COUNTIF({RAW_DATA_TABLE_NAME}[best-practice],"{best_practice_label}")',
        integer_format,
      )

    top_rules = (
      data_frame[data_frame['id'].astype(str) != '']
      .groupby('id', dropna=False)['num_issues']
      .sum()
      .sort_values(ascending=False)
      .head(10)
      .index
      .tolist()
    )
    statistics_sheet.write('A22', 'Top rule IDs by issue count', section_header_format)
    statistics_sheet.write_row('A23', ['Rule ID', 'Issue count'], header_format)
    if top_rules:
      for row_index, rule_id in enumerate(top_rules, start=24):
        statistics_sheet.write_string(row_index - 1, 0, str(rule_id))
        statistics_sheet.write_formula(
          row_index - 1,
          1,
          f'=SUMIF({RAW_DATA_TABLE_NAME}[id],A{row_index},{RAW_DATA_TABLE_NAME}[num_issues])',
          integer_format,
        )
    else:
      statistics_sheet.write_string(23, 0, 'No rule IDs found')
      statistics_sheet.write_number(23, 1, 0, integer_format)

    impact_chart = workbook.add_chart({'type': 'column'})
    impact_chart.add_series(
      {
        'name': 'Issues by impact',
        'categories': f'={STATISTICS_SHEET_NAME}!$A$10:$A$14',
        'values': f'={STATISTICS_SHEET_NAME}!$B$10:$B$14',
        'fill': {'color': '#4F81BD'},
      },
    )
    impact_chart.set_title({'name': 'Issues by impact'})
    impact_chart.set_y_axis({'name': 'Count'})
    statistics_sheet.insert_chart('D2', impact_chart, {'description': 'Column chart showing axe-core issue counts by impact level.'})

    top_rules_chart = workbook.add_chart({'type': 'bar'})
    top_rules_end_row = 23 + max(len(top_rules), 1)
    top_rules_chart.add_series(
      {
        'name': 'Top rules',
        'categories': f'={STATISTICS_SHEET_NAME}!$A$24:$A${top_rules_end_row}',
        'values': f'={STATISTICS_SHEET_NAME}!$B$24:$B${top_rules_end_row}',
        'fill': {'color': '#9BBB59'},
      },
    )
    top_rules_chart.set_title({'name': 'Top rule IDs'})
    top_rules_chart.set_x_axis({'name': 'Issue count'})
    statistics_sheet.insert_chart('D20', top_rules_chart, {'description': 'Bar chart showing the top axe-core rule IDs by issue count.'})
