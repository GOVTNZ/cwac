"""Functions used for verifying the validity of data."""

import logging

from config import config


def verify_axe_results(pages_scanned: dict[str, set[str]]) -> None:
    """Perform a series of checks on the output test.

    Ensures output data is free of obvious errors.

    Args:
        pages_scanned: dict of pages_scanned from Analytics
    """
    # Check that each site had the correct number of pages scanned
    # outputs non-conforming sites to the log
    for key, value in pages_scanned.items():
        correct_len = config.max_links_per_domain
        if len(value) != correct_len:
            logging.warning(
                "VERIFY: %s had %i pages scanned, not %i",
                key,
                len(value),
                correct_len,
            )
