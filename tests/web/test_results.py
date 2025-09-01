"""Basic tests of the endpoints relating to URLs"""

# todo: find a way to improve HTML assertions so that we can do matching on tags
#  without their full content and with nesting taken into account e.g. most of
#  the table related assertions in these tests should be trying to find whole
#  rows rather than just content on the page

from flask.testing import FlaskClient
from pyfakefs.fake_filesystem import FakeFilesystem


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


def build_language_audit_csv_content() -> str:
  """Build the contents of a language_audit.csv file."""
  return '\n'.join(
    [
      'organisation,sector,page_title,base_url,url,viewport_size,audit_id,page_id,flesch_kincaid_gl,num_sentences,words_per_sentence,syllables_per_word,smog_gl,helpUrl',  # noqa: E501, pylint: disable=line-too-long
      "DIA,R&D,CWAC | Configs,http://localhost:5000,http://localhost:5000/configs,\"{'width': 320, 'height': 450}\",6_small,6,8.501,43,13.558,1.593,11.440,https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/",  # noqa: E501, pylint: disable=line-too-long
      "DIA,R&D,CWAC | Configs,http://localhost:5000,http://localhost:5000/configs,\"{'width': 1280, 'height': 800}\",6_medium,6,8.501,43,13.558,1.593,11.440,https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/",  # noqa: E501, pylint: disable=line-too-long
    ]
  )


class TestViewResults:
  """Tests for the GET /results endpoint."""

  def test_missing_directory_is_ok(self, client: FlaskClient) -> None:
    """Test handling when the results/ directory is missing.

    The page should say that no results were found.
    """

    response = client.get('/results')

    assert response.status_code == 200

    assert b'No results found' in response.data

  def test_empty_directory_is_ok(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the results/ directory is empty.

    The page should say that no results were found.
    """

    fs.makedir('results')

    response = client.get('/results')

    assert response.status_code == 200

    assert b'No results found' in response.data

  def test_results_are_listed(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the results/ directory has content.

    The results should be listed with their files.
    """

    fs.makedir('results')

    # results with nothing in it
    fs.makedir('results/2025-01-01_12-00-00_audit_results')

    # results with just a config
    fs.makedir('results/2025-01-02_12-00-00_audit_results')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-01-02_12-00-00_audit_results/config.json',
    )

    # results with just a config and an output log
    fs.makedir('results/2025-01-03_12-00-00_audit_results')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-01-03_12-00-00_audit_results/config.json',
    )
    fs.create_file(
      'results/2025-01-03_12-00-00_audit_results/2025-01-03_12-00-00_audit_results.log',
      contents=build_audit_results_log_content('2025-01-03'),
    )

    # results with a bunch of stuff
    fs.makedir('results/2025-01-04_12-00-00_audit_results')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-01-04_12-00-00_audit_results/config.json',
    )
    fs.create_file(
      'results/2025-01-04_12-00-00_audit_results/2025-01-04_12-00-00_audit_results.log',
      contents=build_audit_results_log_content('2025-01-04'),
    )
    fs.create_file(
      'results/2025-01-04_12-00-00_audit_results/audit_log.csv',
      contents='\n'.join(
        [
          'organisation,base_url,url,sector',
          'DIA,http://localhost:5000,http://localhost:5000,R&D',
          'DIA,http://localhost:5000,http://localhost:5000/configs,R&D',
          'DIA,http://localhost:5000,http://localhost:5000/urls,R&D',
        ]
      ),
    )
    fs.create_file(
      'results/2025-01-04_12-00-00_audit_results/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )
    fs.create_file(
      'results/2025-01-04_12-00-00_audit_results/pages_scanned.csv',
      contents='\n'.join(
        [
          'organisation,base_url,number_of_pages,sector',
          'DIA,http://localhost:5000,3,R&D',
        ]
      ),
    )
    fs.create_file(
      'results/2025-01-04_12-00-00_audit_results/progress.csv',
      contents='\n'.join(
        [
          'time,iteration,total,speed,percent,elapsed,remaining',
          '1735945200.8321352,1,6,0.18,16.7,0h 0m,0h 0m',
          '1735945201.0728102,2,6,0.34,33.3,0h 0m,0h 0m',
          '1735945203.8444102,3,6,0.34,50.0,0h 0m,0h 0m',
          '1735945204.7461178,4,6,0.42,66.7,0h 0m,0h 0m',
          '1735945206.3876212,5,6,0.44,83.3,0h 0m,0h 0m',
          '1735945206.4044518,5,6,0.44,83.3,0h 0m,0h 0m',
          '1735945208.6121624,6,6,0.44,100.0,0h 0m,0h 0m',
          '1735945208.6308975,6,6,0.44,100.0,0h 0m,0h 0m',
        ]
      ),
    )

    response = client.get('/results')

    assert response.status_code == 200

    # todo: none of this actually asserts the relation of the items properly

    assert b'<h5>results/2025-01-01_12-00-00_audit_results</h5>' in response.data
    assert b'No files found' in response.data

    # results with just a config
    assert b'<h5>results/2025-01-02_12-00-00_audit_results</h5>' in response.data
    assert b'config.json' in response.data

    # results with just a config and an output log
    assert b'<h5>results/2025-01-03_12-00-00_audit_results</h5>' in response.data
    assert b'config.json' in response.data
    assert b'audit_log.csv' in response.data

    # results with a bunch of stuff
    assert b'<h5>results/2025-01-04_12-00-00_audit_results</h5>' in response.data
    assert b'config.json' in response.data
    assert b'language_audit.csv' in response.data

  def test_nested_directories_are_handled_correctly(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when the results/ directory has a result with nested directories.

    The nested directories should be associated with the correct result, but only shown
    if they actually have a file.
    """

    fs.makedir('results')

    # results with just some empty nested directories
    fs.makedir('results/2025-02-01_12-00-00_audit_results')
    fs.makedir('results/2025-02-01_12-00-00_audit_results/inner-dir-empty')
    fs.makedirs('results/2025-02-01_12-00-00_audit_results/inner-dir1/empty-inner-inner-dir')

    # results with just a config file and some empty nested directories
    fs.makedir('results/2025-02-02_12-00-00_audit_results')
    fs.makedirs('results/2025-02-02_12-00-00_audit_results/inner-dir-empty')
    fs.makedirs('results/2025-02-02_12-00-00_audit_results/inner-dir2/empty-inner-inner-dir')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-02-02_12-00-00_audit_results/config.json',
    )

    # results with files, some in nested directories
    fs.makedir('results/2025-02-03_12-00-00_audit_results')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-02-03_12-00-00_audit_results/config.json',
    )
    fs.create_file(
      'results/2025-02-03_12-00-00_audit_results/logs/audit_results.log',
      contents=build_audit_results_log_content('2025-02-03'),
    )
    fs.create_file(
      'results/2025-02-03_12-00-00_audit_results/csvs/internal/progress.csv',
      contents='\n'.join(
        [
          'time,iteration,total,speed,percent,elapsed,remaining',
          '1735945200.8321352,1,6,0.18,16.7,0h 0m,0h 0m',
          '1735945201.0728102,2,6,0.34,33.3,0h 0m,0h 0m',
          '1735945203.8444102,3,6,0.34,50.0,0h 0m,0h 0m',
          '1735945204.7461178,4,6,0.42,66.7,0h 0m,0h 0m',
          '1735945206.3876212,5,6,0.44,83.3,0h 0m,0h 0m',
          '1735945206.4044518,5,6,0.44,83.3,0h 0m,0h 0m',
          '1735945208.6121624,6,6,0.44,100.0,0h 0m,0h 0m',
          '1735945208.6308975,6,6,0.44,100.0,0h 0m,0h 0m',
        ]
      ),
    )
    fs.create_file(
      'results/2025-02-03_12-00-00_audit_results/csvs/audits/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )

    response = client.get('/results')

    assert response.status_code == 200

    # todo: none of this actually asserts the relation of the items properly

    # results with just some empty nested directories
    assert b'<h5>results/2025-02-01_12-00-00_audit_results</h5>' in response.data
    assert b'No files found' in response.data
    assert b'inner-dir-empty' not in response.data
    assert b'inner-dir1' not in response.data
    assert b'empty-inner-inner-dir' not in response.data

    # results with just a config file and some empty nested directories
    assert b'<h5>results/2025-02-02_12-00-00_audit_results</h5>' in response.data
    assert b'config.json' in response.data
    assert b'inner-dir-empty' not in response.data
    assert b'inner-dir2' not in response.data
    assert b'empty-inner-inner-dir' not in response.data

    # results with files, some in nested directories
    assert b'<h5>results/2025-02-03_12-00-00_audit_results</h5>' in response.data
    assert b'config.json' in response.data
    assert b'logs/audit_results.log' in response.data
    assert b'csvs/internal/progress.csv' in response.data
    assert b'csvs/audits/language_audit.csv' in response.data


class TestDownloadResultFile:
  """Tests for the GET /d/results endpoint."""

  def test_results_directories_cannot_be_downloaded(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a results directory without a file.

    A 404 should be returned.
    """
    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedir('results')

    fs.makedir('results/2025-03-01_12-00-00_audit_results')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-03-01_12-00-00_audit_results/config.json',
    )

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results')

    assert response.status_code == 404

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/')

    assert response.status_code == 404

  def test_files_that_do_not_exist_are_handled(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a file that does not exist.

    A 404 should be returned.
    """
    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedir('results')

    fs.makedir('results/2025-03-01_12-00-00_audit_results')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-03-01_12-00-00_audit_results/config.json',
    )

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/default_config.json')

    assert response.status_code == 404

  def test_files_inside_results_can_be_downloaded(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a file that is inside the results/ directory.

    The file contents should be returned.
    """

    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedirs('results/2025-03-01_12-00-00_audit_results')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-03-01_12-00-00_audit_results/config.json',
    )
    fs.create_file(
      'results/2025-03-01_12-00-00_audit_results/logs/audit_results.log',
      contents=build_audit_results_log_content('2025-03-01'),
    )
    fs.create_file(
      'results/2025-03-01_12-00-00_audit_results/audit_log.csv',
      contents='\n'.join(
        [
          'organisation,base_url,url,sector',
          'DIA,http://localhost:5000,http://localhost:5000,R&D',
          'DIA,http://localhost:5000,http://localhost:5000/configs,R&D',
          'DIA,http://localhost:5000,http://localhost:5000/urls,R&D',
        ]
      ),
    )
    fs.create_file(
      'results/2025-03-01_12-00-00_audit_results/language_audit.csv',
      contents=build_language_audit_csv_content(),
    )
    fs.create_file(
      'results/2025-03-01_12-00-00_audit_results/pages_scanned.csv',
      contents='\n'.join(
        [
          'organisation,base_url,number_of_pages,sector',
          'DIA,http://localhost:5000,3,R&D',
        ]
      ),
    )

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/config.json')

    assert response.status_code == 200

    with open('results/2025-03-01_12-00-00_audit_results/config.json', encoding='utf-8') as f:
      assert f.read().encode() == response.data

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/logs/audit_results.log')

    assert response.status_code == 200

    with open('results/2025-03-01_12-00-00_audit_results/logs/audit_results.log', encoding='utf-8') as f:
      assert f.read().encode() == response.data

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/audit_log.csv')

    assert response.status_code == 200

    with open('results/2025-03-01_12-00-00_audit_results/audit_log.csv', encoding='utf-8') as f:
      assert f.read().encode() == response.data

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/language_audit.csv')

    assert response.status_code == 200

    with open('results/2025-03-01_12-00-00_audit_results/language_audit.csv', encoding='utf-8') as f:
      assert f.read().encode() == response.data

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/pages_scanned.csv')

    assert response.status_code == 200

    with open('results/2025-03-01_12-00-00_audit_results/pages_scanned.csv', encoding='utf-8') as f:
      assert f.read().encode() == response.data

  def test_files_outside_results_cannot_be_downloaded(self, client: FlaskClient, fs: FakeFilesystem) -> None:
    """Test handling when given a path for a file that is outside the results/ directory.

    A 404 should be returned.
    """

    # todo: we probably should be accounting for this more widely,
    #  and maybe even be using it in all our fs stuff?
    client.application.root_path = '/'

    fs.makedirs('results/2025-03-01_12-00-00_audit_results')
    fs.add_real_file('config/config_default.json')
    fs.add_real_file(
      'config/config_default.json',
      target_path='results/2025-03-01_12-00-00_audit_results/config.json',
    )
    fs.create_file(
      'results/2025-03-01_12-00-00_audit_results/logs/audit_results.log',
      contents=build_audit_results_log_content('2025-03-01'),
    )

    response = client.get('/d/results/../config/config_default.json')

    assert response.status_code == 404

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/../../config/config_default.json')

    assert response.status_code == 404

    response = client.get('/d/results/%2E%2E/config/config_default.json')

    assert response.status_code == 404

    response = client.get('/d/results/2025-03-01_12-00-00_audit_results/%2E%2E/%2E%2E/config/config_default.json')

    assert response.status_code == 404
