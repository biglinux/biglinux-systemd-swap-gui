#!/usr/bin/env python3
"""
Entry point for BigLinux Swap Manager.

This module sets up logging and launches the GTK application.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import NoReturn

_src_dir = Path(__file__).resolve().parent.parent
if _src_dir.name == "src" and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


def setup_logging() -> None:
    """Configure logging based on environment."""
    log_level = os.environ.get("BIGLINUX_SWAP_LOG_LEVEL", "WARNING").upper()

    # Map level name to logging constant
    level = getattr(logging, log_level, logging.WARNING)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    # Suppress GTK warnings in production
    if level > logging.DEBUG:
        logging.getLogger("gi").setLevel(logging.ERROR)


def main() -> NoReturn:
    """Run the application."""
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.debug("Starting BigLinux Swap Manager")

    # Import here to allow logging setup first
    from biglinux_swap.application import SwapApplication

    app = SwapApplication()
    exit_code = app.run(sys.argv)

    logger.debug("Application exited with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
