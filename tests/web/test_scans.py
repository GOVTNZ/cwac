"""Basic tests of the endpoints relating to scans"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

import os

from flask.testing import FlaskClient
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture

from web import CWACAlreadyRunningError, cwac_manager


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
    """Testing handling when a CWAC scan has not been started.

    The user should be redirected to the "new scan" page with a warning.
    """
    response = client.get('/scans/progress')

    assert response.status_code == 302
    assert response.location == '/scans/new'

    assert has_flash(client, 'no scan in progress', 'warning')
