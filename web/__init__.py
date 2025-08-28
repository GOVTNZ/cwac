from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def root() -> str:
  return render_template('index.html')


@app.route('/configs')
def view_configs() -> str:
  return render_template('configs.html')


@app.route('/urls')
def view_urls() -> str:
  return render_template('urls.html')
