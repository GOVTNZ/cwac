"""Tests for XLSX output generation."""

import csv
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from src.output import RAW_DATA_SHEET_NAME
from src.output import STATISTICS_SHEET_NAME
from src.output import generate_axe_core_xlsx_results

MAIN_NS = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
CONTENT_TYPES_NS = {'ct': 'http://schemas.openxmlformats.org/package/2006/content-types'}


def write_axe_core_csv(results_dir: Path, rows: list[dict[str, object]]) -> None:
  """Write an axe-core CSV fixture."""
  results_dir.mkdir(parents=True, exist_ok=True)
  with open(results_dir / 'axe_core_audit.csv', 'w', encoding='utf-8-sig', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)


def sample_rows() -> list[dict[str, object]]:
  """Return sample axe-core rows."""
  return [
    {
      'organisation': 'Agency A',
      'sector': 'government',
      'page_title': 'Home',
      'base_url': 'https://example.govt.nz',
      'url': 'https://example.govt.nz/page-1',
      'viewport_size': "{'width': 1280, 'height': 720}",
      'audit_id': '1_large',
      'page_id': '1',
      'audit_type': 'AxeCoreAudit',
      'issue_id': 'abc123',
      'description': 'Links must have discernible text',
      'target': '//a[1]',
      'num_issues': 2,
      'help': 'Add discernible text',
      'helpUrl': 'https://dequeuniversity.com/rules/axe/4.10/link-name',
      'id': 'link-name',
      'impact': 'serious',
      'html': '<a></a>',
      'tags': 'wcag2a',
      'best-practice': 'No',
    },
    {
      'organisation': 'Agency A',
      'sector': 'government',
      'page_title': 'About',
      'base_url': 'https://example.govt.nz',
      'url': 'https://example.govt.nz/page-2',
      'viewport_size': "{'width': 1280, 'height': 720}",
      'audit_id': '2_large',
      'page_id': '2',
      'audit_type': 'AxeCoreAudit',
      'issue_id': 'def456',
      'description': 'No issues found',
      'target': '',
      'num_issues': 0,
      'help': '',
      'helpUrl': '',
      'id': '',
      'impact': '',
      'html': '',
      'tags': '',
      'best-practice': 'No',
    },
  ]


def parse_xml(archive: zipfile.ZipFile, file_name: str) -> ElementTree.Element:
  """Parse an XML file from a zip archive."""
  return ElementTree.fromstring(archive.read(file_name))


def test_generate_axe_core_xlsx_results_raises_when_source_csv_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  """Raise FileNotFoundError when the source CSV does not exist."""
  monkeypatch.chdir(tmp_path)

  with pytest.raises(FileNotFoundError):
    generate_axe_core_xlsx_results('missing-audit')


def test_generate_axe_core_xlsx_results_creates_expected_workbook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  """Generate a workbook with the expected sheets and formulas."""
  monkeypatch.chdir(tmp_path)
  audit_name = 'audit-run'
  results_dir = tmp_path / 'results' / audit_name
  write_axe_core_csv(results_dir, sample_rows())

  generate_axe_core_xlsx_results(audit_name)

  workbook_path = results_dir / 'axe_core_audit.xlsx'
  assert workbook_path.exists()

  with zipfile.ZipFile(workbook_path) as archive:
    workbook_xml = parse_xml(archive, 'xl/workbook.xml')
    sheet_names = [sheet.attrib['name'] for sheet in workbook_xml.findall('main:sheets/main:sheet', MAIN_NS)]
    assert sheet_names == [RAW_DATA_SHEET_NAME, STATISTICS_SHEET_NAME]

    raw_data_sheet_xml = parse_xml(archive, 'xl/worksheets/sheet1.xml')
    assert raw_data_sheet_xml.findall('.//main:f', MAIN_NS) == []

    statistics_sheet_xml = parse_xml(archive, 'xl/worksheets/sheet2.xml')
    formulas = [formula.text for formula in statistics_sheet_xml.findall('.//main:f', MAIN_NS)]
    assert 'COUNTA(AxeRawData[audit_type])' in formulas
    assert 'SUM(AxeRawData[num_issues])' in formulas
    assert any(formula.startswith('SUMIF(AxeRawData[id],A24') for formula in formulas)


def test_generate_axe_core_xlsx_results_preserves_untrusted_strings_as_literals(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Keep CSV-derived strings as literal cell content without macros or hyperlinks."""
  monkeypatch.chdir(tmp_path)
  audit_name = 'security-audit'
  results_dir = tmp_path / 'results' / audit_name
  rows = sample_rows()
  rows[0]['page_title'] = '=2+2'
  rows[0]['url'] = 'https://malicious.example/looks-like-a-link'
  rows[0]['target'] = '+cmd'
  rows[0]['help'] = '@SUM(1,1)'
  rows[0]['helpUrl'] = '\t=HYPERLINK("https://evil.example")'
  rows[0]['html'] = '-10+20'
  write_axe_core_csv(results_dir, rows)

  generate_axe_core_xlsx_results(audit_name)

  workbook_path = results_dir / 'axe_core_audit.xlsx'
  with zipfile.ZipFile(workbook_path) as archive:
    names = archive.namelist()
    assert 'xl/vbaProject.bin' not in names

    content_types_xml = parse_xml(archive, '[Content_Types].xml')
    content_types = [override.attrib['ContentType'] for override in content_types_xml.findall('ct:Override', CONTENT_TYPES_NS)]
    assert 'application/vnd.ms-office.vbaProject' not in content_types

    raw_data_sheet_xml = parse_xml(archive, 'xl/worksheets/sheet1.xml')
    assert raw_data_sheet_xml.findall('.//main:f', MAIN_NS) == []

    shared_strings_xml = parse_xml(archive, 'xl/sharedStrings.xml')
    shared_strings = [''.join(node.itertext()) for node in shared_strings_xml.findall('main:si', MAIN_NS)]
    assert '=2+2' in shared_strings
    assert 'https://malicious.example/looks-like-a-link' in shared_strings
    assert '+cmd' in shared_strings
    assert '@SUM(1,1)' in shared_strings
    assert '\t=HYPERLINK("https://evil.example")' in shared_strings
    assert '-10+20' in shared_strings

    rels_path = 'xl/worksheets/_rels/sheet1.xml.rels'
    if rels_path in names:
      relationships_xml = parse_xml(archive, rels_path)
      relationship_types = [relationship.attrib['Type'] for relationship in relationships_xml]
      assert not any('hyperlink' in relationship_type for relationship_type in relationship_types)
