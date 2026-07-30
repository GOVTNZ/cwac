#!/usr/bin/env python3

"""Minimal Selenium smoke test for CWAC Chrome/chromedriver setup."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver


def find_chrome_binary(repo_root: Path) -> Path | None:
  """Return a Chrome for Testing binary path for the current OS/architecture."""
  system = platform.system()
  machine = platform.machine().lower()

  binary_pattern = None

  if system == 'Darwin' and machine in {'arm64', 'aarch64'}:
    binary_pattern = (
      'chrome/mac_arm-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'
    )
  elif system == 'Darwin' and machine in {'x86_64', 'amd64'}:
    binary_pattern = (
      'chrome/mac_x64-*/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'
    )
  elif system == 'Linux' and machine in {'x86_64', 'amd64'}:
    binary_pattern = 'chrome/linux-*/chrome-linux64/chrome'

  if binary_pattern is None:
    return None

  candidates = sorted(repo_root.glob(binary_pattern))
  if not candidates:
    return None
  return candidates[-1]


def default_chromedriver(repo_root: Path) -> Path | None:
  """Return default chromedriver path for the current OS and architecture."""
  system = platform.system()
  machine = platform.machine().lower()

  driver_name = None

  if system == 'Darwin' and machine in {'arm64', 'aarch64'}:
    driver_name = 'chromedriver_mac_arm64'
  elif system == 'Darwin' and machine in {'x86_64', 'amd64'}:
    driver_name = 'chromedriver_mac_x64'
  elif system == 'Linux' and machine in {'x86_64', 'amd64'}:
    driver_name = 'chromedriver_linux_x64'

  if driver_name is None:
    return None

  return repo_root / 'drivers' / driver_name


def main() -> int:
  """Run a minimal Selenium smoke test to verify Chrome/chromedriver setup."""
  repo_root = Path(__file__).resolve().parent.parent

  chrome_driver = default_chromedriver(repo_root)
  chrome_binary = find_chrome_binary(repo_root)

  if chrome_driver is None:
    print('ERROR: unsupported OS/architecture for automatic chromedriver selection.')
    return 1

  if not chrome_driver.exists():
    print(f'ERROR: chromedriver not found at {chrome_driver}')
    return 1

  if chrome_binary is None or not chrome_binary.exists():
    print('ERROR: Chrome for Testing binary not found.')
    return 1

  options = webdriver.ChromeOptions()
  options.binary_location = str(chrome_binary)
  options.add_argument('--headless=new')

  test_url = 'https://github.com'
  driver = None
  try:
    driver = WebDriver(service=Service(str(chrome_driver)), options=options)
    driver.set_page_load_timeout(30)
    driver.get(test_url)
    print(f'SUCCESS: Selenium started Chrome and loaded {test_url}')
    print(f'URL: {driver.current_url}')
    print(f'Title: {driver.title}')
    return 0
  except Exception as exc:  # pylint: disable=broad-exception-caught
    print(f'ERROR: Selenium smoke test failed: {exc}')
    return 1
  finally:
    if driver is not None:
      driver.quit()


if __name__ == '__main__':
  sys.exit(main())
