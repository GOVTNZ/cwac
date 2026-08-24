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

    writer.write_csv_file('file.csv')

    assert os.path.exists('file.csv') is not True

  def test_csv_is_written(self) -> None:
    """Writes each row to a csv file, with a header."""
    writer = CSVWriter()

    writer.add_rows(
      [
        {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
        {'name': 'Alice', 'age': 31, 'location': 'Wellington'},
        {'name': 'Greg', 'age': 23, 'location': 'Auckland'},
      ]
    )

    writer.write_csv_file('file.csv')
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

    writer.add_rows(
      [
        {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
        {'name': 'Alice', 'age': 31, 'location': 'Wellington'},
        {'name': 'Greg', 'age': 23, 'location': 'Auckland'},
      ]
    )

    writer.write_csv_file('file.csv')

    assert os.path.exists('file.csv') is True

    expected = """
      \ufeffname,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_multiple_writes_to_same_file(self) -> None:
    """Writes new rows to a csv file, without duplicating the header."""
    writer = CSVWriter()

    writer.add_rows(
      [
        {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
      ]
    )

    writer.write_csv_file('file.csv')

    assert os.path.exists('file.csv') is True

    writer.add_rows(
      [
        {'name': 'Alice', 'age': 31, 'location': 'Wellington'},
        {'name': 'Greg', 'age': 23, 'location': 'Auckland'},
      ]
    )

    writer.write_csv_file('file.csv')

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()

  def test_column_ordering_is_consistent(self) -> None:
    """Orders columns based on the first row."""
    writer = CSVWriter()

    writer.add_rows(
      [
        {'name': 'Bob', 'age': 20, 'location': 'Wellington'},
        {'age': 31, 'name': 'Alice', 'location': 'Wellington'},
        {'location': 'Auckland', 'age': 23, 'name': 'Greg'},
      ]
    )

    writer.write_csv_file('file.csv')

    assert os.path.exists('file.csv') is True

    expected = """
      name,age,location
      Bob,20,Wellington
      Alice,31,Wellington
      Greg,23,Auckland
    """

    with open('file.csv', encoding='utf-8-sig') as f:
      assert f.read() == textwrap.dedent(expected).lstrip()
