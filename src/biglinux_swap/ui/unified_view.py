#!/usr/bin/env python3
"""
Unified view for BigLinux Swap Manager.

Single-page interface with status at top and settings at bottom.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from biglinux_swap.config import (
    CHART_UPDATE_INTERVAL_MS,
    CHUNK_SIZE_OPTIONS,
    COMPRESSOR_NAMES,
    MAX_CHUNK_SIZE_OPTIONS,
    MGLRU_TTL_NAMES,
    SWAP_MODE_NAMES,
    SWAPFILE_MAX_COUNT_DEFAULT,
    SWAPFILE_MAX_COUNT_MAX,
    SWAPFILE_MAX_COUNT_MIN,
    SWAPFILE_SCALING_STEP_DEFAULT,
    SWAPFILE_SCALING_STEP_MAX,
    SWAPFILE_SCALING_STEP_MIN,
    ZRAM_MEM_LIMIT_DEFAULT,
    ZRAM_MEM_LIMIT_MAX,
    ZRAM_MEM_LIMIT_MIN,
    ZRAM_PRIORITY_DEFAULT,
    ZRAM_PRIORITY_MAX,
    ZRAM_PRIORITY_MIN,
    ZRAM_SIZE_DEFAULT,
    ZRAM_SIZE_MAX,
    ZRAM_SIZE_MIN,
    ZRAM_WRITEBACK_MAX_SIZE_OPTIONS,
    ZRAM_WRITEBACK_SIZE_OPTIONS,
    ZRAM_WRITEBACK_THRESHOLD_DEFAULT,
    ZRAM_WRITEBACK_THRESHOLD_MAX,
    ZRAM_WRITEBACK_THRESHOLD_MIN,
    ZSWAP_ACCEPT_THRESHOLD_DEFAULT,
    ZSWAP_ACCEPT_THRESHOLD_MAX,
    ZSWAP_ACCEPT_THRESHOLD_MIN,
    ZSWAP_MAX_POOL_DEFAULT,
    ZSWAP_MAX_POOL_MAX,
    ZSWAP_MAX_POOL_MIN,
    Compressor,
    MglruTtl,
    SwapConfig,
    SwapMode,
)
from biglinux_swap.services import MemoryStats, ServiceState, is_mglru_supported
from biglinux_swap.ui.components import (
    create_action_row_with_scale,
    create_action_row_with_switch,
    create_combo_row,
    create_preferences_group,
    create_spin_row,
    create_status_indicator,
    create_status_row,
    update_status_row,
)
from biglinux_swap.ui.memory_chart import MemoryChartWidget
from biglinux_swap.utils import TooltipHelper
from biglinux_swap.i18n import _


if TYPE_CHECKING:
    from biglinux_swap.services import (
        ConfigService,
        MeminfoService,
        SwapService,
        SwapStatus,
    )

logger = logging.getLogger(__name__)


class UnifiedView(Adw.Bin):
    """
    Unified view with status at top and settings at bottom.

    Layout:
    ┌─────────────────────────────────────┐
    │  Memory/Swap Chart + Status         │
    ├─────────────────────────────────────┤
    │  Swap Mode Selection                │
    ├─────────────────────────────────────┤
    │  Zswap/Zram/SwapFile Settings       │
    ├─────────────────────────────────────┤
    │  [Apply] Button                     │
    └─────────────────────────────────────┘
    """

    def __init__(
        self,
        config_service: ConfigService,
        swap_service: SwapService,
        meminfo_service: MeminfoService,
        on_toast: Callable[[str, int], None] | None = None,
        on_apply: Callable[[SwapConfig], None] | None = None,
        on_config_changed: Callable[[bool], None] | None = None,
    ) -> None:
        """
        Initialize the unified view.

        Args:
            config_service: Configuration service
            swap_service: Swap status service
            meminfo_service: Memory info service
            on_toast: Callback for toast notifications
            on_apply: Callback to apply configuration
            on_config_changed: Callback when config changes (True = has changes)
        """
        super().__init__()

        self._config_service = config_service
        self._swap_service = swap_service
        self._meminfo_service = meminfo_service
        self._on_toast = on_toast
        self._on_apply = on_apply
        self._on_config_changed = on_config_changed

        # Current config being edited and original for comparison
        self._config: SwapConfig = config_service.get()
        self._original_config: SwapConfig = self._deep_copy_config(config_service.get())
        self._loading = True

        # Timer for status updates
        self._status_timer: int = 0

        # Widget references
        self._chart: MemoryChartWidget | None = None
        self._status_row: Adw.ActionRow | None = None
        self._status_indicator: Gtk.Widget | None = None
        self._mode_row: Adw.ActionRow | None = None

        # Mode selection
        self._mode_combo: Adw.ComboRow | None = None

        # Zswap widgets
        self._zswap_compressor_combo: Adw.ComboRow | None = None
        self._zswap_pool_row: Adw.ActionRow | None = None
        self._zswap_pool_scale: Gtk.Scale | None = None
        self._zswap_shrinker_row: Adw.ActionRow | None = None
        self._zswap_shrinker_switch: Gtk.Switch | None = None
        self._zswap_accept_row: Adw.ActionRow | None = None
        self._zswap_accept_scale: Gtk.Scale | None = None
        self._zswap_group: Adw.PreferencesGroup | None = None

        # Zram widgets
        self._zram_size_row: Adw.ActionRow | None = None
        self._zram_size_scale: Gtk.Scale | None = None
        self._zram_alg_combo: Adw.ComboRow | None = None
        self._zram_mem_limit_row: Adw.ActionRow | None = None
        self._zram_mem_limit_scale: Gtk.Scale | None = None
        self._zram_priority_spin: Adw.SpinRow | None = None
        self._zram_writeback_row: Adw.ActionRow | None = None
        self._zram_writeback_switch: Gtk.Switch | None = None
        self._zram_writeback_size_combo: Adw.ComboRow | None = None
        self._zram_writeback_max_combo: Adw.ComboRow | None = None
        self._zram_writeback_threshold_row: Adw.ActionRow | None = None
        self._zram_writeback_threshold_scale: Gtk.Scale | None = None
        self._zram_group: Adw.PreferencesGroup | None = None

        # SwapFile widgets
        self._swapfile_enabled_row: Adw.ActionRow | None = None
        self._swapfile_enabled_switch: Gtk.Switch | None = None
        self._swapfile_chunk_combo: Adw.ComboRow | None = None
        self._swapfile_max_chunk_combo: Adw.ComboRow | None = None
        self._swapfile_max_count_spin: Adw.SpinRow | None = None
        self._swapfile_scaling_spin: Adw.SpinRow | None = None
        self._swapfile_group: Adw.PreferencesGroup | None = None

        # MGLRU
        self._mglru_combo: Adw.ComboRow | None = None

        # Status display rows for live statistics
        self._stats_zswap_pool_row: Adw.ActionRow | None = None
        self._stats_zswap_stored_row: Adw.ActionRow | None = None
        self._stats_zram_size_row: Adw.ActionRow | None = None
        self._stats_swapfile_files_row: Adw.ActionRow | None = None

        # Live statistics expander and rows
        self._stats_expander: Adw.ExpanderRow | None = None

        # Tooltip helper
        self._tooltip_helper = TooltipHelper()

        self._setup_ui()
        self._load_state()
        self._start_monitoring()
        self._loading = False

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        # Main scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # Clamp for content width
        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_margin_top(8)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)

        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # === STATUS SECTION (TOP) ===
        self._setup_status_section(main_box)

        # === SETTINGS SECTION (BOTTOM) ===
        self._setup_settings_section(main_box)

        # === TOOLTIPS ===
        self._setup_tooltips()

        clamp.set_child(main_box)
        scrolled.set_child(clamp)
        self.set_child(scrolled)

    def _setup_status_section(self, parent: Gtk.Box) -> None:
        """Set up the status/monitoring section at top."""
        # Memory Chart - no title as chart has its own legend
        chart_group = create_preferences_group("")

        # Chart widget
        self._chart = MemoryChartWidget()
        self._chart.set_size_request(-1, 150)
        chart_group.add(self._chart)

        parent.append(chart_group)

        # Service Status (compact)
        status_group = create_preferences_group("Service Status")

        # Service state row
        self._status_row = create_status_row(
            "systemd-swap",
            "Unknown",
        )
        self._status_indicator = create_status_indicator(False, "")
        self._status_row.add_suffix(self._status_indicator)
        status_group.add(self._status_row)

        # Current mode
        self._mode_row = create_status_row(
            "Current Mode",
            self._config.mode.value,
        )
        status_group.add(self._mode_row)

        # Live stats (collapsed by default - dynamically shows only active systems)
        self._stats_expander = Adw.ExpanderRow()
        self._stats_expander.set_title("Live Statistics")
        self._stats_expander.set_subtitle("Active system usage info")
        self._stats_expander.set_expanded(False)

        # Zswap stats (shown only when zswap is active)
        self._stats_zswap_pool_row = create_status_row("Zswap Pool", "-")
        self._stats_expander.add_row(self._stats_zswap_pool_row)

        self._stats_zswap_stored_row = create_status_row("Zswap Stored", "-")
        self._stats_expander.add_row(self._stats_zswap_stored_row)

        # Zram stats (shown only when zram is active)
        self._stats_zram_size_row = create_status_row("Zram Size", "-")
        self._stats_expander.add_row(self._stats_zram_size_row)

        # Swap File stats (shown only when swapfile is active)
        self._stats_swapfile_files_row = create_status_row("Swap Files", "-")
        self._stats_expander.add_row(self._stats_swapfile_files_row)

        status_group.add(self._stats_expander)
        parent.append(status_group)

    def _setup_settings_section(self, parent: Gtk.Box) -> None:
        """Set up the configuration section at bottom."""
        # === SWAP MODE ===
        mode_group = create_preferences_group(
            "Swap Mode",
            "Choose how swap is managed",
        )

        mode_names = [SWAP_MODE_NAMES[mode] for mode in SwapMode]
        self._mode_combo = create_combo_row(
            "Mode",
            subtitle="Select swap management strategy",
            options=mode_names,
            on_selected=self._on_mode_changed,
        )
        mode_group.add(self._mode_combo)
        parent.append(mode_group)

        # === ZSWAP SETTINGS ===
        self._zswap_group = create_preferences_group(
            "Zswap",
            "Compressed RAM cache for swap",
        )

        compressor_names = [COMPRESSOR_NAMES[c] for c in Compressor]
        self._zswap_compressor_combo = create_combo_row(
            "Compressor",
            subtitle="Compression algorithm",
            options=compressor_names,
            on_selected=self._on_zswap_compressor_changed,
        )
        self._zswap_group.add(self._zswap_compressor_combo)

        self._zswap_pool_row, self._zswap_pool_scale = create_action_row_with_scale(
            "Max Pool Size",
            subtitle="Maximum % of RAM for cache",
            min_value=ZSWAP_MAX_POOL_MIN,
            max_value=ZSWAP_MAX_POOL_MAX,
            value=ZSWAP_MAX_POOL_DEFAULT,
            step=5,
            on_changed=self._on_zswap_pool_changed,
        )
        self._zswap_group.add(self._zswap_pool_row)

        self._zswap_shrinker_row, self._zswap_shrinker_switch = (
            create_action_row_with_switch(
                "Shrinker",
                subtitle="Move cold pages to disk proactively",
                active=True,
                on_toggled=self._on_zswap_shrinker_changed,
            )
        )
        self._zswap_group.add(self._zswap_shrinker_row)

        self._zswap_accept_row, self._zswap_accept_scale = create_action_row_with_scale(
            "Accept Threshold",
            subtitle="Resume accepting pages when pool drops to %",
            min_value=ZSWAP_ACCEPT_THRESHOLD_MIN,
            max_value=ZSWAP_ACCEPT_THRESHOLD_MAX,
            value=ZSWAP_ACCEPT_THRESHOLD_DEFAULT,
            step=5,
            on_changed=self._on_zswap_accept_changed,
        )
        self._zswap_group.add(self._zswap_accept_row)

        parent.append(self._zswap_group)

        # === ZRAM SETTINGS ===
        self._zram_group = create_preferences_group(
            "Zram",
            "Compressed block device in RAM",
        )

        self._zram_size_row, self._zram_size_scale = create_action_row_with_scale(
            "Virtual Size",
            subtitle="Uncompressed size (% of RAM)",
            min_value=ZRAM_SIZE_MIN,
            max_value=ZRAM_SIZE_MAX,
            value=ZRAM_SIZE_DEFAULT,
            step=5,
            on_changed=self._on_zram_size_changed,
        )
        self._zram_group.add(self._zram_size_row)

        alg_names = [COMPRESSOR_NAMES[c] for c in Compressor]
        self._zram_alg_combo = create_combo_row(
            "Algorithm",
            subtitle="Compression algorithm",
            options=alg_names,
            on_selected=self._on_zram_alg_changed,
        )
        self._zram_group.add(self._zram_alg_combo)

        self._zram_mem_limit_row, self._zram_mem_limit_scale = (
            create_action_row_with_scale(
                "Memory Limit",
                subtitle="Max physical RAM zram can use (OOM protection)",
                min_value=ZRAM_MEM_LIMIT_MIN,
                max_value=ZRAM_MEM_LIMIT_MAX,
                value=ZRAM_MEM_LIMIT_DEFAULT,
                step=5,
                on_changed=self._on_zram_mem_limit_changed,
            )
        )
        self._zram_group.add(self._zram_mem_limit_row)

        self._zram_priority_spin = create_spin_row(
            "Priority",
            subtitle="Swap priority (higher = used first)",
            min_value=ZRAM_PRIORITY_MIN,
            max_value=ZRAM_PRIORITY_MAX,
            value=ZRAM_PRIORITY_DEFAULT,
            on_changed=self._on_zram_priority_changed,
        )
        self._zram_group.add(self._zram_priority_spin)

        # Writeback section (advanced)
        writeback_expander = Adw.ExpanderRow()
        writeback_expander.set_title("Writeback")
        writeback_expander.set_subtitle("Move idle pages from zram to disk")
        writeback_expander.set_expanded(False)

        self._zram_writeback_row, self._zram_writeback_switch = (
            create_action_row_with_switch(
                "Enabled",
                subtitle="Enable writeback to disk",
                active=False,
                on_toggled=self._on_zram_writeback_changed,
            )
        )
        writeback_expander.add_row(self._zram_writeback_row)

        self._zram_writeback_size_combo = create_combo_row(
            "Size Limit",
            subtitle="Max writeback per cycle",
            options=ZRAM_WRITEBACK_SIZE_OPTIONS,
            on_selected=self._on_zram_writeback_size_changed,
        )
        writeback_expander.add_row(self._zram_writeback_size_combo)

        self._zram_writeback_max_combo = create_combo_row(
            "Max Total Size",
            subtitle="Total writeback limit",
            options=ZRAM_WRITEBACK_MAX_SIZE_OPTIONS,
            on_selected=self._on_zram_writeback_max_changed,
        )
        writeback_expander.add_row(self._zram_writeback_max_combo)

        self._zram_writeback_threshold_row, self._zram_writeback_threshold_scale = (
            create_action_row_with_scale(
                "Threshold",
                subtitle="Trigger writeback when zram usage exceeds %",
                min_value=ZRAM_WRITEBACK_THRESHOLD_MIN,
                max_value=ZRAM_WRITEBACK_THRESHOLD_MAX,
                value=ZRAM_WRITEBACK_THRESHOLD_DEFAULT,
                step=5,
                on_changed=self._on_zram_writeback_threshold_changed,
            )
        )
        writeback_expander.add_row(self._zram_writeback_threshold_row)

        self._zram_group.add(writeback_expander)

        parent.append(self._zram_group)

        # === SWAP FILE SETTINGS ===
        self._swapfile_group = create_preferences_group(
            "Swap File",
            "Dynamic swap files on disk",
        )

        self._swapfile_enabled_row, self._swapfile_enabled_switch = (
            create_action_row_with_switch(
                "Enabled",
                subtitle="Create swap files dynamically",
                active=True,
                on_toggled=self._on_swapfile_enabled_changed,
            )
        )
        self._swapfile_group.add(self._swapfile_enabled_row)

        self._swapfile_chunk_combo = create_combo_row(
            "Chunk Size",
            subtitle="Base size for each file",
            options=CHUNK_SIZE_OPTIONS,
            on_selected=self._on_swapfile_chunk_changed,
        )
        self._swapfile_group.add(self._swapfile_chunk_combo)

        self._swapfile_max_chunk_combo = create_combo_row(
            "Max Chunk Size",
            subtitle="Maximum single file size",
            options=MAX_CHUNK_SIZE_OPTIONS,
            on_selected=self._on_swapfile_max_chunk_changed,
        )
        self._swapfile_group.add(self._swapfile_max_chunk_combo)

        self._swapfile_max_count_spin = create_spin_row(
            "Max Files",
            subtitle="Maximum number of swap files",
            min_value=SWAPFILE_MAX_COUNT_MIN,
            max_value=SWAPFILE_MAX_COUNT_MAX,
            value=SWAPFILE_MAX_COUNT_DEFAULT,
            on_changed=self._on_swapfile_max_count_changed,
        )
        self._swapfile_group.add(self._swapfile_max_count_spin)

        self._swapfile_scaling_spin = create_spin_row(
            "Scaling Step",
            subtitle="Double chunk size every N files",
            min_value=SWAPFILE_SCALING_STEP_MIN,
            max_value=SWAPFILE_SCALING_STEP_MAX,
            value=SWAPFILE_SCALING_STEP_DEFAULT,
            on_changed=self._on_swapfile_scaling_changed,
        )
        self._swapfile_group.add(self._swapfile_scaling_spin)

        parent.append(self._swapfile_group)

        # === MGLRU (only if kernel supports it) ===
        self._mglru_group: Adw.PreferencesGroup | None = None
        self._mglru_combo: Adw.ComboRow | None = None

        if is_mglru_supported():
            self._mglru_group = create_preferences_group(
                "MGLRU Anti-Thrashing",
                "Working set protection",
            )

            mglru_names = [MGLRU_TTL_NAMES[m] for m in MglruTtl]
            self._mglru_combo = create_combo_row(
                "Min TTL",
                subtitle="Protect working set from eviction",
                options=mglru_names,
                on_selected=self._on_mglru_changed,
            )
            self._mglru_group.add(self._mglru_combo)

            parent.append(self._mglru_group)

        # Initial visibility update based on mode
        self._update_settings_visibility()

    def _setup_tooltips(self) -> None:
        """Add informative tooltips to all configuration widgets."""
        # Mode selection tooltip
        if self._mode_combo:
            self._tooltip_helper.add_tooltip(self._mode_combo, "mode_auto")

        # Zswap tooltips - apply to entire rows
        if self._zswap_compressor_combo:
            self._tooltip_helper.add_tooltip(
                self._zswap_compressor_combo, "zswap_compressor"
            )
        if self._zswap_pool_row:
            self._tooltip_helper.add_tooltip(self._zswap_pool_row, "zswap_pool")
        if self._zswap_shrinker_row:
            self._tooltip_helper.add_tooltip(self._zswap_shrinker_row, "zswap_shrinker")
        if self._zswap_accept_row:
            self._tooltip_helper.add_tooltip(
                self._zswap_accept_row, "zswap_accept_threshold"
            )

        # Zram tooltips - apply to entire rows
        if self._zram_size_row:
            self._tooltip_helper.add_tooltip(self._zram_size_row, "zram_size")
        if self._zram_alg_combo:
            self._tooltip_helper.add_tooltip(self._zram_alg_combo, "zram_algorithm")
        if self._zram_mem_limit_row:
            self._tooltip_helper.add_tooltip(self._zram_mem_limit_row, "zram_mem_limit")
        if self._zram_priority_spin:
            self._tooltip_helper.add_tooltip(self._zram_priority_spin, "zram_priority")
        if self._zram_writeback_row:
            self._tooltip_helper.add_tooltip(self._zram_writeback_row, "zram_writeback")

        # Swap File tooltips - apply to entire rows
        if self._swapfile_enabled_row:
            self._tooltip_helper.add_tooltip(
                self._swapfile_enabled_row, "swapfile_toggle"
            )
        if self._swapfile_chunk_combo:
            self._tooltip_helper.add_tooltip(
                self._swapfile_chunk_combo, "swapfile_chunk"
            )
        if self._swapfile_max_count_spin:
            self._tooltip_helper.add_tooltip(
                self._swapfile_max_count_spin, "swapfile_max_count"
            )
        if self._swapfile_max_chunk_combo:
            self._tooltip_helper.add_tooltip(
                self._swapfile_max_chunk_combo, "swapfile_max_chunk"
            )
        if self._swapfile_scaling_spin:
            self._tooltip_helper.add_tooltip(
                self._swapfile_scaling_spin, "swapfile_scaling"
            )

        # MGLRU tooltip
        if self._mglru_combo:
            self._tooltip_helper.add_tooltip(self._mglru_combo, "mglru_ttl")

        # Status tooltips
        if self._status_row:
            self._tooltip_helper.add_tooltip(self._status_row, "status_service")
        if self._mode_row:
            self._tooltip_helper.add_tooltip(self._mode_row, "status_mode")

    def _load_state(self) -> None:
        """Load current configuration into UI widgets."""
        self._loading = True
        config = self._config

        # Mode selection
        mode_index = list(SwapMode).index(config.mode)
        if self._mode_combo:
            self._mode_combo.set_selected(mode_index)

        # Zswap
        compressor_index = list(Compressor).index(config.zswap.compressor)
        if self._zswap_compressor_combo:
            self._zswap_compressor_combo.set_selected(compressor_index)
        if self._zswap_pool_scale:
            self._zswap_pool_scale.set_value(config.zswap.max_pool_percent)
        if self._zswap_shrinker_switch:
            self._zswap_shrinker_switch.set_active(config.zswap.shrinker_enabled)
        if self._zswap_accept_scale:
            self._zswap_accept_scale.set_value(config.zswap.accept_threshold)

        # Zram
        if self._zram_size_scale:
            self._zram_size_scale.set_value(config.zram.size_percent)
        alg_index = list(Compressor).index(config.zram.alg)
        if self._zram_alg_combo:
            self._zram_alg_combo.set_selected(alg_index)
        if self._zram_mem_limit_scale:
            self._zram_mem_limit_scale.set_value(config.zram.mem_limit_percent)
        if self._zram_priority_spin:
            self._zram_priority_spin.set_value(config.zram.priority)
        if self._zram_writeback_switch:
            self._zram_writeback_switch.set_active(config.zram.writeback_enabled)
        if self._zram_writeback_size_combo:
            wb_size_index = (
                ZRAM_WRITEBACK_SIZE_OPTIONS.index(config.zram.writeback_size)
                if config.zram.writeback_size in ZRAM_WRITEBACK_SIZE_OPTIONS
                else 1  # Default to 1G
            )
            self._zram_writeback_size_combo.set_selected(wb_size_index)
        if self._zram_writeback_max_combo:
            wb_max_index = (
                ZRAM_WRITEBACK_MAX_SIZE_OPTIONS.index(config.zram.writeback_max_size)
                if config.zram.writeback_max_size in ZRAM_WRITEBACK_MAX_SIZE_OPTIONS
                else 2  # Default to 8G
            )
            self._zram_writeback_max_combo.set_selected(wb_max_index)
        if self._zram_writeback_threshold_scale:
            self._zram_writeback_threshold_scale.set_value(
                config.zram.writeback_threshold
            )

        # SwapFile
        if self._swapfile_enabled_switch:
            self._swapfile_enabled_switch.set_active(config.swapfile.enabled)
        if self._swapfile_chunk_combo:
            chunk_index = (
                CHUNK_SIZE_OPTIONS.index(config.swapfile.chunk_size)
                if config.swapfile.chunk_size in CHUNK_SIZE_OPTIONS
                else 1
            )
            self._swapfile_chunk_combo.set_selected(chunk_index)
        if self._swapfile_max_chunk_combo:
            max_chunk_index = (
                MAX_CHUNK_SIZE_OPTIONS.index(config.swapfile.max_chunk_size)
                if config.swapfile.max_chunk_size in MAX_CHUNK_SIZE_OPTIONS
                else 3  # Default to 64G
            )
            self._swapfile_max_chunk_combo.set_selected(max_chunk_index)
        if self._swapfile_max_count_spin:
            self._swapfile_max_count_spin.set_value(config.swapfile.max_count)
        if self._swapfile_scaling_spin:
            self._swapfile_scaling_spin.set_value(config.swapfile.scaling_step)

        # MGLRU
        mglru_index = list(MglruTtl).index(config.mglru_min_ttl)
        if self._mglru_combo:
            self._mglru_combo.set_selected(mglru_index)

        self._loading = False

    def _deep_copy_config(self, config: SwapConfig) -> SwapConfig:
        """Create a deep copy of the configuration."""
        import copy

        return copy.deepcopy(config)

    def _check_config_changed(self) -> None:
        """Check if config has changed and notify callback."""
        if self._loading or not self._on_config_changed:
            return

        # Compare current config with original
        has_changes = self._configs_differ(self._config, self._original_config)
        self._on_config_changed(has_changes)

    def _configs_differ(self, a: SwapConfig, b: SwapConfig) -> bool:
        """Check if two configs are different."""
        # Mode
        if a.mode != b.mode:
            return True
        # Zswap
        if (
            a.zswap.compressor != b.zswap.compressor
            or a.zswap.max_pool_percent != b.zswap.max_pool_percent
            or a.zswap.shrinker_enabled != b.zswap.shrinker_enabled
            or a.zswap.accept_threshold != b.zswap.accept_threshold
        ):
            return True
        # Zram
        if (
            a.zram.size_percent != b.zram.size_percent
            or a.zram.alg != b.zram.alg
            or a.zram.mem_limit_percent != b.zram.mem_limit_percent
            or a.zram.priority != b.zram.priority
            or a.zram.writeback_enabled != b.zram.writeback_enabled
            or a.zram.writeback_size != b.zram.writeback_size
            or a.zram.writeback_max_size != b.zram.writeback_max_size
            or a.zram.writeback_threshold != b.zram.writeback_threshold
        ):
            return True
        # SwapFile
        if (
            a.swapfile.enabled != b.swapfile.enabled
            or a.swapfile.chunk_size != b.swapfile.chunk_size
            or a.swapfile.max_chunk_size != b.swapfile.max_chunk_size
            or a.swapfile.max_count != b.swapfile.max_count
            or a.swapfile.scaling_step != b.swapfile.scaling_step
        ):
            return True
        # MGLRU
        return a.mglru_min_ttl != b.mglru_min_ttl

    def _start_monitoring(self) -> None:
        """Start periodic status updates."""
        self._meminfo_service.start_monitoring(
            self._on_memory_update,
            CHART_UPDATE_INTERVAL_MS,
        )
        self._status_timer = GLib.timeout_add(3000, self._update_swap_status)
        self._update_swap_status()

    def stop_monitoring(self) -> None:
        """Stop periodic updates."""
        self._meminfo_service.stop_monitoring()
        if self._status_timer:
            GLib.source_remove(self._status_timer)
            self._status_timer = 0

    def _on_memory_update(self, stats: MemoryStats) -> None:
        """Handle memory stats update."""
        if self._chart:
            mem_text = f"{stats.mem_used_formatted} / {stats.mem_total_formatted}"

            # When zswap is active, show disk swap vs RAM swap
            # Always show Swap RAM and Swap Disk separately when swap exists
            if stats.swap_total > 0:
                # Swap in RAM (zswap stored or zram) - orange line
                swap_ram_text = f"{stats.swap_ram_formatted}"
                swap_ram_percent = stats.swap_ram_percent

                # Swap on disk (actual disk usage) - blue line
                swap_disk_text = f"{stats.swap_disk_formatted}"
                swap_disk_percent = stats.swap_disk_percent

                self._chart.add_data_point(
                    stats.mem_used_percent,
                    swap_disk_percent,  # Blue line: disk swap
                    mem_text,
                    swap_disk_text,
                    swap_ram_percent,  # Orange line: RAM swap (zswap/zram)
                    swap_ram_text,
                )
            else:
                # No swap configured
                self._chart.add_data_point(
                    stats.mem_used_percent,
                    0.0,
                    mem_text,
                    "N/A",
                    0.0,
                    "",
                )

    def _update_swap_status(self) -> bool:
        """Update swap service status display."""
        status = self._swap_service.get_status()

        # Update service state
        state_text = status.service_state.value.capitalize()
        is_active = status.service_state == ServiceState.ACTIVE
        update_status_row(self._status_row, state_text)

        if self._status_indicator and self._status_row:
            self._status_row.remove(self._status_indicator)
            self._status_indicator = create_status_indicator(is_active, "")
            self._status_row.add_suffix(self._status_indicator)

        # Update mode
        config = self._config_service.get()
        if self._mode_row:
            update_status_row(self._mode_row, config.mode.value)

        # Update live statistics visibility (show only active systems)
        self._update_live_statistics_visibility(status)

        # Update statistics values - always show when enabled
        if status.zswap.enabled:
            pool_text = self._format_bytes(status.zswap.pool_size_bytes) if status.zswap.pool_size_bytes > 0 else "0 B"
            stored_text = self._format_bytes(status.zswap.stored_data_bytes) if status.zswap.stored_data_bytes > 0 else "0 B"
            update_status_row(self._stats_zswap_pool_row, pool_text)
            update_status_row(self._stats_zswap_stored_row, stored_text)

        if status.zram.enabled:
            zram_text = self._format_bytes(status.zram.total_size_bytes) if status.zram.total_size_bytes > 0 else "0 B"
            update_status_row(self._stats_zram_size_row, zram_text)

        if status.swapfile.enabled or status.swapfile.file_count > 0:
            # Show detailed swap file info
            if status.swapfile.files:
                total_size = sum(f.size_bytes for f in status.swapfile.files)
                total_used = sum(f.used_bytes for f in status.swapfile.files)
                files_text = f"{len(status.swapfile.files)} files ({self._format_bytes(total_used)} / {self._format_bytes(total_size)})"
            else:
                files_text = f"{status.swapfile.file_count} / {status.swapfile.max_files}"
            update_status_row(self._stats_swapfile_files_row, files_text)

        # Update settings visibility for Auto mode
        if config.mode == SwapMode.AUTO:
            self._update_settings_visibility()

        return True

    def _format_bytes(self, size_bytes: int) -> str:
        """Format bytes to human-readable string."""
        units = ["B", "KiB", "MiB", "GiB"]
        size = float(size_bytes)
        for unit in units[:-1]:
            if abs(size) < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} {units[-1]}"

    def _update_settings_visibility(self) -> None:
        """Update settings sections visibility based on selected mode."""
        mode = self._config.mode

        # Determine what should be visible for each mode
        show_zswap = mode in (SwapMode.AUTO, SwapMode.ZSWAP_SWAPFILE)
        show_zram = mode in (
            SwapMode.AUTO,
            SwapMode.ZRAM_SWAPFILE,
            SwapMode.ZRAM_ONLY,
        )
        show_swapfile = mode in (
            SwapMode.AUTO,
            SwapMode.ZSWAP_SWAPFILE,
            SwapMode.ZRAM_SWAPFILE,
        )

        # For AUTO mode, check what's actually active in the system
        if mode == SwapMode.AUTO:
            status = self._swap_service.get_status()
            show_zswap = status.zswap.enabled
            show_zram = status.zram.enabled
            show_swapfile = status.swapfile.enabled

        # Update visibility
        if self._zswap_group:
            self._zswap_group.set_visible(show_zswap)
        if self._zram_group:
            self._zram_group.set_visible(show_zram)
        if self._swapfile_group:
            self._swapfile_group.set_visible(show_swapfile)

    def _update_live_statistics_visibility(self, status: SwapStatus) -> None:
        """Update live statistics rows visibility based on active systems."""
        # Hide all rows initially, then show only active ones
        has_any_active = False

        # Zswap rows
        zswap_visible = status.zswap.enabled
        if self._stats_zswap_pool_row:
            self._stats_zswap_pool_row.set_visible(zswap_visible)
        if self._stats_zswap_stored_row:
            self._stats_zswap_stored_row.set_visible(zswap_visible)
        if zswap_visible:
            has_any_active = True

        # Zram rows
        zram_visible = status.zram.enabled
        if self._stats_zram_size_row:
            self._stats_zram_size_row.set_visible(zram_visible)
        if zram_visible:
            has_any_active = True

        # Swap File rows
        swapfile_visible = status.swapfile.enabled
        if self._stats_swapfile_files_row:
            self._stats_swapfile_files_row.set_visible(swapfile_visible)
        if swapfile_visible:
            has_any_active = True

        # Update expander subtitle based on what's active
        if self._stats_expander:
            if not has_any_active:
                self._stats_expander.set_subtitle("No active swap systems")
            else:
                active_systems = []
                if status.zswap.enabled:
                    active_systems.append("Zswap")
                if status.zram.enabled:
                    active_systems.append("Zram")
                if status.swapfile.enabled:
                    active_systems.append("Swap File")
                self._stats_expander.set_subtitle(", ".join(active_systems))

    # === Setting callbacks ===

    def _on_mode_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.mode = list(SwapMode)[index]
        self._update_settings_visibility()
        self._check_config_changed()

    def _on_zswap_compressor_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.zswap.compressor = list(Compressor)[index]
        self._check_config_changed()

    def _on_zswap_pool_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.zswap.max_pool_percent = int(value)
        self._check_config_changed()

    def _on_zswap_shrinker_changed(self, active: bool) -> None:
        if self._loading:
            return
        self._config.zswap.shrinker_enabled = active
        self._check_config_changed()

    def _on_zswap_accept_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.zswap.accept_threshold = int(value)
        self._check_config_changed()

    def _on_zram_size_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.zram.size_percent = int(value)
        self._check_config_changed()

    def _on_zram_alg_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.zram.alg = list(Compressor)[index]
        self._check_config_changed()

    def _on_zram_mem_limit_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.zram.mem_limit_percent = int(value)
        self._check_config_changed()

    def _on_zram_priority_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.zram.priority = int(value)
        self._check_config_changed()

    def _on_zram_writeback_changed(self, active: bool) -> None:
        if self._loading:
            return
        self._config.zram.writeback_enabled = active
        self._check_config_changed()

    def _on_zram_writeback_size_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.zram.writeback_size = ZRAM_WRITEBACK_SIZE_OPTIONS[index]
        self._check_config_changed()

    def _on_zram_writeback_max_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.zram.writeback_max_size = ZRAM_WRITEBACK_MAX_SIZE_OPTIONS[index]
        self._check_config_changed()

    def _on_zram_writeback_threshold_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.zram.writeback_threshold = int(value)
        self._check_config_changed()

    def _on_swapfile_enabled_changed(self, active: bool) -> None:
        if self._loading:
            return
        self._config.swapfile.enabled = active
        self._check_config_changed()

    def _on_swapfile_chunk_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.swapfile.chunk_size = CHUNK_SIZE_OPTIONS[index]
        self._check_config_changed()

    def _on_swapfile_max_chunk_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.swapfile.max_chunk_size = MAX_CHUNK_SIZE_OPTIONS[index]
        self._check_config_changed()

    def _on_swapfile_max_count_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.swapfile.max_count = int(value)
        self._check_config_changed()

    def _on_swapfile_scaling_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.swapfile.scaling_step = int(value)
        self._check_config_changed()

    def _on_mglru_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.mglru_min_ttl = list(MglruTtl)[index]
        self._check_config_changed()

    def restore_defaults(self) -> None:
        """Restore default configuration (public method for window)."""
        self._config = SwapConfig()
        self._load_state()
        self._update_settings_visibility()
        self._check_config_changed()

    def mark_saved(self) -> None:
        """Mark current config as saved (resets change tracking)."""
        self._original_config = self._deep_copy_config(self._config)
        self._check_config_changed()

    def get_config(self) -> SwapConfig:
        """Get current configuration."""
        return self._config
