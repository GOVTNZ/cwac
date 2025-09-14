"""Basic tests of the endpoints relating to URLs"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

import os

from flask.testing import FlaskClient
from markupsafe import escape
from pyfakefs.fake_filesystem import FakeFilesystem

from tests.web.test_helpers import assert_has_invalid_field


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

    assert b'<pre class="m-0 ms-2">one.csv</pre>' in response.data
    assert b'<pre class="m-0 ms-2">two.csv</pre>' in response.data

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

    assert b'<pre class="m-0 ms-2">urls.csv</pre>' in response.data
    assert b'example.txt' not in response.data


class TestShowUrls:
  """Tests for the GET /urls/<filename> endpoint."""

  def test_missing_directory_is_handled(self, client: FlaskClient) -> None:
    """Test handling when the base_urls/visit/ directory is missing.

    The page should return a 404
    """

    response = client.get('/urls/urls')

    assert response.status_code == 404

  def test_file_does_not_exist(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the file does not exist.

    The page should return a 404
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.get('/urls/does_not_exist')

    assert response.status_code == 404

  def test_file_contents_are_shown(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a csv file that exists.

    The contents of the file should be read and rendered in a text area.
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.get('/urls/urls')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/urls.csv</h2>' in response.data

    # the header row should not be included with the others
    assert b'<td>organisation</td>' not in response.data
    assert b'<td>url</td>' not in response.data
    assert b'<td>sector</td>' not in response.data

    assert b'<td>Umbrella Corp</td>' in response.data
    assert b'<td>https://umbrella.com</td>' in response.data
    assert b'<td>R&amp;D</td>' in response.data

    assert b'<td>Buy &#39;n&#39; Large</td>' in response.data
    assert b'<td>https://bnl.com/</td>' in response.data
    assert b'<td>Sales</td>' in response.data

  def test_invalid_csvs_are_ok(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a csv file whose contents are invalid.

    The page should render with a column saying the CSV is invalid and why.
    """
    # currently we require CSVs to have at least three columns
    fs.create_file(
      'base_urls/visit/invalid-missing-column.csv',
      contents='\n'.join(
        [
          'organisation,url',
          'Umbrella Corp,https://umbrella.com',
          "Buy 'n' Large,https://bnl.com/",
        ]
      ),
    )

    response = client.get('/urls/invalid-missing-column')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/invalid-missing-column.csv</h2>' in response.data

    assert b'Invalid CSV: must have 3 columns' in response.data

    assert b'Umbrella Corp' not in response.data
    assert b'https://umbrella.com' not in response.data

    assert b"Buy 'n' Large" not in response.data
    assert b'Buy &#39;n&#39; Large' not in response.data
    assert b'https://bnl.com/' not in response.data

    # this is actually a JSON file
    fs.add_real_file('config/config_default.json', target_path='base_urls/visit/invalid-is-json.csv')

    response = client.get('/urls/invalid-is-json')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/invalid-is-json.csv</h2>' in response.data

    assert b'Invalid CSV: must have 3 columns' in response.data

  def test_weird_characters_work_fine(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has interesting characters.

    The file should be resolved without issue.
    """

    fs.create_file(
      'base_urls/visit/my urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'ACME,https://acme.com/finance,Finance',
          'ACME,https://acme.com/hr,Human Resources',
        ]
      ),
    )
    fs.create_file(
      'base_urls/visit/theirs: urls.file.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.get('/urls/my%20urls')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/my urls.csv</h2>' in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/finance</td>' in response.data
    assert b'<td>Finance</td>' in response.data

    assert b'<td>ACME</td>' in response.data
    assert b'<td>https://acme.com/hr</td>' in response.data
    assert b'<td>Human Resources</td>' in response.data

    response = client.get('/urls/theirs:%20urls.file')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/theirs: urls.file.csv</h2>' in response.data

    assert b'<td>Umbrella Corp</td>' in response.data
    assert b'<td>https://umbrella.com</td>' in response.data
    assert b'<td>R&amp;D</td>' in response.data

    assert b'<td>Buy &#39;n&#39; Large</td>' in response.data
    assert b'<td>https://bnl.com/</td>' in response.data
    assert b'<td>Sales</td>' in response.data

  def test_parent_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse upwards.

    The file should not be resolved.
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    fs.create_file('root_file.json', contents='{"hello": "world"}')

    response = client.get('/urls/../root_file')

    assert response.status_code == 404

    response = client.get('/urls/..%2Froot_file')

    assert response.status_code == 404

    response = client.get('/urls/..\\root_file')

    assert response.status_code == 404

    response = client.get('/urls/..%5Croot_file')

    assert response.status_code == 404

  def test_child_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse downwards.

    The file should not be resolved.
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    fs.create_file('base_urls/visit/inner/file.csv', contents='{"hello": "world"}')

    response = client.get('/urls/inner/file')

    assert response.status_code == 404

    response = client.get('/urls/inner%2Ffile')

    assert response.status_code == 404

    response = client.get('/urls/inner\\file')

    assert response.status_code == 404

    response = client.get('/urls/inner/%5Cfile')

    assert response.status_code == 404


class TestEditUrls:
  """Tests for the GET /urls/<filename>/edit endpoint."""

  def test_missing_directory_is_handled(self, client: FlaskClient) -> None:
    """Test handling when the base_urls/visit/ directory is missing.

    The page should return a 404
    """

    response = client.get('/urls/urls/edit')

    assert response.status_code == 404

  def test_file_does_not_exist(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the file does not exist.

    The page should return a 404
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.get('/urls/does_not_exist/edit')

    assert response.status_code == 404

  def test_file_contents_are_shown(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a csv file that exists.

    The contents of the file should be read and rendered in a text area.
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.get('/urls/urls/edit')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/urls.csv</h2>' in response.data

    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

  def test_file_does_not_have_to_be_a_valid_csv(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a file that is not a valid csv.

    The contents of the file should be shown per normal.
    """

    fs.create_file('base_urls/visit/urls.csv', contents='{\n"hello": "world"\n}')

    response = client.get('/urls/urls/edit')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/urls.csv</h2>' in response.data

    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

  def test_weird_characters_work_fine(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has interesting characters.

    The file should be resolved without issue.
    """

    fs.create_file(
      'base_urls/visit/my urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'ACME,https://acme.com/finance,Finance',
          'ACME,https://acme.com/hr,Human Resources',
        ]
      ),
    )
    fs.create_file(
      'base_urls/visit/theirs: urls.file.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.get('/urls/my%20urls/edit')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/my urls.csv</h2>' in response.data

    with open('base_urls/visit/my urls.csv', encoding='utf-8-sig') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

    response = client.get('/urls/theirs:%20urls.file/edit')

    assert response.status_code == 200

    assert b'<h2>./base_urls/visit/theirs: urls.file.csv</h2>' in response.data

    with open('base_urls/visit/theirs: urls.file.csv', encoding='utf-8-sig') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

  def test_parent_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse upwards.

    The file should not be resolved.
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    fs.create_file('root_file.json', contents='{"hello": "world"}')

    response = client.get('/urls/../root_file/edit')

    assert response.status_code == 404

    response = client.get('/urls/..%2Froot_file/edit')

    assert response.status_code == 404

    response = client.get('/urls/..\\root_file/edit')

    assert response.status_code == 404

    response = client.get('/urls/..%5Croot_file/edit')

    assert response.status_code == 404

  def test_child_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse downwards.

    The file should not be resolved.
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    fs.create_file('base_urls/visit/inner/file.csv', contents='{"hello": "world"}')

    response = client.get('/urls/inner/file/edit')

    assert response.status_code == 404

    response = client.get('/urls/inner%2Ffile/edit')

    assert response.status_code == 404

    response = client.get('/urls/inner\\file/edit')

    assert response.status_code == 404

    response = client.get('/urls/inner/%5Cfile/edit')

    assert response.status_code == 404


class TestUpdateUrls:
  """Tests for the POST /urls/<filename> endpoint."""

  def test_missing_directory_is_handled(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory is missing.

    The page should return a 404
    """

    response = client.post('/urls/urls', data={'contents': '{}'})

    assert response.status_code == 404

  def test_file_must_exist_to_be_updated(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename is not for a file that already exists.

    An error should be returned without the file being created.
    """

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )

    response = client.post(
      '/urls/does_not_exist',
      data={
        'contents': '\n'.join(
          [
            'organisation,url,sector',
            'ACME,https://acme.com/finance,Finance',
            'ACME,https://acme.com/hr,Human Resources',
          ]
        )
      },
    )

    assert response.status_code == 404
    assert os.path.exists('./base_urls/visit/does_not_exist.csv') is False
    assert os.path.exists('./base_urls/does_not_exist.csv') is False

  def test_contents_is_required_and_a_string(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling requests that do not have a "contents" string in their data.

    An error should be returned without the file being changed.
    """

    contents_old = '\n'.join(
      [
        'organisation,url,sector',
        'Umbrella Corp,https://umbrella.com,R&D',
        "Buy 'n' Large,https://bnl.com/,Sales",
      ]
    )

    fs.create_file('base_urls/visit/urls.csv', contents=contents_old)

    response = client.post('/urls/urls')

    assert response.status_code == 422
    assert b'cannot be blank' in response.data
    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      assert contents_old == f.read()

    response = client.post('/urls/urls', data={})

    assert response.status_code == 422
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')
    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      assert contents_old == f.read()

    response = client.post('/urls/urls', data={'contents': ''})

    assert response.status_code == 422
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')
    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      assert contents_old == f.read()

  def test_file_contents_are_updated(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a csv file that exists.

    The contents of the file should be updated, and the user redirected to the
    list page with a success message.
    """

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

    response = client.post(
      '/urls/urls',
      data={
        'contents': '\n'.join(
          [
            'organisation,url,sector',
            'Umbrella Corp,https://umbrella.com,R&D',
            "Buy 'n' Large,https://bnl.com/,Sales",
          ]
        )
      },
    )

    assert response.status_code == 302
    assert response.location == '/urls/urls'

    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      assert f.read() == '\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      )

    response = client.post('/urls/urls', data={'contents': 'this is not a valid csv'})

    assert response.status_code == 302
    assert response.location == '/urls/urls'

    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      assert f.read() == 'this is not a valid csv'

  def test_weird_characters_work_fine(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has interesting characters.

    The file should be updated without issue.
    """

    fs.create_file('base_urls/visit/my urls.csv', contents='organisation,url,sector\n')
    fs.create_file('base_urls/visit/theirs: urls.file.csv', contents='organisation,url,sector\n')

    response = client.post(
      '/urls/my%20urls',
      data={
        'contents': '\n'.join(
          [
            'organisation,url,sector',
            'ACME,https://acme.com/finance,Finance',
            'ACME,https://acme.com/hr,Human Resources',
          ]
        )
      },
    )

    assert response.status_code == 302
    assert response.location == '/urls/my%20urls'

    with open('base_urls/visit/my urls.csv', encoding='utf-8-sig') as f:
      assert f.read() == '\n'.join(
        [
          'organisation,url,sector',
          'ACME,https://acme.com/finance,Finance',
          'ACME,https://acme.com/hr,Human Resources',
        ]
      )

    response = client.post(
      '/urls/theirs:%20urls.file',
      data={
        'contents': '\n'.join(
          [
            'organisation,url,sector',
            'Umbrella Corp,https://umbrella.com,R&D',
            "Buy 'n' Large,https://bnl.com/,Sales",
          ]
        )
      },
    )

    assert response.status_code == 302
    assert response.location == '/urls/theirs:%20urls.file'

    with open('base_urls/visit/theirs: urls.file.csv', encoding='utf-8-sig') as f:
      assert f.read() == '\n'.join(
        [
          'organisation,url,sector',
          'Umbrella Corp,https://umbrella.com,R&D',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      )

  def test_line_endings_are_normalized(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test line endings are normalized to Unix style."""

    contents = '\n'.join(
      [
        'organisation,url,sector',
        'Umbrella Corp,https://umbrella.com,R&D',
        "Buy 'n' Large,https://bnl.com/,Sales",
      ]
    )
    fs.create_file('base_urls/visit/urls.csv', contents=contents)

    response = client.post('/urls/urls', data={'contents': contents.replace('\n', '\r\n')})

    assert response.status_code == 302
    assert response.location == '/urls/urls'

    with open('base_urls/visit/urls.csv', encoding='utf-8-sig') as f:
      contents_now = f.read()
      assert contents_now == contents_now.replace('\r\n', '\n')

  def test_parent_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse upwards.

    The file should not be resolved.
    """

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

    contents_visit = '\n'.join(
      [
        'organisation,url,sector',
        'Umbrella Corp,https://umbrella.com,R&D',
      ]
    )
    fs.create_file('base_urls/visit.csv', contents=contents_visit)

    contents_root = '\n'.join(
      [
        'organisation,url,sector',
        "Buy 'n' Large,https://bnl.com/,Sales",
      ]
    )
    fs.create_file('root.csv', contents=contents_root)

    response = client.post('/urls/../root', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_root
    with open('base_urls/visit.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_visit

    response = client.post('/urls/..%2Froot', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_root
    with open('base_urls/visit.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_visit

    response = client.post('/urls/..\\root', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_root
    with open('base_urls/visit.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_visit

    response = client.post('/urls/..%5Croot', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_root
    with open('base_urls/visit.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents_visit

  def test_child_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse downwards.

    The file should not be resolved.
    """

    contents = '\n'.join(
      [
        'organisation,url,sector',
        'Umbrella Corp,https://umbrella.com,R&D',
      ]
    )

    fs.create_file(
      'base_urls/visit/urls.csv',
      contents='\n'.join(
        [
          'organisation,url,sector',
          "Buy 'n' Large,https://bnl.com/,Sales",
        ]
      ),
    )
    fs.create_file('base_urls/visit/inner/file.csv', contents=contents)

    response = client.post('/urls/inner/file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('base_urls/visit/inner/file.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents

    response = client.post('/urls/inner%2Ffile', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('base_urls/visit/inner/file.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents

    response = client.post('/urls/inner\\file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('base_urls/visit/inner/file.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents

    response = client.post('/urls/inner/%5Cfile', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('base_urls/visit/inner/file.csv', encoding='utf-8-sig') as f:
      assert f.read() == contents
