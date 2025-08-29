import os

from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def root() -> str:
  return render_template('index.html')


@app.route('/configs')
def view_configs() -> str:
  return render_template(
    'configs.html',
    files=[c for c in os.listdir('./config') if c.endswith('.json')],
  )


@app.route('/urls')
def view_urls() -> str:
  return render_template(
    'urls.html',
    # todo: we should be taking the "base_urls_visit_path" of the "current config" into account
    files=[c for c in os.listdir('./base_urls/visit') if c.endswith('.csv')],
  )
