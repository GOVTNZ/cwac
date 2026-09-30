#!/usr/bin/env python

import csv
import os
import shutil
import sys
import typing
from collections.abc import Sequence

from src.output import CSVWriter

page_identifiers: dict[str, int] = {}
csv_headers: dict[str, Sequence[str]] = {}
csv_writer = CSVWriter()


def update_id_columns(row: dict[str, typing.Any]) -> dict[str, typing.Any]:
  """Update the id columns of the csv row."""
  if not row.get('page_id'):
    return row

  if 'url' not in row:
    raise ValueError('cannot determine page id without url column')

  page_id = page_identifiers.setdefault(row['url'], len(page_identifiers) + 1)

  # the audit_id will be "<page id>_<viewport name>"
  if 'audit_id' in row:
    row['audit_id'] = f'{page_id}{row["audit_id"].removeprefix(row["page_id"])}'

  row['page_id'] = page_id

  return row


def merge_csv_file(merged_dir: str, incoming_file: str) -> None:
  """Merge the given csv file into the merged csv file.

  The first "merge" of a file will define which headers are included,
  and all subsequent merges will drop any extra columns.

  The audit_id and page_id columns will be updated if present so that
  they are consistent across files.
  """
  filename = os.path.basename(incoming_file)

  with open(incoming_file, encoding='utf-8-sig') as f:
    csv_reader = csv.DictReader(f)

    if csv_reader.fieldnames is None:
      raise ValueError(f'{incoming_file} cannot be merged without a header')

    # fetch the headers that are allowed for this file, setting them
    # if this is the first time we've seen this type of csv file
    headers = csv_headers.setdefault(filename, csv_reader.fieldnames)

    csv_writer.append_rows(
      f'{merged_dir}/{filename}',
      *[update_id_columns({k: row.get(k, '') for k in headers}) for row in csv_reader],
    )


def merge_results(merged_dir: str, inputs: list[str]) -> None:
  """Merge multiple results into a single result directory."""
  os.mkdir(merged_dir)

  for input_dir in inputs:
    # normalize to remove any trailing slashes
    result_dir = os.path.normpath(input_dir)

    for filestat in os.scandir(result_dir):
      # just skip directories entirely
      if filestat.is_dir():
        continue

      print(f'merging {result_dir}/{filestat.name}')

      if filestat.name.endswith('.csv'):
        merge_csv_file(merged_dir, f'{result_dir}/{filestat.name}')
        continue

      fname, fext = os.path.splitext(filestat.name)
      unique_name = f'{fname}.{os.path.basename(result_dir)}{fext}'

      shutil.copy(f'{result_dir}/{filestat.name}', f'{merged_dir}/{unique_name}')


if len(sys.argv) < 3:
  raise ValueError('must provide two or more results to be merged')

src = os.path.normpath(sys.argv[1])

merge_results(
  os.path.join(os.path.dirname(src), os.path.basename(src) + '-merged'),
  sys.argv[1:],
)
