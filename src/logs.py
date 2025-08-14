"""Logging helpers."""

import logging
import os
import re
import threading
from contextlib import contextmanager
from typing import Any, Callable, Generator


def __register_thread_based_file_handler(directory: str, prefix: str) -> logging.Handler:
    thread_name = threading.current_thread().name
    log_file = f"{directory}/{prefix}{thread_name}.log"

    log_handler = create_file_log_handler(log_file)
    log_handler.addFilter(lambda record: record.threadName == thread_name)

    logging.getLogger().addHandler(log_handler)

    return log_handler


def __create_and_register_selective_file_handler(
    log_file: str, selector: Callable[[logging.LogRecord], bool | logging.LogRecord]
) -> logging.Handler:
    log_handler = create_file_log_handler(log_file)
    log_handler.addFilter(selector)

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


# todo: who knows if this is thread safe enough...
matchups = {}


def sanitise_string(string: str) -> str:
    """Sanitise a string for use in a folder/filename.

    Args:
        string (str): the string to sanitise

    Returns:
        str: a sanitised string
    """
    temp_str = string.strip()
    temp_str = re.sub(r"[^a-zA-Z0-9_\-.]", "_", temp_str)
    temp_str = re.sub(r"_+", "_", temp_str)
    temp_str = temp_str[:50]
    return temp_str


@contextmanager
def group_by_base_url(directory: str, base_url: str) -> Generator[None, Any, None]:
    """Group logs for the given base_url into a dedicated secondary file."""
    os.makedirs(directory, exist_ok=True)
    safe_base_url = sanitise_string(base_url)

    matchups[threading.current_thread().ident] = base_url
    log_handler = __create_and_register_selective_file_handler(
        f"{directory}/{safe_base_url}.log",
        lambda record: matchups.get(record.thread, "") == base_url,
    )

    try:
        yield
    finally:
        logging.getLogger().removeHandler(log_handler)
        log_handler.close()
