"""Tests the behaviour of the Config class."""

import json
import platform
import textwrap

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture

from config import Config, SiteData


@pytest.fixture(autouse=True)
def setup_filesystem(fs: FakeFilesystem) -> None:
  """Set up the filesystem."""
  fs.add_real_file('package.json', read_only=False)
  fs.makedirs('base_urls/nohead')
  fs.makedirs('base_urls/visit')


def mock_platform(mocker: MockerFixture, system: str, machine: str) -> None:
  """Patch platform.uname to return the specified system and machine."""
  # uname_result is a "named tuple"-like object of 6 values, but it handles the
  # last value lazily so it actually only allows being passed 5 values
  # noinspection PyArgumentList
  mocker.patch('platform.uname', return_value=platform.uname_result(system, '', '', '', machine))


def test_loading_missing_config_raises_file_not_found() -> None:
  """Raises FileNotFoundError if the config file is missing."""
  with pytest.raises(FileNotFoundError):
    Config('does/not/exist')


def test_valid_config_is_successfully_loaded(fs: FakeFilesystem) -> None:
  """Validates that the config is loaded correctly."""
  fs.add_real_file('config/config_default.json')

  config = Config('config_default.json')

  with open('config/config_default.json', encoding='utf-8') as f:
    raw = json.load(f)

    # assert a few of the properties match, as a sense check
    assert config.headless == raw['headless']
    assert config.thread_count == raw['thread_count']
    assert config.user_agent == raw['user_agent']
    assert config.base_urls_visit_path == raw['base_urls_visit_path']


class TestChromeLocationsAutoResolution:
  """Tests automatic resolution of Chrome binary and driver locations."""

  @pytest.mark.parametrize(
    'system,machine,expected_binary_location,expected_driver_location',
    [
      (
        'Linux',
        'x86_64',
        './chrome/linux-123-abc/chrome-linux64/',
        './chromedriver/linux-123-abc/chromedriver-linux64',
      ),
      (
        'Darwin',
        'arm64',
        './chrome/mac_arm-123-abc/chrome-mac-arm64/',
        './chromedriver/mac_arm-123-abc/chromedriver-mac-arm64',
      ),
    ],
  )
  # pylint: disable-next=too-many-arguments,too-many-positional-arguments
  def test_auto_resolves_for_supported_platforms(  # noqa: PLR0913, PLR0917
    self,
    fs: FakeFilesystem,
    mocker: MockerFixture,
    system: str,
    machine: str,
    expected_binary_location: str,
    expected_driver_location: str,
  ) -> None:
    """Resolves the correct paths for OSs and architectures that are supported for automatic resolution."""
    fs.add_real_file('config/config_default.json')

    with open('package.json', 'w+', encoding='utf-8') as f:
      f.write(json.dumps({'config': {'chromeVersion': '123-abc'}}))

    mock_platform(mocker, system, machine)

    config = Config('config_default.json')

    assert config.chrome_binary_location.startswith(expected_binary_location)
    assert config.chrome_driver_location.startswith(expected_driver_location)

  @pytest.mark.parametrize(
    'system,machine',
    [
      ('Linux', 'arm64'),
      ('Darwin', 'x86_64'),
      ('Windows', 'x86_64'),
      ('Windows', 'arm64'),
    ],
  )
  def test_auto_raises_for_unsupported_platforms(
    self,
    fs: FakeFilesystem,
    mocker: MockerFixture,
    system: str,
    machine: str,
  ) -> None:
    """Raises an error when running on an OS or architecture that is not supported for automatic resolution."""
    fs.add_real_file('config/config_default.json')

    with open('package.json', 'w+', encoding='utf-8') as f:
      f.write(json.dumps({'config': {'chromeVersion': '123-abc'}}))

    mock_platform(mocker, system, machine)

    with pytest.raises(ValueError):
      Config('config_default.json')

  def test_manual_locations_are_preserved(self, fs: FakeFilesystem) -> None:
    """Preserves manually configured chrome_binary_location and chrome_driver_location."""
    fs.add_real_file('config/config_default.json', read_only=False)

    with open('config/config_default.json', 'r+', encoding='utf-8') as f:
      c = {
        **json.load(f),
        'chrome_binary_location': '/home/user/.cache/selenium/chrome/linux64/139.0.7258.68',
        'chrome_driver_location': '/home/user/.cache/selenium/chromedriver/linux64/139.0.7258.68',
      }
      f.seek(0)
      json.dump(c, f)
      f.truncate()

    with open('package.json', 'w+', encoding='utf-8') as f:
      f.write(json.dumps({'config': {'chromeVersion': '123-abc'}}))

    config = Config('config_default.json')

    assert config.chrome_binary_location == '/home/user/.cache/selenium/chrome/linux64/139.0.7258.68'
    assert config.chrome_driver_location == '/home/user/.cache/selenium/chromedriver/linux64/139.0.7258.68'


class TestUrlLoading:
  """Tests the loading of urls from csv files."""

  @pytest.fixture(autouse=True)
  def setup_base_urls_csvs(self, fs: FakeFilesystem) -> None:
    """Set up some csvs with urls and various columns."""
    fs.create_file(
      'base_urls/visit/my urls.csv',
      contents=textwrap.dedent("""
        organisation,url,sector,region,priority
        ACME,https://acme.com/finance,Finance,Wellington,High
        ACME,https://acme.com/hr,Human Resources,Wellington,Medium
        ACME,https://acme.com/legal,Legal,Auckland,Low
        Stark Industries,https://stark.com/rd,R&D,Auckland,High
        Stark Industries,https://stark.com/finance,Finance,Overseas,Medium
      """).strip(),
    )
    fs.create_file(
      'base_urls/visit/q3_2024_urls.csv',
      contents=textwrap.dedent("""
        organisation,url,sector,region,priority
        Wayne Enterprises,https://wayne.com/security,Security,Wellington,High
        Wayne Enterprises,https://wayne.com/finance,Finance,Auckland,Medium
        Wayne Enterprises,https://wayne.com/legal,Legal,Wellington,Low
        Cyberdyne Systems,https://cyberdyne.com/rd,R&D,Auckland,High
        Cyberdyne Systems,https://cyberdyne.com/security,Security,Wellington,Medium
      """).strip(),
    )
    fs.create_file(
      'base_urls/visit/theirs_urls.csv',
      contents=textwrap.dedent("""
        organisation,url,sector,region,priority
        Umbrella Corp,https://umbrella.com,R&D,Overseas,High
        Buy 'n' Large,https://bnl.com/,Sales,Overseas,Medium
        Umbrella Corp,https://umbrella.com/hr,Human Resources,Overseas,Low
        Umbrella Corp,https://umbrella.com/legal,Legal,Wellington,Medium
        Buy 'n' Large,https://bnl.com/finance,Finance,Auckland,High
      """).strip(),
    )

  def test_urls_are_loaded(self, fs: FakeFilesystem) -> None:
    """Loads urls from csv files."""
    fs.add_real_file('config/config_default.json')

    # remove a csv to reduce the amount of sites we have to list
    fs.remove('base_urls/visit/my urls.csv')

    config = Config('config_default.json')

    expected: list[SiteData] = [
      {
        'url': 'https://bnl.com/',
        'supports_head': True,
        'columns': {
          'organisation': "Buy 'n' Large",
          'url': 'https://bnl.com/',
          'sector': 'Sales',
          'region': 'Overseas',
          'priority': 'Medium',
        },
      },
      {
        'url': 'https://bnl.com/finance',
        'supports_head': True,
        'columns': {
          'organisation': "Buy 'n' Large",
          'url': 'https://bnl.com/finance',
          'sector': 'Finance',
          'region': 'Auckland',
          'priority': 'High',
        },
      },
      {
        'url': 'https://cyberdyne.com/rd',
        'supports_head': True,
        'columns': {
          'organisation': 'Cyberdyne Systems',
          'url': 'https://cyberdyne.com/rd',
          'sector': 'R&D',
          'region': 'Auckland',
          'priority': 'High',
        },
      },
      {
        'url': 'https://cyberdyne.com/security',
        'supports_head': True,
        'columns': {
          'organisation': 'Cyberdyne Systems',
          'url': 'https://cyberdyne.com/security',
          'sector': 'Security',
          'region': 'Wellington',
          'priority': 'Medium',
        },
      },
      {
        'url': 'https://umbrella.com',
        'supports_head': True,
        'columns': {
          'organisation': 'Umbrella Corp',
          'url': 'https://umbrella.com',
          'sector': 'R&D',
          'region': 'Overseas',
          'priority': 'High',
        },
      },
      {
        'url': 'https://umbrella.com/hr',
        'supports_head': True,
        'columns': {
          'organisation': 'Umbrella Corp',
          'url': 'https://umbrella.com/hr',
          'sector': 'Human Resources',
          'region': 'Overseas',
          'priority': 'Low',
        },
      },
      {
        'url': 'https://umbrella.com/legal',
        'supports_head': True,
        'columns': {
          'organisation': 'Umbrella Corp',
          'url': 'https://umbrella.com/legal',
          'sector': 'Legal',
          'region': 'Wellington',
          'priority': 'Medium',
        },
      },
      {
        'url': 'https://wayne.com/finance',
        'supports_head': True,
        'columns': {
          'organisation': 'Wayne Enterprises',
          'url': 'https://wayne.com/finance',
          'sector': 'Finance',
          'region': 'Auckland',
          'priority': 'Medium',
        },
      },
      {
        'url': 'https://wayne.com/legal',
        'supports_head': True,
        'columns': {
          'organisation': 'Wayne Enterprises',
          'url': 'https://wayne.com/legal',
          'sector': 'Legal',
          'region': 'Wellington',
          'priority': 'Low',
        },
      },
      {
        'url': 'https://wayne.com/security',
        'supports_head': True,
        'columns': {
          'organisation': 'Wayne Enterprises',
          'url': 'https://wayne.com/security',
          'sector': 'Security',
          'region': 'Wellington',
          'priority': 'High',
        },
      },
    ]

    assert sorted(config.audit_subjects, key=lambda site: site['url']) == expected

  def test_urls_are_loaded_from_set_path(self, fs: FakeFilesystem) -> None:
    """Loads urls from csv files within a directory pointed to by config."""
    fs.add_real_file('config/config_default.json', read_only=False)

    with open('config/config_default.json', 'r+', encoding='utf-8') as f:
      c = {**json.load(f), 'base_urls_visit_path': './base_urls/alternative/'}
      f.seek(0)
      json.dump(c, f)
      f.truncate()

    fs.makedirs('base_urls/alternative')
    fs.rename('base_urls/visit/my urls.csv', 'base_urls/alternative/my urls.csv')

    config = Config('config_default.json')

    assert sorted([site['url'] for site in config.audit_subjects]) == [
      'https://acme.com/finance',
      'https://acme.com/hr',
      'https://acme.com/legal',
      'https://stark.com/finance',
      'https://stark.com/rd',
    ]
