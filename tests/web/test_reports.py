"""Basic tests of the endpoints relating to URLs"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

from flask.testing import FlaskClient
from pyfakefs.fake_filesystem import FakeFilesystem


def build_language_audit_csv_content() -> str:
  """Build the contents of a language_audit.csv file."""
  return '\n'.join(
    [
      'organisation,sector,page_title,base_url,url,viewport_size,audit_id,page_id,flesch_kincaid_gl,num_sentences,words_per_sentence,syllables_per_word,smog_gl,helpUrl',  # noqa: E501, pylint: disable=line-too-long
      "DIA,R&D,CWAC | Configs,http://localhost:5000,http://localhost:5000/configs,\"{'width': 320, 'height': 450}\",6_small,6,8.501,43,13.558,1.593,11.440,https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/",  # noqa: E501, pylint: disable=line-too-long
      "DIA,R&D,CWAC | Configs,http://localhost:5000,http://localhost:5000/configs,\"{'width': 1280, 'height': 800}\",6_medium,6,8.501,43,13.558,1.593,11.440,https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/",  # noqa: E501, pylint: disable=line-too-long
    ]
  )


class TestViewReports:
  """Tests for the GET /reports endpoint."""

  def test_missing_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the reports/ directory is missing.

    The page should say that no reports were found.
    """

    response = client.get('/reports')

    assert response.status_code == 200

    assert b'No reports found' in response.data

  def test_empty_directory_is_ok(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the reports/ directory is empty.

    The page should say that no reports were found.
    """

    fs.makedir('reports')

    response = client.get('/reports')

    assert response.status_code == 200

    assert b'No reports found' in response.data

  def test_reports_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the reports/ directory has content.

    The reports should be listed with their files.
    """

    fs.makedir('reports')

    # reports with nothing in it
    fs.makedir('reports/2025-01-01_12-00-00_audit_reports')

    # reports with just a csv
    fs.makedir('reports/2025-01-02_12-00-00_audit_reports')
    fs.create_file(
      'reports/2025-01-02_12-00-00_audit_reports/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )

    # reports with a bunch of stuff
    fs.makedir('reports/2025-01-03_12-00-00_audit_reports')
    fs.create_file(
      'reports/2025-01-03_12-00-00_audit_reports/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )
    fs.create_file(
      'reports/2025-01-03_12-00-00_audit_reports/language_audit_leaderboard.csv',
      contents='\n'.join(
        [
          'organisation,base_url,smog_grade_level,num_pages_scanned',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
        ]
      ),
    )

    response = client.get('/reports')

    assert response.status_code == 200

    # todo: none of this actually asserts the relation of the items properly

    assert b'>reports/2025-01-01_12-00-00_audit_reports</h5>' in response.data
    assert b'No files found' in response.data

    # reports with just a config
    assert b'>reports/2025-01-02_12-00-00_audit_reports</h5>' in response.data
    assert b'language_audit.csv' in response.data

    # reports with a bunch of stuff
    assert b'>reports/2025-01-03_12-00-00_audit_reports</h5>' in response.data
    assert b'language_audit.csv' in response.data
    assert b'language_audit_leaderboard.csv' in response.data

  def test_nested_directories_are_handled_correctly(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the reports/ directory has a result with nested directories.

    The nested directories should be associated with the correct result, but only shown
    if they actually have a file.
    """

    fs.makedir('reports')

    # reports with just some empty nested directories
    fs.makedir('reports/2025-02-01_12-00-00_audit_reports')
    fs.makedir('reports/2025-02-01_12-00-00_audit_reports/inner-dir-empty')
    fs.makedirs('reports/2025-02-01_12-00-00_audit_reports/inner-dir1/empty-inner-inner-dir')

    # reports with just a config file and some empty nested directories
    fs.makedir('reports/2025-02-02_12-00-00_audit_reports')
    fs.makedirs('reports/2025-02-02_12-00-00_audit_reports/inner-dir-empty')
    fs.makedirs('reports/2025-02-02_12-00-00_audit_reports/inner-dir2/empty-inner-inner-dir')
    fs.create_file(
      'reports/2025-02-02_12-00-00_audit_reports/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )

    # reports with files, some in nested directories
    fs.makedir('reports/2025-02-03_12-00-00_audit_reports')
    fs.create_file(
      'reports/2025-02-03_12-00-00_audit_reports/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )
    fs.create_file(
      'reports/2025-02-03_12-00-00_audit_reports/leaderboards/language_audit_leaderboard.csv',
      contents='\n'.join(
        [
          'organisation,base_url,smog_grade_level,num_pages_scanned',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
        ]
      ),
    )

    response = client.get('/reports')

    assert response.status_code == 200

    # todo: none of this actually asserts the relation of the items properly

    # reports with just some empty nested directories
    assert b'>reports/2025-02-01_12-00-00_audit_reports</h5>' in response.data
    assert b'No files found' in response.data
    assert b'inner-dir-empty' not in response.data
    assert b'inner-dir1' not in response.data
    assert b'empty-inner-inner-dir' not in response.data

    # reports with just a config file and some empty nested directories
    assert b'>reports/2025-02-02_12-00-00_audit_reports</h5>' in response.data
    assert b'language_audit.csv' in response.data
    assert b'inner-dir-empty' not in response.data
    assert b'inner-dir2' not in response.data
    assert b'empty-inner-inner-dir' not in response.data

    # reports with files, some in nested directories
    assert b'>reports/2025-02-03_12-00-00_audit_reports</h5>' in response.data
    assert b'language_audit.csv' in response.data
    assert b'leaderboards/language_audit_leaderboard.csv' in response.data


class TestDownloadReportFile:
  """Tests for the GET /d/reports endpoint."""

  def test_reports_directories_cannot_be_downloaded(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a reports directory without a file.

    A 404 should be returned.
    """
    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedir('reports')

    fs.makedir('reports/2025-03-01_12-00-00_audit_reports')
    fs.create_file(
      'reports/2025-03-01_12-00-00_audit_reports/language_audit_leaderboard.csv',
      contents='\n'.join(
        [
          'organisation,base_url,smog_grade_level,num_pages_scanned',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
        ]
      ),
    )

    response = client.get('/d/reports/2025-03-01_12-00-00_audit_reports')

    assert response.status_code == 404

    response = client.get('/d/reports/2025-03-01_12-00-00_audit_reports/')

    assert response.status_code == 404

  def test_files_that_do_not_exist_are_handled(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a file that does not exist.

    A 404 should be returned.
    """
    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedir('reports')

    fs.makedir('reports/2025-03-01_12-00-00_audit_reports')
    fs.create_file(
      'reports/2025-03-01_12-00-00_audit_reports/language_audit_leaderboard.csv',
      contents='\n'.join(
        [
          'organisation,base_url,smog_grade_level,num_pages_scanned',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
        ]
      ),
    )

    response = client.get('/d/reports/2025-03-01_12-00-00_audit_reports/language_audit.csv')

    assert response.status_code == 404

  def test_files_inside_reports_can_be_downloaded(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a file that is inside the reports/ directory.

    The file contents should be returned.
    """

    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedirs('reports/2025-03-01_12-00-00_audit_reports')
    fs.create_file(
      'reports/2025-03-01_12-00-00_audit_reports/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )
    fs.create_file(
      'reports/2025-03-01_12-00-00_audit_reports/language_audit_leaderboard.csv',
      contents='\n'.join(
        [
          'organisation,base_url,smog_grade_level,num_pages_scanned',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
          'DIA,http://localhost:5000,http://localhost:5000/configs,11.440,1',
        ]
      ),
    )

    response = client.get('/d/reports/2025-03-01_12-00-00_audit_reports/language_audit.csv')

    assert response.status_code == 200

    with open('reports/2025-03-01_12-00-00_audit_reports/language_audit.csv', encoding='utf-8') as f:
      assert f.read().encode() == response.data

    response = client.get('/d/reports/2025-03-01_12-00-00_audit_reports/language_audit_leaderboard.csv')

    assert response.status_code == 200

    with open('reports/2025-03-01_12-00-00_audit_reports/language_audit_leaderboard.csv', encoding='utf-8') as f:
      assert f.read().encode() == response.data

  def test_files_outside_reports_cannot_be_downloaded(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a file that is outside the reports/ directory.

    A 404 should be returned.
    """

    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedirs('reports/2025-03-01_12-00-00_audit_reports')
    fs.add_real_file('config/config_default.json')
    fs.add_real_file(
      'config/config_default.json',
      target_path='reports/2025-03-01_12-00-00_audit_reports/config.json',
    )

    response = client.get('/d/reports/../config/config_default.json')

    assert response.status_code == 404

    response = client.get('/d/reports/2025-03-01_12-00-00_audit_reports/../../config/config_default.json')

    assert response.status_code == 404

    response = client.get('/d/reports/%2E%2E/config/config_default.json')

    assert response.status_code == 404

    response = client.get('/d/reports/2025-03-01_12-00-00_audit_reports/%2E%2E/%2E%2E/config/config_default.json')

    assert response.status_code == 404
