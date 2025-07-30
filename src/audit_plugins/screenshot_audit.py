"""Screenshot Audit plugin."""

import contextlib
import logging
import os
from typing import Any

import cv2
import numpy as np

from config import config
from src.audit_plugins.default_audit import DefaultAudit


class ScreenshotAudit(DefaultAudit):
    """Screenshot Audit."""

    audit_type = "ScreenshotAudit"

    def screenshot(self) -> Any:
        """Take a screenshot of the page that's loaded in the browser.

        Returns:
            Any: the screenshot
        """
        return cv2.imdecode(
            np.frombuffer(self.browser.driver.get_screenshot_as_png(), np.uint8),
            cv2.IMREAD_COLOR,
        )

    def run(self) -> list[dict[str, Any]] | bool:
        """Run the audit.

        Returns:
            bool: if the audit fails
            list[dict[Any, Any]]: a list of audit result dicts
        """
        # create ./results/{config.audit_name}/screenshots folder
        # if it doesn't exist
        if not os.path.exists("results/" + config.audit_name + "/screenshots"):
            with contextlib.suppress(FileExistsError):
                os.makedirs("results/" + config.audit_name + "/screenshots")

        # Take screenshot of the browser and save it as a PNG in /screenshots
        # With a unique filename

        screenshot_path = "results/" + config.audit_name + "/screenshots/" + self.audit_id + ".png"

        # Get browser source code
        # source = self.browser.get_page_source()

        # Write source code to file

        # with open(
        #     "results/"
        #     + config.audit_name
        #     + "/screenshots/"
        #     + self.audit_id
        #     + ".html",
        #     "w",
        #     encoding="utf-8-sig",
        # ) as file:
        #     file.write(source)

        try:
            cv2.imwrite(
                screenshot_path,
                self.screenshot(),
                [cv2.IMWRITE_PNG_COMPRESSION, 9],
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("Failed to save screenshot")
            return False

        return [
            {
                **self._default_audit_row,
                "audit_type": ScreenshotAudit.audit_type,
                "screenshot": self.audit_id + ".png",
            }
        ]
