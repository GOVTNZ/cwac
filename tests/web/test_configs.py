"""Basic tests of the endpoints relating to configs"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

import os

from flask.testing import FlaskClient
from markupsafe import escape
from pyfakefs.fake_filesystem import FakeFilesystem


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


class TestEditConfig:
  """Tests for the GET /configs/<filename>/edit endpoint."""

  def test_missing_directory_is_handled(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory is missing.

    The page should return a 404
    """

    response = client.get('/configs/config_default/edit')

    assert response.status_code == 404

  def test_config_file_does_not_exist(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the config file does not exist.

    The page should return a 404
    """

    fs.add_real_file('config/config_default.json')

    response = client.get('/configs/config_does_not_exist/edit')

    assert response.status_code == 404

  def test_file_contents_are_shown(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a json file that exists.

    The contents of the file should be read and rendered in a text area.
    """

    fs.add_real_file('config/config_default.json')

    response = client.get('/configs/config_default/edit')

    assert response.status_code == 200

    assert b'Editing ./config/config_default.json' in response.data

    with open('config/config_default.json', encoding='utf-8') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

  def test_file_does_not_have_to_be_valid_json(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a file that is not valid json.

    The contents of the file should be shown per normal.
    """

    fs.add_real_file('base_urls/visit/example.txt', target_path='config/config_linux.json')

    response = client.get('/configs/config_linux/edit')

    assert response.status_code == 200

    assert b'Editing ./config/config_linux.json' in response.data

    with open('config/config_linux.json', encoding='utf-8') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

  def test_weird_characters_work_fine(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has interesting characters.

    The file should be resolved without issue.
    """

    fs.add_real_file('config/config_default.json', target_path='config/config macos.json')
    fs.add_real_file('config/config_default.json', target_path='config/config: linux.file.json')

    response = client.get('/configs/config%20macos/edit')

    assert response.status_code == 200

    assert b'Editing ./config/config macos.json' in response.data

    with open('config/config macos.json', encoding='utf-8') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

    response = client.get('/configs/config:%20linux.file/edit')

    assert response.status_code == 200

    assert b'Editing ./config/config: linux.file.json' in response.data

    with open('config/config: linux.file.json', encoding='utf-8') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

  def test_parent_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse upwards.

    The file should not be resolved.
    """

    fs.add_real_file('config/config_default.json')
    fs.create_file('root_file.json', contents='{"hello": "world"}')

    response = client.get('/configs/../root_file/edit')

    assert response.status_code == 404

    response = client.get('/configs/..%2Froot_file/edit')

    assert response.status_code == 404

    response = client.get('/configs/..\\root_file/edit')

    assert response.status_code == 404

    response = client.get('/configs/..%5Croot_file/edit')

    assert response.status_code == 404

  def test_child_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse downwards.

    The file should not be resolved.
    """

    fs.add_real_file('config/config_default.json')
    fs.create_file('config/inner/file.json', contents='{"hello": "world"}')

    response = client.get('/configs/inner/file/edit')

    assert response.status_code == 404

    response = client.get('/configs/inner%2Ffile/edit')

    assert response.status_code == 404

    response = client.get('/configs/inner\\file/edit')

    assert response.status_code == 404

    response = client.get('/configs/inner/%5Cfile/edit')

    assert response.status_code == 404


class TestUpdateConfig:
  """Tests for the POST /configs/<filename> endpoint."""

  def test_missing_directory_is_handled(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory is missing.

    The page should return a 404
    """

    response = client.post('/configs/config_default', data={'contents': '{}'})

    assert response.status_code == 404

  def test_file_must_exist_to_be_updated(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename is not for a file that already exists.

    An error should be returned without the file being created.
    """

    fs.add_real_file('config/config_default.json')

    response = client.post('/configs/config_does_not_exist', data={'contents': '{}'})

    assert response.status_code == 404
    assert os.path.exists('./config/config_does_not_exist.json') is False

  def test_contents_is_required_and_a_string(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling requests that do not have a "contents" string in their data.

    An error should be returned without the file being changed.
    """

    # even though we don't expect any writes, we can't have the file read-only since the
    # implementation opens the file for reading _and_ writing before it does the validation
    fs.add_real_file('config/config_default.json', read_only=False)

    with open('config/config_default.json', encoding='utf-8') as f:
      contents_old = f.read()

    response = client.post('/configs/config_default')

    assert response.status_code == 422
    assert b'contents is required' in response.data
    with open('config/config_default.json', encoding='utf-8') as f:
      assert contents_old == f.read()

    response = client.post('/configs/config_default', data={})

    assert response.status_code == 422
    assert b'contents is required' in response.data
    with open('config/config_default.json', encoding='utf-8') as f:
      assert contents_old == f.read()

    response = client.post('/configs/config_default', data={'contents': ''})

    assert response.status_code == 422
    assert b'contents is required' in response.data
    with open('config/config_default.json', encoding='utf-8') as f:
      assert contents_old == f.read()

  def test_file_contents_are_updated(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a json file that exists.

    The contents of the file should be updated, and the user redirected to the
    list page with a success message.
    """

    fs.add_real_file('config/config_default.json', read_only=False)

    response = client.post('/configs/config_default', data={'contents': '{"hello": "world"}'})

    assert response.status_code == 302

    with open('config/config_default.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/config_default', data={'contents': 'this is not valid json'})

    assert response.status_code == 302

    with open('config/config_default.json', encoding='utf-8') as f:
      assert f.read() == 'this is not valid json'

  def test_weird_characters_work_fine(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has interesting characters.

    The file should be updated without issue.
    """

    fs.add_real_file('config/config_default.json', read_only=False, target_path='config/config macos.json')
    fs.add_real_file('config/config_default.json', read_only=False, target_path='config/config: linux.file.json')

    response = client.post('/configs/config%20macos', data={'contents': '{"hello": "world"}'})

    assert response.status_code == 302

    with open('config/config macos.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/config:%20linux.file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 302

    with open('config/config: linux.file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "sunshine"}'

  def test_line_endings_are_normalized(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test line endings are normalized to Unix style."""

    fs.add_real_file('config/config_default.json', read_only=False)

    with open('config/config_default.json', encoding='utf-8') as f:
      contents_new = f.read().replace(os.linesep, '\r\n')

    response = client.post('/configs/config_default', data={'contents': contents_new})

    assert response.status_code == 302

    with open('config/config_default.json', encoding='utf-8') as f:
      contents_now = f.read()
      assert contents_now == contents_now.replace('\r\n', '\n')

  def test_parent_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse upwards.

    The file should not be resolved.
    """

    fs.add_real_file('config/config_default.json')
    fs.create_file('root_file.json', contents='{"hello": "world"}')

    response = client.post('/configs/../root_file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root_file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/..%2Froot_file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root_file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/..\\root_file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root_file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/..%5Croot_file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('root_file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

  def test_child_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse downwards.

    The file should not be resolved.
    """

    fs.add_real_file('config/config_default.json')
    fs.create_file('config/inner/file.json', contents='{"hello": "world"}')

    response = client.post('/configs/inner/file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('config/inner/file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/inner%2Ffile', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('config/inner/file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/inner\\file', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('config/inner/file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'

    response = client.post('/configs/inner/%5Cfile', data={'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 404
    with open('config/inner/file.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "world"}'
