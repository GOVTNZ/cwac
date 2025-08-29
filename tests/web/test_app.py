"""Basic tests of the web application"""

import os

import pytest
from flask.testing import FlaskClient
from pyfakefs.fake_filesystem import FakeFilesystem

import web


@pytest.fixture(autouse=True)
def setup_filesystem(fs: FakeFilesystem) -> None:
  """Set up the filesystem."""

  # flask.testing requires metadata for this package to be available
  fs.add_package_metadata('werkzeug')

  # add the web directory so we can access files like templates
  fs.add_real_directory(os.path.dirname(web.__file__))


@pytest.fixture(name='client')
def fixture_client() -> FlaskClient:
  """Return a Flask client."""
  return web.app.test_client()


# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page


class TestViewConfigs:
  """Tests for the GET /configs endpoint."""

  def test_missing_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory is missing.

    The page should say that no config files were found.
    """

    response = client.get('/configs')

    assert response.status_code == 200

    assert b'No config files found' in response.data

  def test_empty_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory is empty.

    The page should say that no config files were found.
    """

    os.mkdir('config')

    response = client.get('/configs')

    assert response.status_code == 200

    assert b'No config files found' in response.data

  def test_files_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the config/ directory has config files.

    The files should be listed on the page.
    """

    fs.add_real_file('config/config_default.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_linux.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_macos.json')

    response = client.get('/configs')

    assert response.status_code == 200

    assert b'No config files found' not in response.data

    assert b'<pre class="m-0">config_default.json</pre>' in response.data
    assert b'<pre class="m-0">config_linux.json</pre>' in response.data
    assert b'<pre class="m-0">config_macos.json</pre>' in response.data

  def test_only_json_files_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the config/ directory has other files.

    Only .json files should be considered.
    """

    fs.add_real_file('config/config_default.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_linux.txt')
    fs.add_real_file('config/config_default.json', target_path='config/config_macos.jsonc')

    response = client.get('/configs')

    assert response.status_code == 200

    assert b'No config files found' not in response.data

    assert b'<pre class="m-0">config_default.json</pre>' in response.data
    assert b'config_linux.txt' not in response.data
    assert b'config_macos.jsonc' not in response.data


class TestViewUrls:
  """Tests for the GET /urls endpoint."""

  def test_missing_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the base_urls/visit directory is missing.

    The page should say that no url files were found.
    """

    response = client.get('/urls')

    assert response.status_code == 200

    assert b'No url files found' in response.data

  def test_empty_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the base_urls/visit directory is empty.

    The page should say that no url files were found.
    """

    os.mkdir('config')

    response = client.get('/urls')

    assert response.status_code == 200

    assert b'No url files found' in response.data

  def test_files_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the base_urls/visit directory has url files.

    The files should be parsed and their contents shown on the page.
    """

    fs.create_file(
      'base_urls/visit/one.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'ACME,https://acme.com/finance,Finance',
          'ACME,https://acme.com/hr,Human Resources',
        ]
      ),
    )

    fs.create_file(
      'base_urls/visit/two.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.get('/urls')

    assert response.status_code == 200

    assert b'No url files found' not in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/finance</td>' in response.data
    assert b'<td>Finance</td>' in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/hr</td>' in response.data
    assert b'<td>Human Resources</td>' in response.data

    assert b'<pre class="m-0">Source: ./base_urls/visit/one.csv</pre>' in response.data

    assert b'<td>Umbrella Corp</td>' in response.data
    assert b'<td>https://umbrella.com</td>' in response.data
    assert b'<td>R&amp;D</td>' in response.data

    assert b'<td>Buy &#39;n&#39; Large</td>' in response.data
    assert b'<td>https://bnl.com/</td>' in response.data
    assert b'<td>Sales</td>' in response.data

    assert b'<pre class="m-0">Source: ./base_urls/visit/two.csv</pre>' in response.data

  def test_only_csv_files_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the base_urls/visit directory has other files.

    Only .csv files should be considered.
    """

    fs.add_real_file('base_urls/visit/example.txt')
    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'ACME,https://acme.com/finance,Finance',
          'ACME,https://acme.com/hr,Human Resources',
        ]
      ),
    )

    response = client.get('/urls')

    assert response.status_code == 200

    assert b'No url files found' not in response.data
    assert b'example.txt' not in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/finance</td>' in response.data
    assert b'<td>Finance</td>' in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/hr</td>' in response.data
    assert b'<td>Human Resources</td>' in response.data

    assert b'<pre class="m-0">Source: ./base_urls/visit/urls.csv</pre>' in response.data
