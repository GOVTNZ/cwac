#!/usr/bin/env python
"""Merge multiple CWAC results into a single result directory.

The merged results are written next to the first result, as "<first result>-merged".

usage: merge.py <result dir> <result dir> [<result dir>...]
"""

import os
import shutil
import sys
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
  """Copy the non-csv files of the result, suffixing them with the result name."""
  for filestat in os.scandir(result_dir):
    # directories are skipped, except for screenshots which are copied separately
    if not filestat.is_file() or filestat.name.endswith('.csv'):
      continue

    fname, fext = os.path.splitext(filestat.name)

    shutil.copy(filestat.path, f'{merged_dir}/{fname}.{os.path.basename(result_dir)}{fext}')


def merge_results(merged_dir: str, inputs: list[str]) -> None:
  """Merge multiple results into a single result directory."""
  # normalize to remove any trailing slashes, which would otherwise
  # result in an empty basename when suffixing copied files
  inputs = [os.path.normpath(result_dir) for result_dir in inputs]

  offsets = calculate_offsets(inputs)
  csv_filenames = {f.name for d in inputs for f in os.scandir(d) if f.is_file() and f.name.endswith('.csv')}

  # error if the directory already exists, to avoid mixing in files from a previous merge
  os.mkdir(merged_dir)

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
  if len(sys.argv) < 3:
    sys.exit(f'usage: {sys.argv[0]} <result dir> <result dir> [<result dir>...]')

  src = os.path.normpath(sys.argv[1])

  merge_results(
    os.path.join(os.path.dirname(src), os.path.basename(src) + '-merged'),
    sys.argv[1:],
  )
