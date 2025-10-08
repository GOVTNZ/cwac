"""Do Something."""

import http.server
import socketserver
import typing

PORT = 8000
DIRECTORY = 'pages'


class Handler(http.server.SimpleHTTPRequestHandler):
  """Something."""

  def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
    """Do Something."""
    super().__init__(*args, directory=DIRECTORY, **kwargs)


with socketserver.TCPServer(('', PORT), Handler) as httpd:
  print(f'Serving at http://localhost:{PORT}/ from ./{DIRECTORY}')
  httpd.serve_forever()
