"""Logging helpers."""

import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Generator


def __register_thread_based_file_handler(directory: str, prefix: str) -> logging.Handler:
    thread_name = threading.current_thread().name
    log_file = f"{directory}/{prefix}{thread_name}.log"

    log_handler = create_file_log_handler(log_file)
    log_handler.addFilter(lambda record: record.threadName == thread_name)

    logging.getLogger().addHandler(log_handler)

    return log_handler


def create_file_log_handler(log_file: str) -> logging.FileHandler:
    """Create a file-based logging handler."""
    log_handler = logging.FileHandler(log_file)
    log_handler.setLevel(logging.INFO)

    log_handler.setFormatter(
        logging.Formatter(
            "[{%(asctime)s} %(levelname)-7s %(filename)10s : %(lineno)-4s] %(funcName)30s %(message)s %(threadName)s",
            # Log timestamp format (ISO 8601)
            "%Y-%m-%dT%H:%M:%S%z",
        )
    )

    return log_handler


@contextmanager
def group_by_thread(directory: str, prefix: str) -> Generator[None, Any, None]:
    """Group logs made by the current thread into a secondary file."""
    os.makedirs(directory, exist_ok=True)
    log_handler = __register_thread_based_file_handler(directory, prefix)
    try:
        yield
    finally:
        logging.getLogger().removeHandler(log_handler)
        log_handler.close()
