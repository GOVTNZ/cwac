import contextlib
import csv
import os
from typing import TypedDict, cast

from flask import Flask, render_template

app = Flask(__name__)


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
  return render_template('index.html')


@app.route('/configs')
def view_configs() -> str:
  try:
    files = [c for c in os.listdir('./config') if c.endswith('.json')]
  except FileNotFoundError:
    files = []

  return render_template('configs.html', files=files)


@app.route('/urls')
def view_urls() -> str:
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
