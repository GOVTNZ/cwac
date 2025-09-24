"""Functions used for verifying the validity of data."""

import logging

logger = logging.getLogger("cwac")


def verify_axe_results(max_links_per_domain: int, pages_scanned: dict[str, set[str]]) -> None:
    """Perform a series of checks on the output test.

    Ensures output data is free of obvious errors.

    Args:
        max_links_per_domain: number of max links expected per domain
        pages_scanned: dict of pages_scanned from Analytics
    """
    # Check that each site had the correct number of pages scanned
    # outputs non-conforming sites to the log
    for key, value in pages_scanned.items():
        correct_len = max_links_per_domain
        if len(value) != correct_len:
            logger.warning(
                "VERIFY: %s had %i pages scanned, not %i",
                key,
                len(value),
                correct_len,
            )
