"""AxeCoreAudit plugin.

This plugin uses axe-core to test a webpage.
"""

import hashlib
import sys
from logging import getLogger
from typing import Any

import selenium

from config import Config
from src.audit_manager import AuditManager
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser

logger = getLogger("cwac")


class AxeCoreAudit(DefaultAudit):
    """axe-core audit."""

    audit_type = "AxeCoreAudit"

    def __init__(self, config: Config, browser: Browser, **kwargs: Any) -> None:
        """Init variables."""
        super().__init__(config, browser, **kwargs)
        self.base_url = kwargs["site_data"]["url"]
        self.viewport_size = kwargs["viewport_size"]
        self.best_practice = self.config.audit_plugins["axe_core_audit"]["best-practice"]

    def best_practice_string(self, best_practice: bool) -> str:
        """Return best practice string for reports."""
        return "Yes" if best_practice else "No"

    def axe_core_issue_hash(
        self,
        violation: dict[Any, Any],
        node: dict[Any, Any],
    ) -> str:
        """Return a hash of an axe-core issue."""
        # hashes are calculated with: "base_url", "id", "html", "viewport_size"

        raw_str = self.base_url + violation["id"] + node["html"] + str(self.viewport_size)

        return hashlib.shake_256(raw_str.encode()).hexdigest(5)

    def load_axe_core(self) -> None:
        """Load axe.min.js into a string."""
        if not AuditManager.axe_core_js:
            try:
                with open("./node_modules/axe-core/axe.min.js", encoding="utf-8-sig") as file:
                    logger.info("Reading axe.min.js")
                    axe_min_js = file.read()
            except FileNotFoundError:
                logger.exception("axe.min.js not found. Please run `npm install`")
                print("axe.min.js not found. Please run `npm install`")
                sys.exit(1)
            run_axe = (
                "var callback = arguments[arguments.length - 1];"
                "axe.run({xpath: true, "
                "resultTypes:['violations']"
                "}).then((r)=> {callback(r)});"
            )
            AuditManager.axe_core_js = "".join((axe_min_js, run_axe))

    def run_generate_expanded_results(self, axe_core_results: dict[Any, Any]) -> list[dict[Any, Any]]:
        """Generate an expanded list of axe-core violations.

        Args:
            axe_core_results (dict[Any, Any]): axe_core_results from axe.min.js
        Returns:
            list[dict[Any, Any]]: a list of axe-core violations
        """
        # Stores test output rows
        expanded_results = []

        # Iterate through all axe-core violations
        for violation in axe_core_results["violations"]:
            # Iterate through each instance of a specific violation
            for node in violation["nodes"]:
                # If the config is set to exclude best-practice
                # rules, continue
                if not self.best_practice and "best-practice" in violation["tags"]:
                    continue

                # Truncate html to 100 characters so
                # the CSV is not too chonky
                best_practice_str = self.best_practice_string("best-practice" in violation["tags"])
                results_dict = {
                    "audit_type": AxeCoreAudit.audit_type,
                    "issue_id": self.axe_core_issue_hash(node=node, violation=violation),
                    "description": violation["description"],
                    "target": node["xpath"][0],
                    "num_issues": 1,
                    "help": violation["help"],
                    "helpUrl": violation["helpUrl"],
                    "id": violation["id"],
                    "impact": node["impact"],
                    "html": node["html"][:100],
                    "tags": violation["tags"],
                    "best-practice": best_practice_str,
                }
                expanded_results.append(results_dict)

        # If a website has no axe-core issues, provide default data
        if len(expanded_results) == 0:
            expanded_results.append(
                {
                    "audit_type": AxeCoreAudit.audit_type,
                    "issue_id": "",
                    "description": "No issues found",
                    "target": "",
                    "num_issues": 0,
                    "help": "",
                    "helpUrl": "",
                    "id": "",
                    "impact": "",
                    "html": "",
                    "tags": "",
                    "best-practice": "No",
                }
            )

        return expanded_results

    def run(self) -> list[dict[str, Any]] | bool:
        """Run an axe-core on a specified URL.

        Returns:
            list[Any]: rows of test data
            bool: False if test fails, else a list of results
        """
        self.load_axe_core()

        try:
            logger.info("Injecting axe %s", self.url)
            axe_core_results = self.browser.driver.execute_async_script(AuditManager.axe_core_js)
            logger.info("axe-core has returned results %s", self.url)
        except selenium.common.exceptions.JavascriptException:
            logger.exception("JavaScript exception %s", self.url)
            return False
        except selenium.common.exceptions.TimeoutException:
            logger.exception("Timeout exception %s", self.url)
            return False

        # Get page information from DefaultAudit
        default_audit_row = self._default_audit_row

        expanded_results = self.run_generate_expanded_results(axe_core_results)

        # Add default_test_row to all results
        final_output = []
        for axe_row in expanded_results:
            final_output.append({**default_audit_row, **axe_row})
        return final_output
