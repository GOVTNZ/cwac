"""Basic tests of the endpoints relating to scans"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

import os

from flask.testing import FlaskClient
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture

from web import CWACAlreadyRunningError, CWACManager, cwac_manager


def build_audit_results_log_content(date: str) -> str:
  """Build the contents of an audit_results.log file."""
  return '\n'.join(
    [
      f'[{{{date}T12:00:00+1200}} INFO output.py : 113 ] print_log *************************************************************** MainThread',  # noqa: E501, pylint: disable=line-too-long
      f'[{{{date}T12:00:00+1200}} INFO output.py : 113 ] print_log Centralised Web Accessibility Checker (CWAC) MainThread',  # noqa: E501, pylint: disable=line-too-long
      f'[{{{date}T12:00:00+1200}} INFO output.py : 113 ] print_log Te Tari Taiwhenua | Department of Internal Affairs MainThread',  # noqa: E501, pylint: disable=line-too-long
      f'[{{{date}T12:00:00+1200}} INFO output.py : 113 ] print_log Run time: {date} 12:00:00 MainThread',
      f'[{{{date}T12:00:00+1200}} INFO output.py : 113 ] print_log *************************************************************** MainThread',  # noqa: E501, pylint: disable=line-too-long
      f'[{{{date}T12:00:39+1200}} INFO   cwac.py : 151 ]  __init__ CWAC complete! MainThread',
    ]
  )


def has_flash(client: FlaskClient, message: str, typ: str) -> bool:
  """Check that a flash message of the given type exists in the session."""
  with client.session_transaction() as session:
    return any(flash == (typ, message) for flash in session.get('_flashes', []))


class TestNewScan:
  """Tests for the GET /scans/new endpoint."""

  def test_missing_config_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory is missing.

    The page should say that no config files were found, and not allow
    starting a scan.
    """

    response = client.get('/scans/new')

    assert response.status_code == 200

    assert b'No config files found' in response.data
    # todo: assert "start scan" button is disabled

  def test_empty_config_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory is empty.

    The page should say that no config files were found, and not allow
    starting a scan.
    """

    os.mkdir('config')

    response = client.get('/scans/new')

    assert response.status_code == 200

    assert b'No config files found' in response.data
    # todo: assert "start scan" button is disabled

  def test_config_files_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the config/ directory has config files.

    The files should be listed as options to select for use in a scan.
    """

    fs.add_real_file('config/config_default.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_linux.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_macos.json')

    response = client.get('/scans/new')

    assert response.status_code == 200

    assert b'No config files found' not in response.data

    assert b'<option>config_default.json</option>' in response.data
    assert b'<option>config_linux.json</option>' in response.data
    assert b'<option>config_macos.json</option>' in response.data

  def test_only_json_files_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the config/ directory has other files.

    Only .json files should be listed as options for a scan.
    """

    fs.add_real_file('config/config_default.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_linux.txt')
    fs.add_real_file('config/config_default.json', target_path='config/config_macos.jsonc')

    response = client.get('/scans/new')

    assert response.status_code == 200

    assert b'No config files found' not in response.data

    assert b'<option>config_default.json</option>' in response.data
    assert b'config_linux.txt' not in response.data
    assert b'config_macos.jsonc' not in response.data


class TestCreateScan:
  """Tests for the POST /scan endpoint."""

  def test_config_is_required(self, client: FlaskClient, mocker: MockerFixture) -> None:
    """Test handling requests that do not have a "config" string in their data.

    An error should be returned without a scan being started.
    """
    spy = mocker.spy(cwac_manager, 'start')
    spy.side_effect = lambda _: None  # avoid actually starting a run

    response = client.post('/scans')

    assert response.status_code == 422
    assert spy.called is False

    response = client.post('/scans', data={'config': ''})

    assert response.status_code == 422
    assert spy.called is False

  def test_a_scan_can_be_started(self, client: FlaskClient, mocker: MockerFixture) -> None:
    """Test handling a valid request to start a scan when one is not already in progress.

    The scan should be started, and the user redirected to the progress page.
    """
    spy = mocker.spy(cwac_manager, 'start')
    spy.side_effect = lambda _: None  # avoid actually starting a run

    response = client.post('/scans', data={'config': 'config_default.json'})

    assert response.status_code == 302
    assert response.location == '/scans/progress'
    assert spy.called is True

    assert has_flash(client, 'scan started', 'success')

  def test_a_second_scan_cannot_be_started(self, client: FlaskClient, mocker: MockerFixture) -> None:
    """Test handling a valid request to start a scan when one is already in progress.

    An error should be returned without a (new) scan being started.
    """
    # todo: we should ideally ensure the "state" property returns "running" too
    spy = mocker.spy(cwac_manager, 'start')
    spy.side_effect = CWACAlreadyRunningError

    response = client.post('/scans', data={'config': 'config_default.json'})

    assert response.status_code == 422
    assert spy.called is True

    assert b'scan already in progress' in response.data

    # todo: assert the in-progress scan has not been changed, nor a second one started


class TestViewScan:
  """Tests for the GET /scans/progress endpoint."""

  def test_a_scan_must_be_running(self, client: FlaskClient) -> None:
    """Test handling when a CWAC scan has not been started.

    The user should be redirected to the "new scan" page with a warning.
    """
    response = client.get('/scans/progress')

    assert response.status_code == 302
    assert response.location == '/scans/new'

    assert has_flash(client, 'no scan in progress', 'warning')


class TestScanProgressUpdate:
  """Tests for the GET /scans/progress endpoint."""

  def test_an_idle_state_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the scan state is idle.

    An empty object should be returned as JSON.
    """
    response = client.get('/scans/progress/update')

    assert response.status_code == 200

    assert response.json == {}

  def test_the_latest_progress_update_and_logs_are_returned(
    self,
    client: FlaskClient,
    fs: FakeFilesystem,
    mocker: MockerFixture,
  ) -> None:
    """Test handling when a scan is in progress.

    The JSON response should include the latest scan progress update and the logs.
    """
    fs.create_file(
      'results/2025-01-01_12-00-00_audit_results/2025-01-01_12-00-00_audit_results.log',
      contents=build_audit_results_log_content('2025-01-03'),
    )
    fs.create_file(
      'results/2025-01-01_12-00-00_audit_results/chromedriver.log',
      contents='\n'.join(
        [
          '[1759967794.041][INFO]: Starting ChromeDriver 122.0.6261.39 (...) on port 39241',
          '[1759967794.041][INFO]: Please see ... for suggestions on keeping ChromeDriver safe.',
        ]
      ),
    )
    mocker.patch.object(CWACManager, 'state', new_callable=mocker.PropertyMock, return_value='running')
    mocker.patch.object(
      cwac_manager,
      'audit_log_file_path',
      return_value='results/2025-01-01_12-00-00_audit_results/2025-01-01_12-00-00_audit_results.log',
    )
    mocker.patch.object(
      cwac_manager,
      'chromedriver_log_file_path',
      return_value='results/2025-01-01_12-00-00_audit_results/chromedriver.log',
    )
    mocker.patch.object(
      cwac_manager,
      'progress',
      return_value={
        'logs': {
          'audit': build_audit_results_log_content('2025-01-03'),
          'chromedriver': '\n'.join(
            [
              '[1759967794.041][INFO]: Starting ChromeDriver 122.0.6261.39 (...) on port 39241',
              '[1759967794.041][INFO]: Please see ... for suggestions on keeping ChromeDriver safe.',
            ]
          ),
        },
        'elapsed': '0h 2m',
        'iteration': 7,
        'percent': '87.5',
        'remaining': '0h 1m',
        'speed': '0.14',
        'time': 1757294135.263283,
        'total': 8,
      },
    )

    response = client.get('/scans/progress/update')

    assert response.status_code == 200
    assert response.json == {
      'logs': {
        'audit': build_audit_results_log_content('2025-01-03'),
        'chromedriver': '\n'.join(
          [
            '[1759967794.041][INFO]: Starting ChromeDriver 122.0.6261.39 (...) on port 39241',
            '[1759967794.041][INFO]: Please see ... for suggestions on keeping ChromeDriver safe.',
          ]
        ),
      },
      'elapsed': '0h 2m',
      'iteration': 7,
      'percent': '87.5',
      'remaining': '0h 1m',
      'speed': '0.14',
      'time': 1757294135.263283,
      'total': 8,
      'state': 'running',
    }
