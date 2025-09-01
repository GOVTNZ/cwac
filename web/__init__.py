"""Basic web interface for using CWAC."""

import contextlib
import csv
import os
import secrets
from typing import TypedDict, cast

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue


def fetch_secret_key() -> str:
  """Fetches the secret key from disk, generating it if it does not already exist."""
  with contextlib.suppress(FileExistsError), open('secret_key', 'x', encoding='utf-8') as f:
    f.write(secrets.token_hex())

  with open('secret_key', encoding='utf-8') as f:
    return f.read()


app = Flask(__name__)
app.secret_key = fetch_secret_key()


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
