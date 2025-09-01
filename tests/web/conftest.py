"""Setups common fixtures for tests."""

import os

import pytest
from flask.testing import FlaskClient
from pyfakefs.fake_filesystem import FakeFilesystem

import web


@pytest.fixture(autouse=True)
def setup_filesystem(fs: FakeFilesystem) -> None:
  """Set up the filesystem."""
  # flask.testing requires metadata for this package to be available
  fs.add_package_metadata('werkzeug')

  # add the web directory so we can access files like templates
  fs.add_real_directory(os.path.dirname(web.__file__))


@pytest.fixture(name='client')
def fixture_client() -> FlaskClient:
  """Return a Flask client."""
  return web.app.test_client()
