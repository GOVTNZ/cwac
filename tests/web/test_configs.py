"""Basic tests of the endpoints relating to configs"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

import os

from flask.testing import FlaskClient
from markupsafe import escape
from pyfakefs.fake_filesystem import FakeFilesystem

from tests.web.test_helpers import assert_has_invalid_field, assert_has_valid_field


def has_flash(client: FlaskClient, message: str, typ: str) -> bool:
  """Check that a flash message of the given type exists in the session."""
  with client.session_transaction() as session:
    return any(flash == (typ, message) for flash in session.get('_flashes', []))


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

    assert b'<pre class="m-0 ms-2">config_default.json</pre>' in response.data
    assert b'<pre class="m-0 ms-2">config_linux.json</pre>' in response.data
    assert b'<pre class="m-0 ms-2">config_macos.json</pre>' in response.data

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

    assert b'<pre class="m-0 ms-2">config_default.json</pre>' in response.data
    assert b'config_linux.txt' not in response.data
    assert b'config_macos.jsonc' not in response.data


class TestNewConfig:
  """Tests for the GET /configs/new endpoint."""

  def test_the_page_is_rendered(self, client: FlaskClient) -> None:
    """Test handling when viewing the page."""
    response = client.get('/configs/new')

    assert response.status_code == 200
    assert b'Currently creating' in response.data

    assert b'<form' in response.data


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

    assert b'<h2>./config/config_default.json</h2>' in response.data

    with open('config/config_default.json', encoding='utf-8') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

  def test_file_does_not_have_to_be_valid_json(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given the name of a file that is not valid json.

    The contents of the file should be shown per normal.
    """

    fs.add_real_file('base_urls/visit/example.txt', target_path='config/config_linux.json')

    response = client.get('/configs/config_linux/edit')

    assert response.status_code == 200

    assert b'<h2>./config/config_linux.json</h2>' in response.data

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

    assert b'<h2>./config/config macos.json</h2>' in response.data

    with open('config/config macos.json', encoding='utf-8') as f:
      assert f'{escape(f.read())}</textarea\n'.encode() in response.data

    response = client.get('/configs/config:%20linux.file/edit')

    assert response.status_code == 200

    assert b'<h2>./config/config: linux.file.json</h2>' in response.data

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


class TestCreateConfig:
  """Tests for the POST /config endpoint."""

  def test_missing_directory_is_handled(self, client: FlaskClient) -> None:
    """Test handling when the config/ directory does not exist.

    The directory should be created along with the new config.
    """
    response = client.post('/configs', data={'filename': 'config_new', 'contents': '{}'})

    assert response.status_code == 302
    assert response.location == '/configs'

    assert os.path.exists('config/config_new.json') is True
    assert os.path.exists('config/config_new') is False

  def test_config_file_can_be_created(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when provided with a valid filename and content.

    The file should be created with the given name and content, and the user redirected to the view page.
    """
    fs.makedir('configs')

    response = client.post('/configs', data={'filename': 'config_linux', 'contents': '{"hello": "sunshine"}'})

    assert response.status_code == 302
    assert response.location == '/configs'

    assert os.path.exists('config/config_linux.json') is True
    assert os.path.exists('config/config_linux') is False

    with open('config/config_linux.json', encoding='utf-8') as f:
      assert f.read() == '{"hello": "sunshine"}'

  def test_filename_is_required(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename is not present.

    An error should be returned, without the file being created.
    """
    fs.makedir('configs')

    response = client.post('/configs', data={'filename': '', 'contents': '{"hello": "world"}'})

    assert response.status_code == 422

    assert_has_invalid_field(response.data, 'filename', 'cannot be blank')
    assert_has_valid_field(response.data, 'contents')

    assert os.path.exists('config/.json') is False

    response = client.post('/configs', data={'contents': '{"hello": "world"}'})

    assert response.status_code == 422

    assert_has_invalid_field(response.data, 'filename', 'cannot be blank')
    assert_has_valid_field(response.data, 'contents')

    assert os.path.exists('config/.json') is False

  def test_contents_is_required(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the file contents is not present.

    An error should be returned, without the file being created.
    """
    fs.makedir('configs')

    response = client.post('/configs', data={'filename': 'config_linux', 'contents': ''})

    assert response.status_code == 422

    assert_has_valid_field(response.data, 'filename')
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')

    assert os.path.exists('config/config_linux.json') is False
    assert os.path.exists('config/config_linux') is False

    response = client.post('/configs', data={'filename': 'config_linux'})

    assert response.status_code == 422

    assert_has_valid_field(response.data, 'filename')
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')

    assert os.path.exists('config/config_linux.json') is False
    assert os.path.exists('config/config_linux') is False

  def test_all_fields_are_validated_together(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when all fields are invalid.

    An error should be returned, without the file being created.
    """
    fs.makedir('configs')

    response = client.post('/configs', data={'filename': 'config_linux.json', 'contents': ''})

    assert response.status_code == 422

    assert_has_invalid_field(response.data, 'filename', 'cannot include an extension')
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')

    assert os.path.exists('config/config_linux.json') is False
    assert os.path.exists('config/config_linux') is False

    response = client.post('/configs', data={'filename': 'config_linux.json'})

    assert response.status_code == 422

    assert_has_invalid_field(response.data, 'filename', 'cannot include an extension')
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')

    assert os.path.exists('config/config_linux.json') is False
    assert os.path.exists('config/config_linux') is False

  def test_filename_should_not_have_an_extension(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has an extension.

    An error should be returned, without the file being created
    """
    fs.makedir('configs')

    for filename in ['config_new.json', 'config_new.yml.yaml', 'config_new.json.yml', 'config_new.txt.yml']:
      response = client.post('/configs', data={'filename': filename, 'contents': '{}'})

      assert response.status_code == 422

      assert_has_invalid_field(response.data, 'filename', 'cannot include an extension')
      assert_has_valid_field(response.data, 'contents')

      assert os.path.exists(f'config/{filename}.json') is False
      assert os.path.exists(f'config/{filename}') is False

  def test_filename_can_have_expected_characters(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has characters that are fine for filenames.

    The file should be created with the given name, and the user redirected to the view page.
    """
    fs.makedir('configs')

    for filename in ['config_new', 'config-new', '_', 'config1', 'config-2']:
      response = client.post('/configs', data={'filename': filename, 'contents': '{"hello": "world"}'})

      assert response.status_code == 302
      assert response.location == '/configs'

      assert os.path.exists(f'config/{filename}.json') is True
      assert os.path.exists(f'config/{filename}') is False

      with open(f'config/{filename}.json', encoding='utf-8') as f:
        assert f.read() == '{"hello": "world"}'

  def test_filename_should_not_have_weird_characters(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename has characters that are best not used in filenames.

    An error should be returned without any file being created.
    """
    fs.makedir('configs')

    for filename in ['config new']:
      response = client.post('/configs', data={'filename': filename, 'contents': '{}'})

      assert response.status_code == 422

      assert_has_invalid_field(response.data, 'filename', 'can only contain letters, numbers, dashes, and underscores')
      assert_has_valid_field(response.data, 'contents')

      assert os.path.exists(f'config/{filename}.json') is False
      assert os.path.exists(f'config/{filename}') is False

  def test_existing_files_cannot_be_overridden(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename matches a config that already exists.

    An error should be returned, and the existing file unchanged.
    """
    fs.add_real_file('config/config_default.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_macos.json')

    response = client.post('/configs', data={'filename': 'config_default', 'contents': '{"hello": "world"}'})

    assert response.status_code == 422
    assert b'a config file with that name already exists' in response.data

    with open('config/config_default.json', encoding='utf-8') as f:
      assert f.read() != '{"hello": "world"}'

    response = client.post('/configs', data={'filename': 'config_macos', 'contents': '{"hello": "world"}'})

    assert response.status_code == 422
    assert b'a config file with that name already exists' in response.data

    with open('config/config_macos.json', encoding='utf-8') as f:
      assert f.read() != '{"hello": "world"}'

    # do a little bonus check since both files came from the same source
    with (
      open('config/config_default.json', encoding='utf-8') as f1,
      open('config/config_macos.json', encoding='utf-8') as f2,
    ):
      assert f1.read() == f2.read()

  def test_parent_files_cannot_be_created(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse upwards.

    An error should be returned without any files being created.
    """
    fs.makedirs('config')

    for filename in ['../config_new', '..\\/config_new', '..%2Fconfig_new', '..%5Cconfig_new']:
      response = client.post('/configs', data={'filename': filename, 'contents': '{}'})

      assert response.status_code == 422
      assert_has_invalid_field(response.data, 'filename', 'can only contain letters, numbers, dashes, and underscores')
      assert_has_valid_field(response.data, 'contents')

      assert os.path.exists(f'config/{filename}.json') is False
      assert os.path.exists(f'config/{filename}') is False
      assert os.path.exists(f'{filename}.json') is False
      assert os.path.exists(f'{filename}') is False
      assert os.path.exists('config_new.json') is False
      assert os.path.exists('config_new') is False

  def test_child_files_cannot_be_created(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse downwards.

    An error should be returned without any files being created.
    """
    fs.makedirs('config')

    for filename in ['inner/config_new', 'inner%2Fconfig_new', 'inner\\/config_new', 'inner%5Cconfig_new']:
      response = client.post('/configs', data={'filename': filename, 'contents': '{}'})

      assert response.status_code == 422
      assert_has_invalid_field(response.data, 'filename', 'can only contain letters, numbers, dashes, and underscores')
      assert_has_valid_field(response.data, 'contents')

      assert os.path.exists(f'config/{filename}.json') is False
      assert os.path.exists(f'config/{filename}') is False
      assert os.path.exists('config/inner') is False
      assert os.path.exists(f'config/inner/{filename}.json') is False
      assert os.path.exists(f'config/inner/{filename}') is False
      assert os.path.exists('config/inner/config_new.json') is False
      assert os.path.exists('config/inner/config_new') is False


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
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')
    with open('config/config_default.json', encoding='utf-8') as f:
      assert contents_old == f.read()

    response = client.post('/configs/config_default', data={})

    assert response.status_code == 422
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')
    with open('config/config_default.json', encoding='utf-8') as f:
      assert contents_old == f.read()

    response = client.post('/configs/config_default', data={'contents': ''})

    assert response.status_code == 422
    assert_has_invalid_field(response.data, 'contents', 'cannot be blank')
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


class TestDeleteConfig:
  """Tests for the DELETE /configs/<filename> endpoint."""

  def test_missing_directory_is_handled(self, client: FlaskClient) -> None:
    """Test handling attempting to delete a file when the config/ directory does not exist.

    An error should be returned.
    """
    response = client.delete('/configs/config_linux')

    assert response.status_code == 404

  def test_file_does_not_exist(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling attempting to delete a file that does not exist.

    An error should be returned.
    """
    fs.makedir('config')

    response = client.delete('/configs/does_not_exist')

    assert response.status_code == 404

  def test_default_config_cannot_be_deleted(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when attempting to delete the default config file.

    The file should not be deleted, and the user redirected with a flash message.
    """
    fs.add_real_file('config/config_default.json')

    response = client.delete('configs/config_default')

    assert response.status_code == 302
    assert response.location == '/configs'

    assert has_flash(client, './config/config_default.json cannot be deleted', 'danger')

    assert os.path.exists('config/config_default.json') is True

  def test_the_file_is_deleted(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when attempting to delete a config file.

    The file should be deleted and the user redirected to the view page
    """
    fs.add_real_file('config/config_default.json')
    fs.add_real_file('config/config_default.json', target_path='config/config_linux.json')

    response = client.delete('configs/config_linux')

    assert response.status_code == 302
    assert response.location == '/configs'

    assert has_flash(client, './config/config_linux.json has been deleted', 'success')

    assert os.path.exists('config/config_default.json') is True
    assert os.path.exists('config/config_linux.json') is False

  def test_parent_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse upwards.

    The file should not be resolved.
    """

    fs.add_real_file('config/config_default.json')
    fs.create_file('root_file.json', contents='{"hello": "world"}')

    response = client.delete('/configs/../root_file')

    assert response.status_code == 404
    assert os.path.exists('root_file.json') is True

    response = client.delete('/configs/..%2Froot_file')

    assert response.status_code == 404
    assert os.path.exists('root_file.json') is True

    response = client.delete('/configs/..\\root_file')

    assert response.status_code == 404
    assert os.path.exists('root_file.json') is True

    response = client.delete('/configs/..%5Croot_file')

    assert response.status_code == 404
    assert os.path.exists('root_file.json') is True

  def test_child_files_cannot_be_accessed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the filename includes a path attempting to traverse downwards.

    The file should not be resolved.
    """

    fs.add_real_file('config/config_default.json')
    fs.create_file('config/inner/file.json', contents='{"hello": "world"}')

    response = client.delete('/configs/inner/file')

    assert response.status_code == 404
    assert os.path.exists('config/inner/file.json') is True

    response = client.delete('/configs/inner%2Ffile')

    assert response.status_code == 404
    assert os.path.exists('config/inner/file.json') is True

    response = client.delete('/configs/inner\\file')

    assert response.status_code == 404
    assert os.path.exists('config/inner/file.json') is True

    response = client.delete('/configs/inner/%5Cfile')

    assert response.status_code == 404
    assert os.path.exists('config/inner/file.json') is True
