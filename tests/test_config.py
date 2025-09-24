"""Tests the behaviour of the Config class."""

import json
import platform

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from pytest_mock import MockerFixture

from config import Config


@pytest.fixture(autouse=True)
def setup_filesystem(fs: FakeFilesystem) -> None:
    """Set up the filesystem."""
    fs.add_real_file("package.json", read_only=False)
    fs.makedirs("base_urls/visit")


def mock_platform(mocker: MockerFixture, system: str, machine: str) -> None:
    """Patch platform.uname to return the specified system and machine."""
    # uname_result is a "named tuple"-like object of 6 values, but it handles the
    # last value lazily so it actually only allows being passed 5 values
    # noinspection PyArgumentList
    mocker.patch("platform.uname", return_value=platform.uname_result(system, "", "", "", machine))


def test_loading_missing_config_raises_file_not_found() -> None:
    """Raises FileNotFoundError if the config file is missing."""
    with pytest.raises(FileNotFoundError):
        Config("does/not/exist")


def test_valid_config_is_successfully_loaded(fs: FakeFilesystem) -> None:
    """Validates that the config is loaded correctly."""
    fs.add_real_file("config/config_default.json")

    config = Config("config_default.json")

    with open("config/config_default.json", encoding="utf-8") as f:
        raw = json.load(f)

        # assert a few of the properties match, as a sense check
        assert config.headless == raw["headless"]
        assert config.thread_count == raw["thread_count"]
        assert config.user_agent == raw["user_agent"]
        assert config.base_urls_visit_path == raw["base_urls_visit_path"]


class TestChromeLocationsAutoResolution:
    """Tests automatic resolution of Chrome binary and driver locations."""

    @pytest.mark.parametrize(
        "system,machine,expected_binary_location,expected_driver_location",
        [
            ("Linux", "x86_64", "./chrome/linux-123-abc/chrome-linux64/", "./drivers/chromedriver_linux_x64"),
            ("Darwin", "arm64", "./chrome/mac_arm-123-abc/chrome-mac-arm64/", "./drivers/chromedriver_mac_arm64"),
        ],
    )
    def test_auto_resolves_for_supported_platforms(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        fs: FakeFilesystem,
        mocker: MockerFixture,
        system: str,
        machine: str,
        expected_binary_location: str,
        expected_driver_location: str,
    ) -> None:
        """Resolves the correct paths for OSs and architectures that are supported for automatic resolution."""
        fs.add_real_file("config/config_default.json")

        with open("package.json", "w+", encoding="utf-8") as f:
            f.write(json.dumps({"config": {"chromeVersion": "123-abc"}}))

        mock_platform(mocker, system, machine)

        config = Config("config_default.json")

        assert config.chrome_binary_location.startswith(expected_binary_location)
        assert config.chrome_driver_location == expected_driver_location

    @pytest.mark.parametrize(
        "system,machine",
        [
            ("Linux", "arm64"),
            ("Darwin", "x86_64"),
            ("Windows", "x86_64"),
            ("Windows", "arm64"),
        ],
    )
    def test_auto_raises_for_unsupported_platforms(
        self,
        fs: FakeFilesystem,
        mocker: MockerFixture,
        system: str,
        machine: str,
    ) -> None:
        """Raises an error when running on an OS or architecture that is not supported for automatic resolution."""
        fs.add_real_file("config/config_default.json")

        with open("package.json", "w+", encoding="utf-8") as f:
            f.write(json.dumps({"config": {"chromeVersion": "123-abc"}}))

        mock_platform(mocker, system, machine)

        with pytest.raises(ValueError):
            Config("config_default.json")

    def test_manual_locations_are_preserved(self, fs: FakeFilesystem) -> None:
        """Preserves manually configured chrome_binary_location and chrome_driver_location."""
        fs.add_real_file("config/config_default.json", read_only=False)

        with open("config/config_default.json", "r+", encoding="utf-8") as f:
            c = {
                **json.load(f),
                "chrome_binary_location": "/home/user/.cache/selenium/chrome/linux64/139.0.7258.68",
                "chrome_driver_location": "/home/user/.cache/selenium/chromedriver/linux64/139.0.7258.68",
            }
            f.seek(0)
            json.dump(c, f)
            f.truncate()

        with open("package.json", "w+", encoding="utf-8") as f:
            f.write(json.dumps({"config": {"chromeVersion": "123-abc"}}))

        config = Config("config_default.json")

        assert config.chrome_binary_location == "/home/user/.cache/selenium/chrome/linux64/139.0.7258.68"
        assert config.chrome_driver_location == "/home/user/.cache/selenium/chromedriver/linux64/139.0.7258.68"
