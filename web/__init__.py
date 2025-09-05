"""Basic web interface for using CWAC."""

import contextlib
import csv
import os
import secrets
import threading
from typing import Literal, TypedDict, cast

from flask import (
  Flask,
  abort,
  flash,
  redirect,
  render_template,
  request,
  send_from_directory,
  url_for,
)
from flask.typing import ResponseReturnValue

from cwac import CWAC


def fetch_secret_key() -> str:
  """Fetches the secret key from disk, generating it if it does not already exist."""
  with contextlib.suppress(FileExistsError), open('secret_key', 'x', encoding='utf-8') as f:
    f.write(secrets.token_hex())

  with open('secret_key', encoding='utf-8') as f:
    return f.read()


app = Flask(__name__)
app.secret_key = fetch_secret_key()

type CWACState = Literal['idle', 'running', 'finished']


class CWACAlreadyRunningError(RuntimeError):
  """Exception raised when a CWAC session is already running."""


class CWACNotRunError(RuntimeError):
  """Exception raised when a CWAC session has not yet been run."""


class CWACManager:
  """A class for managing runs of CWAC in the background.

  Only one instance of CWAC can be running at a time.
  """

  __thread: threading.Thread | None = None

  __latest_cwac_instance: CWAC | None = None

  @property
  def state(self) -> CWACState:
    """The current state of the manager."""
    if self.__thread is None:
      return 'idle'
    if self.__thread.is_alive():
      return 'running'
    return 'finished'

  def start(self, config_filename: str) -> None:
    """Start a new CWAC run."""
    if self.state == 'running':
      raise CWACAlreadyRunningError()

    self.__thread = threading.Thread(target=self.__run_cwac, args=(config_filename,), daemon=True)
    self.__thread.start()

  def __run_cwac(self, config_filename: str) -> None:
    """Run a new instance of CWAC with the given config file."""
    print(f'running CWAC using {config_filename}')
    self.__latest_cwac_instance = CWAC(config_filename)
    self.__latest_cwac_instance.run()
    print('finished CWACing')

  @property
  def __cwac(self) -> CWAC:
    """Return the latest instance of CWAC to be started.

    An error will be raised if CWAC has not yet been run.
    """
    if self.__latest_cwac_instance is None:
      raise CWACNotRunError()
    return self.__latest_cwac_instance

  def results_directory(self) -> str:
    """Return the path to the results directory for the current CWAC run."""
    return 'results/' + self.__cwac.config.audit_name

  def log_file_path(self) -> str:
    """Return the path to the main log file for the current CWAC run."""
    return self.results_directory() + '/' + self.__cwac.config.audit_name + '.log'


cwac_manager = CWACManager()


# todo: this has been copied from config.py to avoid loading the config
class Endpoint(TypedDict):
  """Holds data for a url that should be audited and potentially crawled."""

  organisation: str
  url: str
  sector: str


class EndpointsFile(TypedDict):
  """Holds a list of endpoints that should be audited and potentially crawled."""

  path: str
  endpoints: list[Endpoint]
  invalid_reason: str


class ScanResult(TypedDict):
  """Holds the outcome of a scan of one or more endpoints."""

  name: str
  files: list[str]


@app.route('/')
def root() -> str:
  """Present a home page."""
  return render_template('index.html')


@app.route('/configs')
def view_configs() -> str:
  """Present a list of available configs."""
  try:
    files = [c for c in os.listdir('./config') if c.endswith('.json')]
  except FileNotFoundError:
    files = []

  return render_template('configs.html', files=files)


@app.route('/configs/<filename>/edit')
def edit_config(filename: str) -> str:
  """Present a form for modifying a config file."""
  filepath = f'./config/{filename}.json'

  try:
    with open(filepath, encoding='utf-8-sig') as f:
      return render_template(
        'configs_edit.html',
        filepath=filepath,
        filename=filename,
        contents=f.read(),
      )
  except FileNotFoundError:
    abort(404)


@app.route('/configs/<filename>', methods=['POST'])
def update_config(filename: str) -> ResponseReturnValue:
  """Update a url CSV with new content."""
  filepath = f'./config/{filename}.json'

  try:
    # todo: clean this up once we've established a proper Config class that can
    #  handle the loading, validating, updating, etc of arbitrary files
    with open(filepath, 'r+', encoding='utf-8') as f:
      contents = request.form.get('contents', '')
      if not isinstance(contents, str) or contents == '':
        flash('contents is required', 'danger')
        return (
          render_template(
            'configs_edit.html',
            filepath=filepath,
            filename=filename,
            contents=f.read(),
          ),
          422,
        )

      # ensure that Unix line endings are in use, even on Windows
      # todo: confirm that this is a good idea; the underlying issue we want to avoid is
      #  having the default config in version control flipping between line endings, which
      #  can come up in particular if you're on WSL as that will use Unix line-endings but
      #  the browser (running in the Windows host) will use Windows line-endings...
      contents = contents.replace('\r\n', '\n')

      f.truncate()
      f.write(contents)
      flash(f'{filepath} has been updated', 'success')
      return redirect(url_for('view_configs'))
  except FileNotFoundError:
    abort(404)


@app.route('/results')
def view_results() -> str:
  """Present a list of results from previous scans."""
  results: list[ScanResult] = []

  for dirname, _, files in os.walk('results'):
    if dirname.count('/') == 0:
      continue
    if dirname.count('/') == 1:
      results.append(ScanResult(name=dirname.removeprefix('results/'), files=files))
    else:
      subname = dirname.removeprefix('results/').removeprefix(results[-1]['name']).removeprefix('/')
      results[-1]['files'] += [f'{subname}/{f}' for f in files]

  return render_template('results.html', results=results)


@app.route('/d/results/<string:name>/<path:file>')
def download_result_file(name: str, file: str) -> ResponseReturnValue:
  """Download a file from a scan results directory."""
  return send_from_directory('../results', f'{name}/{file}', as_attachment=True)


@app.route('/urls')
def view_urls() -> str:
  """Present contents of url CSVs."""
  files: list[EndpointsFile] = []

  # todo: we should be taking the "base_urls_visit_path" of the "current config" into account
  folder_path = './base_urls/visit/'

  with contextlib.suppress(FileNotFoundError):
    for filename in os.listdir(folder_path):
      if filename.endswith('.csv'):
        with open(
          os.path.join(folder_path, filename),
          encoding='utf-8-sig',
          newline='',
        ) as file:
          endpoint_file = EndpointsFile(
            path=os.path.join(folder_path, filename),
            endpoints=[],
            invalid_reason='',
          )
          files.append(endpoint_file)
          reader = csv.reader(file)
          header = next(reader)
          for row in reader:
            if len(row) != 3:
              endpoint_file['invalid_reason'] = 'must have 3 columns'
              break

            subject = cast(Endpoint, dict(zip(header, row)))
            endpoint_file['endpoints'].append(subject)

  return render_template('urls.html', files=files)


@app.route('/urls/<filename>/edit')
def edit_urls(filename: str) -> str:
  """Present a form for modifying a url CSV."""
  # todo: we should be taking the "base_urls_visit_path" of the "current config" into account
  filepath = f'./base_urls/visit/{filename}.csv'

  try:
    with open(filepath, encoding='utf-8-sig') as f:
      return render_template(
        'urls_edit.html',
        filepath=filepath,
        filename=filename,
        contents=f.read(),
      )
  except FileNotFoundError:
    abort(404)


@app.route('/urls/<filename>', methods=['POST'])
def update_urls(filename: str) -> ResponseReturnValue:
  """Update a url CSV with new content."""
  # todo: we should be taking the "base_urls_visit_path" of the "current config" into account
  filepath = f'./base_urls/visit/{filename}.csv'

  try:
    # todo: clean this up once we've established a proper Config class that can
    #  handle the loading, validating, updating, etc of arbitrary files
    with open(filepath, 'r+', encoding='utf-8-sig') as f:
      contents = request.form.get('contents', '')
      if not isinstance(contents, str) or contents == '':
        flash('contents is required', 'danger')
        return (
          render_template(
            'urls_edit.html',
            filepath=filepath,
            filename=filename,
            contents=f.read(),
          ),
          422,
        )

      # ensure that Unix line endings are in use, even on Windows
      # todo: confirm that this is a good idea; the underlying issue we want to avoid is
      #  having the default config in version control flipping between line endings, which
      #  can come up in particular if you're on WSL as that will use Unix line-endings but
      #  the browser (running in the Windows host) will use Windows line-endings...
      contents = contents.replace('\r\n', '\n')

      f.truncate()
      f.write(contents)
      flash(f'{filepath} has been updated', 'success')
      return redirect(url_for('view_urls'))
  except FileNotFoundError:
    abort(404)


def render_scans_new_template() -> str:
  """Render the scans_new.html template."""
  try:
    configs = [c for c in os.listdir('./config') if c.endswith('.json')]
  except FileNotFoundError:
    configs = []

  return render_template('scans_new.html', configs=configs)


@app.route('/scans/new')
def new_scan() -> ResponseReturnValue:
  """Initialize a new scan."""
  return render_scans_new_template()


@app.route('/scans', methods=['POST'])
def create_scan() -> ResponseReturnValue:
  """Initialize a new scan."""
  # todo: ensure config file exists (?)
  config_file = request.form.get('config', '')
  if config_file == '':
    flash('a config file is required', 'danger')
    return render_scans_new_template(), 422

  try:
    cwac_manager.start(config_file)

    flash('scan started', 'success')
    return redirect(url_for('view_scan'))
  except CWACAlreadyRunningError:
    flash('scan already in progress', 'danger')
    return render_scans_new_template(), 422


@app.route('/scans/progress')
def view_scan() -> ResponseReturnValue:
  """View the progress of an ongoing scan."""
  if cwac_manager.state == 'idle':
    flash('no scan in progress', 'warning')
    return redirect(url_for('new_scan'))

  with open(cwac_manager.log_file_path(), encoding='utf-8') as f:
    logs = f.read()

  return render_template('scans_progress.html', manager=cwac_manager, logs=logs)
