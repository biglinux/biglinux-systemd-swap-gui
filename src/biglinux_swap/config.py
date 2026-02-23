#!/usr/bin/env python3
"""
Configuration module for BigLinux Swap Manager.

Contains all constants, dataclasses, and configuration management
following strict typing and PEP standards.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version
from pathlib import Path
from typing import Any

from biglinux_swap.i18n import _

logger = logging.getLogger(__name__)

# =============================================================================
# Application Constants
# =============================================================================

APP_ID = "br.com.biglinux.swap"
APP_NAME = _("Swap Manager")
try:
    APP_VERSION = _metadata_version("biglinux-swap")
except PackageNotFoundError:
    APP_VERSION = "1.0.0"
APP_WEBSITE = "https://github.com/biglinux/biglinux-systemd-swap-gui"

# =============================================================================
# Window Configuration
# =============================================================================

WINDOW_WIDTH_DEFAULT = 800
WINDOW_HEIGHT_DEFAULT = 750

# =============================================================================
# Path Configuration
# =============================================================================

# System configuration paths
CONFIG_FILE = Path("/etc/systemd/swap.conf")
CONFIG_PATH = "/etc/systemd/swap.conf"  # String version for subprocess
DEFAULT_CONFIG = Path("/usr/share/systemd-swap/swap-default.conf")
MEMINFO_PATH = Path("/proc/meminfo")

# User config paths
USER_CONFIG_DIR = Path.home() / ".config" / "biglinux-swap"
USER_SETTINGS_FILE = USER_CONFIG_DIR / "settings.json"

# Scripts path

# =============================================================================
# Memory Chart Configuration
# =============================================================================

CHART_MAX_HISTORY = 60  # 60 seconds of history
CHART_UPDATE_INTERVAL_MS = 1000  # 1 second

# =============================================================================
# Enumerations
# =============================================================================


class SwapMode(Enum):
    """Available swap modes."""

    AUTO = "auto"
    ZSWAP_SWAPFILE = "zswap+swapfile"
    ZRAM_SWAPFILE = "zram+swapfile"
    ZRAM_ONLY = "zram"
    DISABLED = "disabled"


SWAP_MODE_NAMES: dict[SwapMode, str] = {
    SwapMode.AUTO: _("Auto (Recommended)"),
    SwapMode.ZSWAP_SWAPFILE: _("Zswap + SwapFile"),
    SwapMode.ZRAM_SWAPFILE: _("Zram + SwapFile"),
    SwapMode.ZRAM_ONLY: _("Zram Only"),
    SwapMode.DISABLED: _("Disabled"),
}

SWAP_MODE_DESCRIPTIONS: dict[SwapMode, str] = {
    SwapMode.AUTO: _("Automatically detects the best mode for your system"),
    SwapMode.ZSWAP_SWAPFILE: _(
        "Zswap RAM compression cache + dynamic swap files (best for ext4/xfs)"
    ),
    SwapMode.ZRAM_SWAPFILE: _(
        "Zram fast compressed block device in RAM + dynamic swap files for overflow"
    ),
    SwapMode.ZRAM_ONLY: _(
        "Only Zram, no disk swap (for systems without disk swap support)"
    ),
    SwapMode.DISABLED: _("Disable swap management (stops the service)"),
}


class Compressor(Enum):
    """Available compression algorithms."""

    LZ4 = "lz4"
    ZSTD = "zstd"
    LZO = "lzo"


COMPRESSOR_NAMES: dict[Compressor, str] = {
    Compressor.LZ4: _("LZ4 (Fastest)"),
    Compressor.ZSTD: _("Zstd (Balanced)"),
    Compressor.LZO: _("LZO (Legacy)"),
}


# =============================================================================
# Configuration Limits
# =============================================================================

# Zswap limits
ZSWAP_MAX_POOL_MIN = 10
ZSWAP_MAX_POOL_MAX = 80
ZSWAP_MAX_POOL_DEFAULT = 45

ZSWAP_ACCEPT_THRESHOLD_MIN = 50
ZSWAP_ACCEPT_THRESHOLD_MAX = 100
ZSWAP_ACCEPT_THRESHOLD_DEFAULT = 80

# Zram limits
ZRAM_SIZE_MIN = 10
ZRAM_SIZE_MAX = 300
ZRAM_SIZE_DEFAULT = 150

ZRAM_PRIORITY_MIN = 1
ZRAM_PRIORITY_MAX = 32767
ZRAM_PRIORITY_DEFAULT = 32767

# =============================================================================
# SwapFile limits
# =============================================================================

SWAPFILE_MIN_COUNT = 1
SWAPFILE_MAX_COUNT_MIN = 1
SWAPFILE_MAX_COUNT_MAX = 28
SWAPFILE_MAX_COUNT_DEFAULT = 28

SWAPFILE_MIN_COUNT_UI_MIN = 0
SWAPFILE_MIN_COUNT_UI_MAX = 10

SWAPFILE_FREE_RAM_PERC_MIN = 5
SWAPFILE_FREE_RAM_PERC_MAX = 40
SWAPFILE_FREE_RAM_PERC_DEFAULT = 20

SWAPFILE_FREE_SWAP_PERC_MIN = 10
SWAPFILE_FREE_SWAP_PERC_MAX = 60
SWAPFILE_FREE_SWAP_PERC_DEFAULT = 40

SWAPFILE_REMOVE_FREE_SWAP_PERC_MIN = 50
SWAPFILE_REMOVE_FREE_SWAP_PERC_MAX = 90
SWAPFILE_REMOVE_FREE_SWAP_PERC_DEFAULT = 70


# =============================================================================
# Chunk Size Options
# =============================================================================

CHUNK_SIZE_OPTIONS = ["256M", "512M", "1G", "2G", "4G", "8G"]
CHUNK_SIZE_DEFAULT = "512M"


# =============================================================================
# Storage and Virtualization Types (PLANNING.md 12.5, 12.6)
# =============================================================================


class StorageType(Enum):
    """Storage device types for priority calculation."""

    NVME = "nvme"
    SSD = "ssd"
    HDD = "hdd"
    EMMC = "emmc"
    SD = "sd"
    UNKNOWN = "unknown"


STORAGE_TYPE_NAMES: dict[StorageType, str] = {
    StorageType.NVME: _("NVMe SSD"),
    StorageType.SSD: _("SATA SSD"),
    StorageType.HDD: _("Hard Drive"),
    StorageType.EMMC: _("eMMC"),
    StorageType.SD: _("SD Card"),
    StorageType.UNKNOWN: _("Unknown"),
}

# Swap priorities by storage type (PLANNING.md 12.6.3)
STORAGE_SWAP_PRIORITY: dict[StorageType, int] = {
    StorageType.NVME: 100,
    StorageType.SSD: 75,
    StorageType.EMMC: 50,
    StorageType.SD: 25,
    StorageType.HDD: 10,
    StorageType.UNKNOWN: 0,
}


class VirtualizationType(Enum):
    """Virtualization environment types (PLANNING.md 12.5)."""

    NONE = "none"  # Bare metal
    KVM = "kvm"
    VMWARE = "vmware"
    VIRTUALBOX = "oracle"
    XEN = "xen"
    HYPERV = "microsoft"
    DOCKER = "docker"
    LXC = "lxc"
    WSL = "wsl"
    OTHER = "other"


class DiscardPolicy(Enum):
    """Discard/TRIM policies for SSDs (PLANNING.md 12.6.2)."""

    NONE = "none"  # No TRIM
    ONCE = "once"  # TRIM at swapoff only
    PAGES = "pages"  # Continuous TRIM
    BOTH = "both"  # once + pages
    AUTO = "auto"  # Auto-detect based on storage


DISCARD_POLICY_NAMES: dict[DiscardPolicy, str] = {
    DiscardPolicy.NONE: _("Disabled"),
    DiscardPolicy.ONCE: _("At deactivation (recommended)"),
    DiscardPolicy.PAGES: _("Continuous (may impact performance)"),
    DiscardPolicy.BOTH: _("Both modes"),
    DiscardPolicy.AUTO: _("Auto-detect"),
}


# =============================================================================
# Dataclasses for Configuration
# =============================================================================


@dataclass
class ZswapConfig:
    """Zswap configuration."""

    compressor: Compressor = Compressor.ZSTD
    max_pool_percent: int = ZSWAP_MAX_POOL_DEFAULT
    zpool: str = "zsmalloc"
    shrinker_enabled: bool = False
    accept_threshold: int = ZSWAP_ACCEPT_THRESHOLD_DEFAULT


@dataclass
class ZramConfig:
    """Zram configuration."""

    size_percent: int = ZRAM_SIZE_DEFAULT
    alg: Compressor = Compressor.ZSTD
    priority: int = ZRAM_PRIORITY_DEFAULT


@dataclass
class SwapFileConfig:
    """SwapFile configuration."""

    enabled: bool = True
    path: str = "/swapfile"
    chunk_size: str = CHUNK_SIZE_DEFAULT
    max_count: int = SWAPFILE_MAX_COUNT_DEFAULT
    min_count: int = SWAPFILE_MIN_COUNT

    # Performance optimizations
    discard_policy: DiscardPolicy = DiscardPolicy.AUTO
    priority: int = -1  # -1 = auto-calculate based on storage type

    # Dynamic thresholds for expansion/contraction
    free_ram_perc: int = SWAPFILE_FREE_RAM_PERC_DEFAULT
    free_swap_perc: int = SWAPFILE_FREE_SWAP_PERC_DEFAULT
    remove_free_swap_perc: int = SWAPFILE_REMOVE_FREE_SWAP_PERC_DEFAULT


@dataclass
class SwapFileInfo:
    """Information about an individual swap file."""

    path: str = ""
    size_bytes: int = 0
    used_bytes: int = 0
    is_active: bool = False
    priority: int = 0


@dataclass
class SwapConfig:
    """Complete swap configuration."""

    mode: SwapMode = SwapMode.AUTO
    zswap: ZswapConfig = field(default_factory=ZswapConfig)
    zram: ZramConfig = field(default_factory=ZramConfig)
    swapfile: SwapFileConfig = field(default_factory=SwapFileConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for JSON serialization."""
        data = asdict(self)
        data["mode"] = self.mode.value
        data["zswap"]["compressor"] = self.zswap.compressor.value
        data["zram"]["alg"] = self.zram.alg.value
        data["swapfile"]["discard_policy"] = self.swapfile.discard_policy.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwapConfig:
        """Create config from dictionary."""
        config = cls()

        if "mode" in data:
            config.mode = SwapMode(data["mode"])

        if "zswap" in data:
            zs = data["zswap"]
            max_pool = zs.get("max_pool_percent", ZSWAP_MAX_POOL_DEFAULT)
            max_pool = max(ZSWAP_MAX_POOL_MIN, min(ZSWAP_MAX_POOL_MAX, max_pool))
            accept_thresh = zs.get("accept_threshold", ZSWAP_ACCEPT_THRESHOLD_DEFAULT)
            accept_thresh = max(
                ZSWAP_ACCEPT_THRESHOLD_MIN,
                min(ZSWAP_ACCEPT_THRESHOLD_MAX, accept_thresh),
            )
            config.zswap = ZswapConfig(
                compressor=Compressor(zs.get("compressor", "zstd")),
                max_pool_percent=max_pool,
                zpool=zs.get("zpool", "zsmalloc"),
                shrinker_enabled=zs.get("shrinker_enabled", True),
                accept_threshold=accept_thresh,
            )

        if "zram" in data:
            zr = data["zram"]
            size_pct = zr.get("size_percent", ZRAM_SIZE_DEFAULT)
            size_pct = max(ZRAM_SIZE_MIN, min(ZRAM_SIZE_MAX, size_pct))
            priority = zr.get("priority", ZRAM_PRIORITY_DEFAULT)
            priority = max(ZRAM_PRIORITY_MIN, min(ZRAM_PRIORITY_MAX, priority))
            config.zram = ZramConfig(
                size_percent=size_pct,
                alg=Compressor(zr.get("alg", "zstd")),
                priority=priority,
            )

        sf = data.get("swapfile", {})
        if sf:
            discard_str = sf.get("discard_policy", "auto")
            try:
                discard_policy = DiscardPolicy(discard_str)
            except ValueError:
                discard_policy = DiscardPolicy.AUTO

            max_count = sf.get("max_count", SWAPFILE_MAX_COUNT_DEFAULT)
            max_count = max(
                SWAPFILE_MAX_COUNT_MIN, min(SWAPFILE_MAX_COUNT_MAX, max_count)
            )

            config.swapfile = SwapFileConfig(
                enabled=sf.get("enabled", True),
                path=sf.get("path", "/swapfile"),
                chunk_size=sf.get("chunk_size", CHUNK_SIZE_DEFAULT),
                max_count=max_count,
                min_count=sf.get("min_count", SWAPFILE_MIN_COUNT),
                discard_policy=discard_policy,
                priority=sf.get("priority", -1),
                free_ram_perc=sf.get("free_ram_perc", SWAPFILE_FREE_RAM_PERC_DEFAULT),
                free_swap_perc=sf.get(
                    "free_swap_perc", SWAPFILE_FREE_SWAP_PERC_DEFAULT
                ),
                remove_free_swap_perc=sf.get(
                    "remove_free_swap_perc", SWAPFILE_REMOVE_FREE_SWAP_PERC_DEFAULT
                ),
            )

        return config
