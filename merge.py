#!/usr/bin/env python
"""Merge multiple CWAC results into a single result directory.

By default the merged results are written next to the first result, as
"<first result>-merged", unless an output directory is given with -o/--output-dir.
"""

import argparse
import os
import shutil
from collections.abc import Callable

import pandas as pd

from src.output import generate_axe_core_template_aware_results

# columns whose values are prefixed with the page id, i.e. "<page id>_<viewport name>"
PREFIXED_ID_COLUMNS = ('audit_id', 'screenshot')

SKIPPED_CSV_FILENAMES = (
  # progress is specific to each scan, so doesn't make sense to merge
  'progress.csv',
  # this is regenerated from the merged axe-core results instead, so
  # that issues are grouped across all the results
  'axe_core_audit_template_aware.csv',
)


def read_csv(path: str, usecols: Callable[[str], bool] | None = None) -> pd.DataFrame:
  """Read a results csv file, keeping all values as they are written."""
  return pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig', usecols=usecols)


def shift_page_id(value: str, offset: int) -> str:
  """Shift the page id at the start of the value by the given offset."""
  if not value:
    return value

  page_id, sep, rest = value.partition('_')

  return f'{int(page_id) + offset}{sep}{rest}'


def max_page_id(result_dir: str) -> int:
  """Find the highest page id used across the csv files of the result."""
  highest = 0

  for filestat in os.scandir(result_dir):
    if not filestat.is_file() or not filestat.name.endswith('.csv'):
      continue

    df = read_csv(filestat.path, usecols=lambda column: column == 'page_id')

    if 'page_id' not in df:
      continue

    highest = max(highest, max((int(page_id) for page_id in df['page_id'] if page_id), default=0))

  return highest


def calculate_offsets(inputs: list[str]) -> dict[str, int]:
  """Calculate how much to shift the page ids of each result by.

  Page ids start from 1 in every result, so each result is offset by
  the number of pages in the results before it to keep them unique.

  The same url appearing in multiple results is kept as separate pages,
  rather than given the same page id, to match how CWAC handles the same
  url being crawled from multiple base urls within a single result.
  """
  offsets: dict[str, int] = {}
  total = 0

  for result_dir in inputs:
    offsets[result_dir] = total
    total += max_page_id(result_dir)

  return offsets


def merge_csv_file(merged_dir: str, inputs: list[str], offsets: dict[str, int], filename: str) -> None:
  """Merge the csv file of the given name from each of the results.

  The merged file will include every column seen across the results,
  with columns missing from a result being left empty, and the page id
  columns will be shifted so that they are unique across the results.
  """
  frames = []

  for result_dir in inputs:
    if not os.path.isfile(f'{result_dir}/{filename}'):
      continue

    df = read_csv(f'{result_dir}/{filename}')

    for column in ('page_id', *PREFIXED_ID_COLUMNS):
      if column in df:
        df[column] = df[column].map(lambda value, offset=offsets[result_dir]: shift_page_id(value, offset))

    frames.append(df)

  pd.concat(frames).fillna('').to_csv(f'{merged_dir}/{filename}', index=False, encoding='utf-8-sig')


def copy_screenshots(merged_dir: str, result_dir: str, offset: int) -> None:
  """Copy the screenshots of the result, shifting the page id they're named after."""
  if not os.path.isdir(f'{result_dir}/screenshots'):
    return

  os.makedirs(f'{merged_dir}/screenshots', exist_ok=True)

  for filestat in os.scandir(f'{result_dir}/screenshots'):
    shutil.copy(filestat.path, f'{merged_dir}/screenshots/{shift_page_id(filestat.name, offset)}')


def copy_other_files(merged_dir: str, result_dir: str) -> None:
  """Copy the non-csv files of the result, suffixing them with the result name.

  Files in subdirectories are copied into the same subdirectory of the merged
  result, except for screenshots which are copied separately.
  """
  for dirpath, dirnames, filenames in os.walk(result_dir):
    reldir = os.path.relpath(dirpath, result_dir)

    if reldir == '.' and 'screenshots' in dirnames:
      dirnames.remove('screenshots')

    os.makedirs(os.path.normpath(f'{merged_dir}/{reldir}'), exist_ok=True)

    for filename in filenames:
      # csv files at the top level are merged separately
      if reldir == '.' and filename.endswith('.csv'):
        continue

      fname, fext = os.path.splitext(filename)

      shutil.copy(
        f'{dirpath}/{filename}',
        os.path.normpath(f'{merged_dir}/{reldir}/{fname}.{os.path.basename(result_dir)}{fext}'),
      )


def merge_results(merged_dir: str, inputs: list[str]) -> None:
  """Merge multiple results into a single result directory."""
  # normalize to remove any trailing slashes, which would otherwise
  # result in an empty basename when suffixing copied files
  inputs = [os.path.normpath(result_dir) for result_dir in inputs]

  # the basename is used to make copied files unique, so it must be unique too;
  # this also catches the same result being given more than once
  if len({os.path.basename(result_dir) for result_dir in inputs}) != len(inputs):
    raise ValueError('cannot merge results that have the same directory name')

  # otherwise the merged result would end up being copied into itself
  for result_dir in inputs:
    if os.path.commonpath([os.path.abspath(merged_dir), os.path.abspath(result_dir)]) == os.path.abspath(result_dir):
      raise ValueError(f'cannot write the merged results inside of {result_dir}')

  offsets = calculate_offsets(inputs)
  csv_filenames = {f.name for d in inputs for f in os.scandir(d) if f.is_file() and f.name.endswith('.csv')}

  # error if the directory already exists, to avoid mixing in files from a previous merge
  os.makedirs(merged_dir)

  for filename in sorted(csv_filenames.difference(SKIPPED_CSV_FILENAMES)):
    print(f'merging {filename}')
    merge_csv_file(merged_dir, inputs, offsets, filename)

  if os.path.isfile(f'{merged_dir}/axe_core_audit.csv'):
    print('generating axe_core_audit_template_aware.csv')
    generate_axe_core_template_aware_results(merged_dir)

  for result_dir in inputs:
    print(f'copying files from {result_dir}')
    copy_other_files(merged_dir, result_dir)
    copy_screenshots(merged_dir, result_dir, offsets[result_dir])


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument('results', nargs='+', help='the result directories to merge')
  parser.add_argument(
    '-o',
    '--output-dir',
    help='the directory to write the merged results to (default: "<first result>-merged")',
  )
  args = parser.parse_args()

  if len(args.results) < 2:
    parser.error('must provide two or more results to merge')

  output_dir = args.output_dir

  if output_dir is None:
    src = os.path.normpath(args.results[0])
    output_dir = os.path.join(os.path.dirname(src), os.path.basename(src) + '-merged')

  merge_results(output_dir, args.results)
