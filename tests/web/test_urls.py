"""Basic tests of the endpoints relating to URLs"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

import os

from flask.testing import FlaskClient
from pyfakefs.fake_filesystem import FakeFilesystem


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

  def test_invalid_csv_files_are_fine(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the base_urls/visit directory has an invalid CSV file.

    All CSV files should be processed and shown, with the invalid ones having
    an error message in their table.
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

    # currently we require CSVs to have at least three columns
    fs.create_file(
      'base_urls/visit/two.csv',
      contents='\n'.join(
        [
          'organisation,url',
          'Umbrella Corp,https://umbrella.com',
          "Buy 'n' Large,https://bnl.com/",
        ]
      ),
    )

    fs.create_file(
      'base_urls/visit/three.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    # this is actually a JSON file
    fs.add_real_file('config/config_default.json', target_path='base_urls/visit/silly.csv')

    response = client.get('/urls')

    assert response.status_code == 200

    assert b'No url files found' not in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/finance</td>' in response.data
    assert b'<td>Finance</td>' in response.data

    assert b'<pre class="m-0">Source: ./base_urls/visit/one.csv</pre>' in response.data

    assert b'Invalid CSV: must have 3 columns' in response.data
    assert b'<pre class="m-0">Source: ./base_urls/visit/two.csv</pre>' in response.data

    assert b'<td>Umbrella Corp</td>' in response.data
    assert b'<td>https://umbrella.com</td>' in response.data
    assert b'<td>R&amp;D</td>' in response.data

    assert b'<pre class="m-0">Source: ./base_urls/visit/three.csv</pre>' in response.data

    assert b'Invalid CSV: must have 3 columns' in response.data
    assert b'<pre class="m-0">Source: ./base_urls/visit/silly.csv</pre>' in response.data

  def test_empty_csv_files_are_fine(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the base_urls/visit directory has an empty CSV file.

    All CSV files should be processed and shown, with the empty ones having
    a message in their table.
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

    fs.create_file('base_urls/visit/two.csv', contents='organisation,url,sector')
    fs.create_file('base_urls/visit/three.csv', contents='\n')

    response = client.get('/urls')

    assert response.status_code == 200

    assert b'No url files found' not in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/finance</td>' in response.data
    assert b'<td>Finance</td>' in response.data

    assert b'<pre class="m-0">Source: ./base_urls/visit/one.csv</pre>' in response.data

    assert b'File is empty' in response.data
    assert b'<pre class="m-0">Source: ./base_urls/visit/two.csv</pre>' in response.data

    assert b'File is empty' in response.data
    assert b'<pre class="m-0">Source: ./base_urls/visit/three.csv</pre>' in response.data
