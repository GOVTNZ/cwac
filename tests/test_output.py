"""Tests the behaviour of the output classes and functions."""

import os
import textwrap

import pytest

from src.output import CSVWriter


@pytest.mark.usefixtures('fs')
class TestCSVWriter:
  """Tests writing csv files using the CSVWriter class."""

  def test_csv_is_not_written_when_no_rows(self) -> None:
    """Skips writing a file when no rows have been added."""
    writer = CSVWriter()

    writer.append_rows('file.csv')

    assert os.path.exists('file.csv') is not True

  def test_csv_is_written(self) -> None:
    """Writes each row to a csv file, with a header."""
    writer = CSVWriter()

    writer.append_rows(
      'file.csv',
      {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
      {'name': 'Alice', 'age': 31, 'location': 'Wellington'},
      {'name': 'Greg', 'age': 23, 'location': 'Auckland'},
    )

    assert os.path.exists('file.csv') is True

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_csv_is_written_with_bom(self) -> None:
    """Writes a bom before the header row."""
    writer = CSVWriter()

    writer.append_rows(
      'file.csv',
      {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
      {'name': 'Alice', 'age': 31, 'location': 'Wellington'},
      {'name': 'Greg', 'age': 23, 'location': 'Auckland'},
    )

    assert os.path.exists('file.csv') is True

    expected = """
      \ufeffname,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_appends_to_existing_file(self) -> None:
    """Writes new rows to a csv file, without duplicating the header."""
    writer = CSVWriter()

    writer.append_rows(
      'file.csv',
      {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
    )

    assert os.path.exists('file.csv') is True

    writer.append_rows(
      'file.csv',
      {'name': 'Alice', 'age': 31, 'location': 'Wellington'},
      {'name': 'Greg', 'age': 23, 'location': 'Auckland'},
    )

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_ignores_missing_columns(self) -> None:
    """Ignores columns missing in subsequent rows."""
    writer = CSVWriter()

    writer.append_rows(
      'file.csv',
      {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
      {'name': 'Alice', 'age': 31},
      {'age': 23, 'location': 'Auckland'},
    )

    assert os.path.exists('file.csv') is True

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,
      ,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_ignores_missing_columns_across_writes(self) -> None:
    """Ignores columns missing in subsequent rows across multiple writes."""
    writer = CSVWriter()

    writer.append_rows(
      'file.csv',
      {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
      {'name': 'Alice', 'age': 31},
    )

    assert os.path.exists('file.csv') is True

    writer.append_rows(
      'file.csv',
      {'age': 23, 'location': 'Auckland'},
    )

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,
      ,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_raises_extra_columns(self) -> None:
    """Errors when rows have extra columns."""
    writer = CSVWriter()

    with pytest.raises(ValueError):
      writer.append_rows(
        'file.csv',
        {'name': 'Bob', 'age': 20},
        {'name': 'Alice', 'age': 31, 'location': 'Wellington'},
        {'name': 'Greg', 'age': 23, 'location': 'Auckland'},
      )

    # the file will still end up being created due to the open mode
    assert os.path.exists('file.csv')

  def test_column_ordering_is_consistent(self) -> None:
    """Orders columns based on the first row."""
    writer = CSVWriter()

    writer.append_rows(
      'file.csv',
      {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
      {'age': 31, 'name': 'Alice', 'location': 'Wellington'},
      {'location': 'Auckland', 'age': 23, 'name': 'Greg'},
    )

    assert os.path.exists('file.csv') is True

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_preserves_column_order(self) -> None:
    """Preserves column order when writing to an existing file."""
    writer = CSVWriter()

    writer.append_rows(
      'file.csv',
      {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
      {'age': 31, 'name': 'Alice', 'location': 'Wellington'},
    )

    assert os.path.exists('file.csv') is True

    writer.append_rows(
      'file.csv',
      {'location': 'Auckland', 'age': 23, 'name': 'Greg'},
    )

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()
