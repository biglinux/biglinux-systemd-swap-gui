"""
BigLinux Swap Manager - GTK4/Adwaita GUI for systemd-swap.

This package provides a graphical interface for configuring
systemd-swap on BigLinux systems.
"""

__author__ = "BigLinux Team"
__license__ = "GPL-3.0"

from biglinux_swap.config import (
    APP_ID,
    APP_NAME,
    APP_VERSION,
    Compressor,
    SwapConfig,
    SwapFileConfig,
    SwapMode,
    ZramConfig,
    ZswapConfig,
)

__version__ = APP_VERSION

__all__ = [
    "APP_ID",
    "APP_NAME",
    "APP_VERSION",
    "Compressor",
    "SwapConfig",
    "SwapFileConfig",
    "SwapMode",
    "ZramConfig",
    "ZswapConfig",
    "__version__",
]
