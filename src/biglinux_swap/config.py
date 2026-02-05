#!/usr/bin/env python3
"""
Configuration module for BigLinux Swap Manager.

Contains all constants, dataclasses, and configuration management
following strict typing and PEP standards.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# Application Constants
# =============================================================================

APP_ID = "br.com.biglinux.swap"
APP_NAME = "Swap Manager"
APP_VERSION = "1.0.0"
APP_DEVELOPER = "BigLinux Team"
APP_WEBSITE = "https://github.com/biglinux/biglinux-systemd-swap-gui"
APP_ISSUE_URL = f"{APP_WEBSITE}/issues"
APP_ICON = "biglinux-swap"


# =============================================================================
# Window Configuration
# =============================================================================

WINDOW_WIDTH_DEFAULT = 800
WINDOW_HEIGHT_DEFAULT = 750
WINDOW_WIDTH_MIN = 450
WINDOW_HEIGHT_MIN = 550

# =============================================================================
# UI Spacing Constants
# =============================================================================

MARGIN_SMALL = 6
MARGIN_DEFAULT = 12
MARGIN_LARGE = 24
SPACING_SMALL = 6
SPACING_DEFAULT = 12
SPACING_LARGE = 24

# =============================================================================
# Path Configuration
# =============================================================================

# System configuration paths
CONFIG_FILE = Path("/etc/systemd/swap.conf")
CONFIG_PATH = "/etc/systemd/swap.conf"  # String version for subprocess
DEFAULT_CONFIG = Path("/usr/share/systemd-swap/swap-default.conf")
MEMINFO_PATH = Path("/proc/meminfo")
WORK_DIR = Path("/run/systemd/swap")

# User config paths
USER_CONFIG_DIR = Path.home() / ".config" / "biglinux-swap"
USER_SETTINGS_FILE = USER_CONFIG_DIR / "settings.json"

# Scripts path
SCRIPTS_DIR = Path("/usr/share/biglinux-swap/scripts")

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
    SwapMode.AUTO: "Auto (Recommended)",
    SwapMode.ZSWAP_SWAPFILE: "Zswap + SwapFile",
    SwapMode.ZRAM_SWAPFILE: "Zram + SwapFile",
    SwapMode.ZRAM_ONLY: "Zram Only",
    SwapMode.DISABLED: "Disabled",
}

SWAP_MODE_DESCRIPTIONS: dict[SwapMode, str] = {
    SwapMode.AUTO: "Automatically detects the best mode for your system",
    SwapMode.ZSWAP_SWAPFILE: "Compressed RAM cache + dynamic swap files (best for desktop)",
    SwapMode.ZRAM_SWAPFILE: "Compressed RAM block device + swap files",
    SwapMode.ZRAM_ONLY: "Only Zram, no disk swap (for systems without disk swap support)",
    SwapMode.DISABLED: "Disable swap management (stops the service)",
}


class Compressor(Enum):
    """Available compression algorithms."""

    LZ4 = "lz4"
    ZSTD = "zstd"
    LZO = "lzo"


COMPRESSOR_NAMES: dict[Compressor, str] = {
    Compressor.LZ4: "LZ4 (Fastest)",
    Compressor.ZSTD: "Zstd (Balanced)",
    Compressor.LZO: "LZO (Legacy)",
}


class MglruTtl(Enum):
    """MGLRU min_ttl_ms presets."""

    AUTO = "auto"
    DISABLED = "0"
    MS_100 = "100"
    MS_300 = "300"
    MS_600 = "600"
    VERY_HIGH_RAM = "1000"  # 1s for 16GB+
    HIGH_RAM = "3000"  # 3s for 4-8GB
    MEDIUM_RAM = "5000"  # 5s for 2-4GB
    LOW_RAM = "10000"  # 10s for 1-2GB


MGLRU_TTL_NAMES: dict[MglruTtl, str] = {
    MglruTtl.AUTO: "Auto (Based on RAM)",
    MglruTtl.DISABLED: "Disabled",
    MglruTtl.MS_100: "100ms",
    MglruTtl.MS_300: "300ms",
    MglruTtl.MS_600: "600ms",
    MglruTtl.VERY_HIGH_RAM: "1s (16GB+)",
    MglruTtl.HIGH_RAM: "3s (4-8GB)",
    MglruTtl.MEDIUM_RAM: "5s (2-4GB)",
    MglruTtl.LOW_RAM: "10s (1-2GB)",
}


# =============================================================================
# Configuration Limits
# =============================================================================

# Zswap limits
ZSWAP_MAX_POOL_MIN = 10
ZSWAP_MAX_POOL_MAX = 80
ZSWAP_MAX_POOL_DEFAULT = 50
ZSWAP_MAX_POOL_STEP = 5

ZSWAP_ACCEPT_THRESHOLD_MIN = 50
ZSWAP_ACCEPT_THRESHOLD_MAX = 100
ZSWAP_ACCEPT_THRESHOLD_DEFAULT = 85

# Zram limits
ZRAM_SIZE_MIN = 10
ZRAM_SIZE_MAX = 100
ZRAM_SIZE_DEFAULT = 80

ZRAM_MEM_LIMIT_MIN = 30
ZRAM_MEM_LIMIT_MAX = 90
ZRAM_MEM_LIMIT_DEFAULT = 70

ZRAM_PRIORITY_MIN = 1
ZRAM_PRIORITY_MAX = 32767
ZRAM_PRIORITY_DEFAULT = 32767

ZRAM_WRITEBACK_THRESHOLD_MIN = 10
ZRAM_WRITEBACK_THRESHOLD_MAX = 90
ZRAM_WRITEBACK_THRESHOLD_DEFAULT = 50

# Zram writeback size options
ZRAM_WRITEBACK_SIZE_OPTIONS = ["512M", "1G", "2G", "4G"]
ZRAM_WRITEBACK_SIZE_DEFAULT = "1G"

ZRAM_WRITEBACK_MAX_SIZE_OPTIONS = ["2G", "4G", "8G", "16G", "32G"]
ZRAM_WRITEBACK_MAX_SIZE_DEFAULT = "8G"

# =============================================================================
# SwapFile limits
# =============================================================================

SWAPFILE_MIN_COUNT = 1
SWAPFILE_MAX_COUNT_MIN = 1
SWAPFILE_MAX_COUNT_MAX = 32
SWAPFILE_MAX_COUNT_DEFAULT = 32

SWAPFILE_SCALING_STEP_MIN = 1
SWAPFILE_SCALING_STEP_MAX = 10
SWAPFILE_SCALING_STEP_DEFAULT = 4

# New intelligent thresholds (PLANNING.md 12.4)
SWAPFILE_SHRINK_THRESHOLD_MIN = 10
SWAPFILE_SHRINK_THRESHOLD_MAX = 50
SWAPFILE_SHRINK_THRESHOLD_DEFAULT = 30  # Remove candidate if < 30% used

SWAPFILE_SAFE_HEADROOM_MIN = 20
SWAPFILE_SAFE_HEADROOM_MAX = 60
SWAPFILE_SAFE_HEADROOM_DEFAULT = 40  # Keep 40% free after migration

# Swap partition thresholds (PLANNING.md 12.7)
SWAPFILE_PARTITION_THRESHOLD_MIN = 70
SWAPFILE_PARTITION_THRESHOLD_MAX = 100
SWAPFILE_PARTITION_THRESHOLD_DEFAULT = 90  # Create files when partitions >= 90%

SWAPFILE_PARTITION_PRIORITY_DEFAULT = 100  # Base priority for partitions


# =============================================================================
# Chunk Size Options
# =============================================================================

CHUNK_SIZE_OPTIONS = ["256M", "512M", "1G", "2G", "4G", "8G"]
CHUNK_SIZE_DEFAULT = "512M"

MAX_CHUNK_SIZE_OPTIONS = ["8G", "16G", "32G", "64G", "128G"]
MAX_CHUNK_SIZE_DEFAULT = "64G"


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
    StorageType.NVME: "NVMe SSD",
    StorageType.SSD: "SATA SSD",
    StorageType.HDD: "Hard Drive",
    StorageType.EMMC: "eMMC",
    StorageType.SD: "SD Card",
    StorageType.UNKNOWN: "Unknown",
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
    DiscardPolicy.NONE: "Disabled",
    DiscardPolicy.ONCE: "At deactivation (recommended)",
    DiscardPolicy.PAGES: "Continuous (may impact performance)",
    DiscardPolicy.BOTH: "Both modes",
    DiscardPolicy.AUTO: "Auto-detect",
}


# =============================================================================
# Dataclasses for Configuration
# =============================================================================


@dataclass
class ZswapConfig:
    """Zswap configuration."""

    compressor: Compressor = Compressor.LZ4
    max_pool_percent: int = ZSWAP_MAX_POOL_DEFAULT
    zpool: str = "zsmalloc"
    shrinker_enabled: bool = True
    accept_threshold: int = ZSWAP_ACCEPT_THRESHOLD_DEFAULT


@dataclass
class ZramConfig:
    """Zram configuration."""

    size_percent: int = ZRAM_SIZE_DEFAULT
    alg: Compressor = Compressor.LZ4
    mem_limit_percent: int = ZRAM_MEM_LIMIT_DEFAULT
    priority: int = ZRAM_PRIORITY_DEFAULT
    writeback_enabled: bool = False
    writeback_size: str = "1G"
    writeback_max_size: str = "8G"
    writeback_threshold: int = 50


@dataclass
class SwapFileConfig:
    """SwapFile configuration (renamed from SwapFC per PLANNING.md 12.1)."""

    enabled: bool = True
    path: str = "/swapfile"
    chunk_size: str = CHUNK_SIZE_DEFAULT
    max_chunk_size: str = MAX_CHUNK_SIZE_DEFAULT
    max_count: int = SWAPFILE_MAX_COUNT_DEFAULT
    min_count: int = SWAPFILE_MIN_COUNT
    scaling_step: int = SWAPFILE_SCALING_STEP_DEFAULT

    # New intelligent thresholds (PLANNING.md 12.4)
    shrink_threshold: int = SWAPFILE_SHRINK_THRESHOLD_DEFAULT
    safe_headroom: int = SWAPFILE_SAFE_HEADROOM_DEFAULT

    # Swap partition support (PLANNING.md 12.7)
    use_partitions: bool = True
    partition_priority: int = SWAPFILE_PARTITION_PRIORITY_DEFAULT
    partition_threshold: int = SWAPFILE_PARTITION_THRESHOLD_DEFAULT
    min_count_with_partitions: int = 0

    # Performance optimizations (PLANNING.md 12.6)
    discard_policy: DiscardPolicy = DiscardPolicy.AUTO
    direct_io: bool = True
    priority: int = -1  # -1 = auto-calculate based on storage type


@dataclass
class SwapPartitionInfo:
    """Information about a swap partition (PLANNING.md 12.7)."""

    device: str = ""  # /dev/sda2, /dev/nvme0n1p3
    uuid: str = ""
    size_bytes: int = 0
    used_bytes: int = 0
    storage_type: StorageType = StorageType.UNKNOWN
    is_active: bool = False
    priority: int = 0

    @property
    def usage_percent(self) -> float:
        """Calculate usage percentage."""
        if self.size_bytes == 0:
            return 0.0
        return (self.used_bytes / self.size_bytes) * 100.0


@dataclass
class SwapFileInfo:
    """Information about an individual swap file (PLANNING.md 12.4)."""

    path: str = ""  # /swapfile/swap.0
    size_bytes: int = 0
    used_bytes: int = 0
    is_active: bool = False
    priority: int = 0

    @property
    def usage_percent(self) -> float:
        """Calculate usage percentage."""
        if self.size_bytes == 0:
            return 0.0
        return (self.used_bytes / self.size_bytes) * 100.0

    @property
    def is_removal_candidate(self) -> bool:
        """Check if this file is a candidate for removal."""
        return self.usage_percent < SWAPFILE_SHRINK_THRESHOLD_DEFAULT


@dataclass
class SwapConfig:
    """Complete swap configuration."""

    mode: SwapMode = SwapMode.AUTO
    zswap: ZswapConfig = field(default_factory=ZswapConfig)
    zram: ZramConfig = field(default_factory=ZramConfig)
    swapfile: SwapFileConfig = field(default_factory=SwapFileConfig)
    mglru_min_ttl: MglruTtl = MglruTtl.AUTO

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert enums to their values
        data["mode"] = self.mode.value
        data["mglru_min_ttl"] = self.mglru_min_ttl.value
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

        if "mglru_min_ttl" in data:
            config.mglru_min_ttl = MglruTtl(data["mglru_min_ttl"])

        if "zswap" in data:
            zs = data["zswap"]
            config.zswap = ZswapConfig(
                compressor=Compressor(zs.get("compressor", "lz4")),
                max_pool_percent=zs.get("max_pool_percent", ZSWAP_MAX_POOL_DEFAULT),
                zpool=zs.get("zpool", "zsmalloc"),
                shrinker_enabled=zs.get("shrinker_enabled", True),
                accept_threshold=zs.get(
                    "accept_threshold", ZSWAP_ACCEPT_THRESHOLD_DEFAULT
                ),
            )

        if "zram" in data:
            zr = data["zram"]
            config.zram = ZramConfig(
                size_percent=zr.get("size_percent", ZRAM_SIZE_DEFAULT),
                alg=Compressor(zr.get("alg", "lz4")),
                mem_limit_percent=zr.get("mem_limit_percent", ZRAM_MEM_LIMIT_DEFAULT),
                priority=zr.get("priority", ZRAM_PRIORITY_DEFAULT),
                writeback_enabled=zr.get("writeback_enabled", False),
                writeback_size=zr.get("writeback_size", "1G"),
                writeback_max_size=zr.get("writeback_max_size", "8G"),
                writeback_threshold=zr.get("writeback_threshold", 50),
            )

        sf = data.get("swapfile", {})
        if sf:
            discard_str = sf.get("discard_policy", "auto")
            try:
                discard_policy = DiscardPolicy(discard_str)
            except ValueError:
                discard_policy = DiscardPolicy.AUTO

            config.swapfile = SwapFileConfig(
                enabled=sf.get("enabled", True),
                path=sf.get("path", "/swapfile"),
                chunk_size=sf.get("chunk_size", CHUNK_SIZE_DEFAULT),
                max_chunk_size=sf.get("max_chunk_size", MAX_CHUNK_SIZE_DEFAULT),
                max_count=sf.get("max_count", SWAPFILE_MAX_COUNT_DEFAULT),
                min_count=sf.get("min_count", SWAPFILE_MIN_COUNT),
                scaling_step=sf.get("scaling_step", SWAPFILE_SCALING_STEP_DEFAULT),
                shrink_threshold=sf.get(
                    "shrink_threshold", SWAPFILE_SHRINK_THRESHOLD_DEFAULT
                ),
                safe_headroom=sf.get("safe_headroom", SWAPFILE_SAFE_HEADROOM_DEFAULT),
                use_partitions=sf.get("use_partitions", True),
                partition_priority=sf.get(
                    "partition_priority", SWAPFILE_PARTITION_PRIORITY_DEFAULT
                ),
                partition_threshold=sf.get(
                    "partition_threshold", SWAPFILE_PARTITION_THRESHOLD_DEFAULT
                ),
                min_count_with_partitions=sf.get("min_count_with_partitions", 0),
                discard_policy=discard_policy,
                direct_io=sf.get("direct_io", True),
                priority=sf.get("priority", -1),
            )

        return config


@dataclass
class WindowConfig:
    """Window state configuration."""

    width: int = WINDOW_WIDTH_DEFAULT
    height: int = WINDOW_HEIGHT_DEFAULT
    maximized: bool = False


@dataclass
class AppSettings:
    """Application settings (user preferences, not swap config)."""

    window: WindowConfig = field(default_factory=WindowConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        """Create settings from dictionary."""
        settings = cls()
        if "window" in data:
            w = data["window"]
            settings.window = WindowConfig(
                width=w.get("width", WINDOW_WIDTH_DEFAULT),
                height=w.get("height", WINDOW_HEIGHT_DEFAULT),
                maximized=w.get("maximized", False),
            )
        return settings


# =============================================================================
# Settings Management Functions
# =============================================================================


def load_app_settings() -> AppSettings:
    """Load application settings from user config file."""
    if not USER_SETTINGS_FILE.exists():
        logger.info("No settings file found, using defaults")
        return AppSettings()

    try:
        with open(USER_SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return AppSettings.from_dict(data)
    except json.JSONDecodeError as e:
        logger.error("Error parsing settings file: %s", e)
        return AppSettings()
    except OSError as e:
        logger.error("Error reading settings file: %s", e)
        return AppSettings()


def save_app_settings(settings: AppSettings) -> bool:
    """Save application settings to user config file."""
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = settings.to_dict()
        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.debug("Settings saved successfully")
        return True
    except OSError as e:
        logger.error("Error saving settings: %s", e)
        return False
