#!/usr/bin/env python3
"""
Unified view for BigLinux Swap Manager.

Single-page interface with status at top, mode selection, and
advanced settings collapsed by default for simplicity.
"""

from __future__ import annotations

import copy
import glob
import logging
import threading
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
    DISCARD_POLICY_NAMES,
    SWAP_MODE_DESCRIPTIONS,
    SWAP_MODE_NAMES,
    SWAPFILE_FREE_RAM_PERC_DEFAULT,
    SWAPFILE_FREE_RAM_PERC_MAX,
    SWAPFILE_FREE_RAM_PERC_MIN,
    SWAPFILE_FREE_SWAP_PERC_DEFAULT,
    SWAPFILE_FREE_SWAP_PERC_MAX,
    SWAPFILE_FREE_SWAP_PERC_MIN,
    SWAPFILE_MAX_COUNT_DEFAULT,
    SWAPFILE_MAX_COUNT_MAX,
    SWAPFILE_MAX_COUNT_MIN,
    SWAPFILE_MIN_COUNT_UI_MAX,
    SWAPFILE_MIN_COUNT_UI_MIN,
    SWAPFILE_REMOVE_FREE_SWAP_PERC_DEFAULT,
    SWAPFILE_REMOVE_FREE_SWAP_PERC_MAX,
    SWAPFILE_REMOVE_FREE_SWAP_PERC_MIN,
    ZRAM_SIZE_DEFAULT,
    ZRAM_SIZE_MAX,
    ZRAM_SIZE_MIN,
    ZSWAP_ACCEPT_THRESHOLD_DEFAULT,
    ZSWAP_ACCEPT_THRESHOLD_MAX,
    ZSWAP_ACCEPT_THRESHOLD_MIN,
    ZSWAP_MAX_POOL_DEFAULT,
    ZSWAP_MAX_POOL_MAX,
    ZSWAP_MAX_POOL_MIN,
    Compressor,
    DiscardPolicy,
    SwapConfig,
    SwapMode,
)
from biglinux_swap.i18n import _
from biglinux_swap.ui.components import (
    create_action_row_with_scale,
    create_action_row_with_switch,
    create_combo_row,
    create_preferences_group,
    create_status_indicator,
    create_status_row,
    update_status_row,
)
from biglinux_swap.ui.memory_chart import MemoryChartWidget
from biglinux_swap.utils import TooltipHelper

from biglinux_swap.services import MemoryStats, ServiceState

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
    Unified view: status + mode selector + advanced settings.

    Layout:
    ┌─────────────────────────────────────┐
    │  Memory/Swap Chart                  │
    ├─────────────────────────────────────┤
    │  Service Status + Live Stats        │
    ├─────────────────────────────────────┤
    │  Swap Mode (dropdown + description) │
    ├─────────────────────────────────────┤
    │  ▶ Advanced Settings (collapsed)    │
    └─────────────────────────────────────┘
    """

    def __init__(
        self,
        config_service: ConfigService,
        swap_service: SwapService,
        meminfo_service: MeminfoService,
        on_toast: Callable[[str, int], None] | None = None,
        on_config_changed: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__()

        self._config_service = config_service
        self._swap_service = swap_service
        self._meminfo_service = meminfo_service
        self._on_toast = on_toast
        self._on_config_changed = on_config_changed

        self._config: SwapConfig = config_service.get()
        self._original_config: SwapConfig = self._deep_copy_config(config_service.get())
        self._loading = True

        self._status_timer: int = 0

        self._latest_mem_stats: MemoryStats | None = None
        self._latest_swap_status: SwapStatus | None = None

        # Widget references
        self._chart: MemoryChartWidget | None = None
        self._status_row: Adw.ActionRow | None = None
        self._status_indicator: Gtk.Widget | None = None
        self._mode_status_row: Adw.ActionRow | None = None

        # Mode selection
        self._mode_combo: Adw.ComboRow | None = None
        self._mode_description: Gtk.Label | None = None

        # Advanced settings widgets
        self._zswap_compressor_combo: Adw.ComboRow | None = None
        self._zswap_pool_row: Adw.ActionRow | None = None
        self._zswap_pool_scale: Gtk.Scale | None = None
        self._zswap_shrinker_row: Adw.ActionRow | None = None
        self._zswap_shrinker_switch: Gtk.Switch | None = None
        self._zswap_accept_row: Adw.ActionRow | None = None
        self._zswap_accept_scale: Gtk.Scale | None = None
        self._zram_size_row: Adw.ActionRow | None = None
        self._zram_size_scale: Gtk.Scale | None = None
        self._zram_alg_combo: Adw.ComboRow | None = None
        self._swapfile_enabled_row: Adw.ActionRow | None = None
        self._swapfile_enabled_switch: Gtk.Switch | None = None
        self._swapfile_chunk_combo: Adw.ComboRow | None = None
        self._swapfile_max_count_row: Adw.ActionRow | None = None
        self._swapfile_max_count_scale: Gtk.Scale | None = None
        self._swapfile_min_count_row: Adw.ActionRow | None = None
        self._swapfile_min_count_scale: Gtk.Scale | None = None
        self._swapfile_free_ram_row: Adw.ActionRow | None = None
        self._swapfile_free_ram_scale: Gtk.Scale | None = None
        self._swapfile_free_swap_row: Adw.ActionRow | None = None
        self._swapfile_free_swap_scale: Gtk.Scale | None = None
        self._swapfile_remove_row: Adw.ActionRow | None = None
        self._swapfile_remove_scale: Gtk.Scale | None = None
        self._swapfile_discard_combo: Adw.ComboRow | None = None

        # Section groups for visibility control
        self._zswap_group: Adw.PreferencesGroup | None = None
        self._zram_group: Adw.PreferencesGroup | None = None
        self._swapfile_group: Adw.PreferencesGroup | None = None

        # Advanced expander
        self._advanced_box: Gtk.Box | None = None
        self._advanced_expander_group: Adw.PreferencesGroup | None = None

        # Live statistics
        self._stats_expander: Adw.ExpanderRow | None = None
        self._stats_ram_total_row: Adw.ActionRow | None = None
        self._stats_ram_used_row: Adw.ActionRow | None = None
        self._stats_ram_available_row: Adw.ActionRow | None = None
        self._stats_ram_buffers_row: Adw.ActionRow | None = None
        self._stats_swap_total_row: Adw.ActionRow | None = None
        self._stats_swap_in_ram_row: Adw.ActionRow | None = None
        self._stats_swap_on_disk_row: Adw.ActionRow | None = None
        self._stats_zswap_pool_row: Adw.ActionRow | None = None
        self._stats_zswap_stored_row: Adw.ActionRow | None = None
        self._stats_zswap_ratio_row: Adw.ActionRow | None = None
        self._stats_zram_size_row: Adw.ActionRow | None = None
        self._stats_zram_used_row: Adw.ActionRow | None = None
        self._stats_zram_ratio_row: Adw.ActionRow | None = None
        self._stats_swapfile_files_row: Adw.ActionRow | None = None
        self._stats_copy_btn: Gtk.Button | None = None

        # Tooltip helper
        self._tooltip_helper = TooltipHelper()

        self._setup_ui()
        self._load_state()
        self._start_monitoring()
        self._loading = False

    def _setup_ui(self) -> None:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_margin_top(8)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._setup_status_section(main_box)
        self._setup_mode_section(main_box)
        self._setup_advanced_section(main_box)
        self._setup_tooltips()

        clamp.set_child(main_box)
        scrolled.set_child(clamp)
        self.set_child(scrolled)

    def _setup_status_section(self, parent: Gtk.Box) -> None:
        # Memory Chart
        chart_group = create_preferences_group("")
        self._chart = MemoryChartWidget()
        self._chart.set_size_request(-1, 150)
        chart_group.add(self._chart)
        parent.append(chart_group)

        # Service Status
        status_group = create_preferences_group(_("Service Status"))

        self._status_row = create_status_row("systemd-swap", "Unknown")
        self._status_indicator = create_status_indicator(False, "")
        self._status_indicator.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [_("Service status indicator")],
        )
        self._status_row.add_suffix(self._status_indicator)
        status_group.add(self._status_row)

        self._mode_status_row = create_status_row(
            _("Current Mode"), self._config.mode.value
        )
        status_group.add(self._mode_status_row)

        # Live statistics (collapsed)
        self._stats_expander = Adw.ExpanderRow()
        self._stats_expander.set_title(_("Live Statistics"))
        self._stats_expander.set_subtitle(_("Active system usage info"))
        self._stats_expander.set_expanded(False)

        # --- RAM section ---
        self._stats_ram_total_row = create_status_row(_("RAM Total"), "-")
        self._stats_expander.add_row(self._stats_ram_total_row)

        self._stats_ram_used_row = create_status_row(_("RAM Used"), "-")
        self._stats_expander.add_row(self._stats_ram_used_row)

        self._stats_ram_available_row = create_status_row(_("RAM Available"), "-")
        self._stats_expander.add_row(self._stats_ram_available_row)

        self._stats_ram_buffers_row = create_status_row(_("Buffers / Cache"), "-")
        self._stats_expander.add_row(self._stats_ram_buffers_row)

        # --- Swap overview section ---
        self._stats_swap_total_row = create_status_row(_("Swap Total"), "-")
        self._stats_expander.add_row(self._stats_swap_total_row)

        self._stats_swap_in_ram_row = create_status_row(_("Swap in RAM"), "-")
        self._stats_expander.add_row(self._stats_swap_in_ram_row)

        self._stats_swap_on_disk_row = create_status_row(_("Swap on Disk"), "-")
        self._stats_expander.add_row(self._stats_swap_on_disk_row)

        # --- Zswap section ---
        self._stats_zswap_pool_row = create_status_row(_("Zswap Pool"), "-")
        self._stats_expander.add_row(self._stats_zswap_pool_row)

        self._stats_zswap_stored_row = create_status_row(_("Zswap Stored"), "-")
        self._stats_expander.add_row(self._stats_zswap_stored_row)

        self._stats_zswap_ratio_row = create_status_row(_("Zswap Ratio"), "-")
        self._stats_expander.add_row(self._stats_zswap_ratio_row)

        # --- Zram section ---
        self._stats_zram_size_row = create_status_row(_("Zram Capacity"), "-")
        self._stats_expander.add_row(self._stats_zram_size_row)

        self._stats_zram_used_row = create_status_row(_("Zram Used"), "-")
        self._stats_expander.add_row(self._stats_zram_used_row)

        self._stats_zram_ratio_row = create_status_row(_("Zram Ratio"), "-")
        self._stats_expander.add_row(self._stats_zram_ratio_row)

        # --- SwapFile section ---
        self._stats_swapfile_files_row = create_status_row(_("Swap Files"), "-")
        self._stats_expander.add_row(self._stats_swapfile_files_row)

        # --- Copy button ---
        copy_row = Adw.ActionRow()
        copy_row.set_activatable(False)
        self._stats_copy_btn = Gtk.Button()
        self._stats_copy_btn.set_icon_name("edit-copy-symbolic")
        self._stats_copy_btn.add_css_class("flat")
        self._stats_copy_btn.set_valign(Gtk.Align.CENTER)
        self._stats_copy_btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [_("Copy statistics to clipboard")],
        )
        self._stats_copy_btn.connect("clicked", self._on_copy_stats_clicked)
        copy_row.set_title(_("Copy to Clipboard"))
        copy_row.add_suffix(self._stats_copy_btn)
        copy_row.set_activatable_widget(self._stats_copy_btn)
        self._stats_expander.add_row(copy_row)

        status_group.add(self._stats_expander)
        parent.append(status_group)

    def _setup_mode_section(self, parent: Gtk.Box) -> None:
        mode_group = create_preferences_group(
            _("Swap Mode"),
            _("Choose how swap is managed on your system"),
        )

        mode_names = [SWAP_MODE_NAMES[mode] for mode in SwapMode]
        self._mode_combo = create_combo_row(
            _("Mode"),
            options=mode_names,
            on_selected=self._on_mode_changed,
        )
        mode_group.add(self._mode_combo)

        # Description label that updates with selected mode
        self._mode_description = Gtk.Label()
        self._mode_description.set_wrap(True)
        self._mode_description.set_xalign(0)
        self._mode_description.add_css_class("dim-label")
        self._mode_description.add_css_class("caption")
        self._mode_description.set_margin_start(16)
        self._mode_description.set_margin_end(16)
        self._mode_description.set_margin_top(4)
        self._mode_description.set_margin_bottom(8)
        self._mode_description.set_text(SWAP_MODE_DESCRIPTIONS[self._config.mode])

        # Wrap in a row-like ActionRow for consistent padding
        desc_row = Adw.ActionRow()
        desc_row.set_activatable(False)
        desc_row.set_child(self._mode_description)
        mode_group.add(desc_row)

        parent.append(mode_group)

    def _setup_advanced_section(self, parent: Gtk.Box) -> None:
        advanced_expander_group = create_preferences_group("")

        advanced_expander = Adw.ExpanderRow()
        advanced_expander.set_title(_("Advanced Settings"))
        advanced_expander.set_subtitle(_("Fine-tune swap parameters"))
        advanced_expander.set_expanded(False)

        self._advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._advanced_box.set_margin_top(8)
        self._advanced_box.set_margin_bottom(8)

        self._create_zswap_group()
        self._create_zram_group()
        self._create_swapfile_group()

        wrapper_row = Adw.ActionRow()
        wrapper_row.set_activatable(False)
        wrapper_row.set_child(self._advanced_box)
        advanced_expander.add_row(wrapper_row)

        advanced_expander_group.add(advanced_expander)
        self._advanced_expander_group = advanced_expander_group
        parent.append(advanced_expander_group)

        self._update_settings_visibility()

    def _create_zswap_group(self) -> None:
        self._zswap_group = create_preferences_group(
            _("Zswap"), _("Compressed RAM cache for swap")
        )

        compressor_names = [COMPRESSOR_NAMES[c] for c in Compressor]
        self._zswap_compressor_combo = create_combo_row(
            _("Compressor"),
            subtitle=_("Compression algorithm"),
            options=compressor_names,
            on_selected=self._on_zswap_compressor_changed,
        )
        self._zswap_group.add(self._zswap_compressor_combo)

        self._zswap_pool_row, self._zswap_pool_scale = create_action_row_with_scale(
            _("Max Pool Size"),
            subtitle=_("Maximum % of RAM for cache"),
            min_value=ZSWAP_MAX_POOL_MIN,
            max_value=ZSWAP_MAX_POOL_MAX,
            value=ZSWAP_MAX_POOL_DEFAULT,
            step=5,
            on_changed=self._on_zswap_pool_changed,
        )
        self._zswap_group.add(self._zswap_pool_row)

        self._zswap_shrinker_row, self._zswap_shrinker_switch = (
            create_action_row_with_switch(
                _("Proactive Shrinker"),
                subtitle=_("Move cold pages to disk proactively"),
                active=False,
                on_toggled=self._on_zswap_shrinker_changed,
            )
        )
        self._zswap_group.add(self._zswap_shrinker_row)

        self._zswap_accept_row, self._zswap_accept_scale = create_action_row_with_scale(
            _("Accept Threshold"),
            subtitle=_("Resume accepting pages when pool drops below this %"),
            min_value=ZSWAP_ACCEPT_THRESHOLD_MIN,
            max_value=ZSWAP_ACCEPT_THRESHOLD_MAX,
            value=ZSWAP_ACCEPT_THRESHOLD_DEFAULT,
            step=5,
            on_changed=self._on_zswap_accept_changed,
        )
        self._zswap_group.add(self._zswap_accept_row)
        self._advanced_box.append(self._zswap_group)

    def _create_zram_group(self) -> None:
        self._zram_group = create_preferences_group(
            _("Zram"), _("Compressed block device in RAM")
        )

        self._zram_size_row, self._zram_size_scale = create_action_row_with_scale(
            _("Virtual Size"),
            subtitle=_("Uncompressed size (% of RAM)"),
            min_value=ZRAM_SIZE_MIN,
            max_value=ZRAM_SIZE_MAX,
            value=ZRAM_SIZE_DEFAULT,
            step=5,
            on_changed=self._on_zram_size_changed,
        )
        self._zram_group.add(self._zram_size_row)

        alg_names = [COMPRESSOR_NAMES[c] for c in Compressor]
        self._zram_alg_combo = create_combo_row(
            _("Algorithm"),
            subtitle=_("Compression algorithm"),
            options=alg_names,
            on_selected=self._on_zram_alg_changed,
        )
        self._zram_group.add(self._zram_alg_combo)
        self._advanced_box.append(self._zram_group)

    def _create_swapfile_group(self) -> None:
        self._swapfile_group = create_preferences_group(
            _("Swap File"), _("Dynamic swap files on disk")
        )

        self._swapfile_enabled_row, self._swapfile_enabled_switch = (
            create_action_row_with_switch(
                _("Enabled"),
                subtitle=_("Create swap files dynamically"),
                active=True,
                on_toggled=self._on_swapfile_enabled_changed,
            )
        )
        self._swapfile_group.add(self._swapfile_enabled_row)

        self._swapfile_chunk_combo = create_combo_row(
            _("Chunk Size"),
            subtitle=_("Base size for each file"),
            options=CHUNK_SIZE_OPTIONS,
            on_selected=self._on_swapfile_chunk_changed,
        )
        self._swapfile_group.add(self._swapfile_chunk_combo)

        self._swapfile_max_count_row, self._swapfile_max_count_scale = (
            create_action_row_with_scale(
                _("Max Files"),
                subtitle=_("Maximum number of swap files (1-28)"),
                min_value=SWAPFILE_MAX_COUNT_MIN,
                max_value=SWAPFILE_MAX_COUNT_MAX,
                value=SWAPFILE_MAX_COUNT_DEFAULT,
                step=1,
                on_changed=self._on_swapfile_max_count_changed,
            )
        )
        self._swapfile_group.add(self._swapfile_max_count_row)

        self._swapfile_min_count_row, self._swapfile_min_count_scale = (
            create_action_row_with_scale(
                _("Min Files"),
                subtitle=_("Minimum number of active swap files"),
                min_value=SWAPFILE_MIN_COUNT_UI_MIN,
                max_value=SWAPFILE_MIN_COUNT_UI_MAX,
                value=1,
                step=1,
                on_changed=self._on_swapfile_min_count_changed,
            )
        )
        self._swapfile_group.add(self._swapfile_min_count_row)

        self._swapfile_free_ram_row, self._swapfile_free_ram_scale = (
            create_action_row_with_scale(
                GLib.markup_escape_text(_("Expand when RAM <")),
                subtitle=_("Create new file when free RAM falls below this %"),
                min_value=SWAPFILE_FREE_RAM_PERC_MIN,
                max_value=SWAPFILE_FREE_RAM_PERC_MAX,
                value=SWAPFILE_FREE_RAM_PERC_DEFAULT,
                step=5,
                on_changed=self._on_swapfile_free_ram_changed,
            )
        )
        self._swapfile_group.add(self._swapfile_free_ram_row)

        self._swapfile_free_swap_row, self._swapfile_free_swap_scale = (
            create_action_row_with_scale(
                GLib.markup_escape_text(_("Expand when Swap <")),
                subtitle=_("Create new file when free swap falls below this %"),
                min_value=SWAPFILE_FREE_SWAP_PERC_MIN,
                max_value=SWAPFILE_FREE_SWAP_PERC_MAX,
                value=SWAPFILE_FREE_SWAP_PERC_DEFAULT,
                step=5,
                on_changed=self._on_swapfile_free_swap_changed,
            )
        )
        self._swapfile_group.add(self._swapfile_free_swap_row)

        self._swapfile_remove_row, self._swapfile_remove_scale = (
            create_action_row_with_scale(
                _("Contract when Swap >"),
                subtitle=_("Remove idle file when swap free rises above this %"),
                min_value=SWAPFILE_REMOVE_FREE_SWAP_PERC_MIN,
                max_value=SWAPFILE_REMOVE_FREE_SWAP_PERC_MAX,
                value=SWAPFILE_REMOVE_FREE_SWAP_PERC_DEFAULT,
                step=5,
                on_changed=self._on_swapfile_remove_changed,
            )
        )
        self._swapfile_group.add(self._swapfile_remove_row)

        discard_names = [DISCARD_POLICY_NAMES[p] for p in DiscardPolicy]
        self._swapfile_discard_combo = create_combo_row(
            _("Discard Policy"),
            subtitle=_("TRIM/discard behavior for SSDs"),
            options=discard_names,
            on_selected=self._on_swapfile_discard_changed,
        )
        self._swapfile_group.add(self._swapfile_discard_combo)
        self._advanced_box.append(self._swapfile_group)

    def _setup_tooltips(self) -> None:
        if self._mode_combo:
            self._tooltip_helper.add_tooltip(self._mode_combo, "mode")
        if self._zswap_compressor_combo:
            self._tooltip_helper.add_tooltip(
                self._zswap_compressor_combo, "zswap_compressor"
            )
        if self._zswap_pool_row:
            self._tooltip_helper.add_tooltip(self._zswap_pool_row, "zswap_pool")
        if self._zram_size_row:
            self._tooltip_helper.add_tooltip(self._zram_size_row, "zram_size")
        if self._zram_alg_combo:
            self._tooltip_helper.add_tooltip(self._zram_alg_combo, "zram_algorithm")
        if self._swapfile_enabled_row:
            self._tooltip_helper.add_tooltip(
                self._swapfile_enabled_row, "swapfile_enabled"
            )
        if self._swapfile_chunk_combo:
            self._tooltip_helper.add_tooltip(
                self._swapfile_chunk_combo, "swapfile_chunk"
            )
        if self._status_row:
            self._tooltip_helper.add_tooltip(self._status_row, "status_service")
        if self._mode_status_row:
            self._tooltip_helper.add_tooltip(self._mode_status_row, "status_mode")
        # Live Statistics tooltips
        if self._stats_ram_total_row:
            self._tooltip_helper.add_tooltip(
                self._stats_ram_total_row, "stats_ram_total"
            )
        if self._stats_ram_used_row:
            self._tooltip_helper.add_tooltip(self._stats_ram_used_row, "stats_ram_used")
        if self._stats_ram_available_row:
            self._tooltip_helper.add_tooltip(
                self._stats_ram_available_row, "stats_ram_available"
            )
        if self._stats_ram_buffers_row:
            self._tooltip_helper.add_tooltip(
                self._stats_ram_buffers_row, "stats_ram_buffers"
            )
        if self._stats_swap_total_row:
            self._tooltip_helper.add_tooltip(
                self._stats_swap_total_row, "stats_swap_total"
            )
        if self._stats_swap_in_ram_row:
            self._tooltip_helper.add_tooltip(
                self._stats_swap_in_ram_row, "stats_swap_in_ram"
            )
        if self._stats_swap_on_disk_row:
            self._tooltip_helper.add_tooltip(
                self._stats_swap_on_disk_row, "stats_swap_on_disk"
            )
        if self._stats_zswap_pool_row:
            self._tooltip_helper.add_tooltip(
                self._stats_zswap_pool_row, "stats_zswap_pool"
            )
        if self._stats_zswap_stored_row:
            self._tooltip_helper.add_tooltip(
                self._stats_zswap_stored_row, "stats_zswap_stored"
            )
        if self._stats_zswap_ratio_row:
            self._tooltip_helper.add_tooltip(
                self._stats_zswap_ratio_row, "stats_zswap_ratio"
            )
        if self._stats_zram_size_row:
            self._tooltip_helper.add_tooltip(
                self._stats_zram_size_row, "stats_zram_capacity"
            )
        if self._stats_zram_used_row:
            self._tooltip_helper.add_tooltip(
                self._stats_zram_used_row, "stats_zram_used"
            )
        if self._stats_zram_ratio_row:
            self._tooltip_helper.add_tooltip(
                self._stats_zram_ratio_row, "stats_zram_ratio"
            )
        if self._stats_swapfile_files_row:
            self._tooltip_helper.add_tooltip(
                self._stats_swapfile_files_row, "stats_swapfiles"
            )
        if self._stats_copy_btn:
            self._tooltip_helper.add_tooltip(self._stats_copy_btn, "stats_copy")

    def _load_state(self) -> None:
        self._loading = True
        config = self._config

        # Mode
        mode_index = list(SwapMode).index(config.mode)
        if self._mode_combo:
            self._mode_combo.set_selected(mode_index)
        if self._mode_description:
            self._mode_description.set_text(SWAP_MODE_DESCRIPTIONS[config.mode])

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
        if self._swapfile_max_count_scale:
            self._swapfile_max_count_scale.set_value(config.swapfile.max_count)
        if self._swapfile_min_count_scale:
            self._swapfile_min_count_scale.set_value(config.swapfile.min_count)
        if self._swapfile_free_ram_scale:
            self._swapfile_free_ram_scale.set_value(config.swapfile.free_ram_perc)
        if self._swapfile_free_swap_scale:
            self._swapfile_free_swap_scale.set_value(config.swapfile.free_swap_perc)
        if self._swapfile_remove_scale:
            self._swapfile_remove_scale.set_value(config.swapfile.remove_free_swap_perc)
        if self._swapfile_discard_combo:
            discard_index = list(DiscardPolicy).index(config.swapfile.discard_policy)
            self._swapfile_discard_combo.set_selected(discard_index)

        self._loading = False

    def _deep_copy_config(self, config: SwapConfig) -> SwapConfig:
        return copy.deepcopy(config)

    def _check_config_changed(self) -> None:
        if self._loading or not self._on_config_changed:
            return
        has_changes = self._configs_differ()
        self._on_config_changed(has_changes)

    def _configs_differ(self) -> bool:
        """Check if current config differs from saved config."""
        return self._config != self._original_config

    def _start_monitoring(self) -> None:
        self._meminfo_service.start_monitoring(
            self._on_memory_update,
            CHART_UPDATE_INTERVAL_MS,
        )
        self._status_timer = GLib.timeout_add(3000, self._update_swap_status)
        self._update_swap_status()

    def stop_monitoring(self) -> None:
        self._meminfo_service.stop_monitoring()
        if self._status_timer:
            GLib.source_remove(self._status_timer)
            self._status_timer = 0

    def cleanup(self) -> None:
        """Stop monitoring and cleanup resources."""
        self.stop_monitoring()
        if hasattr(self, "_tooltip_helper") and self._tooltip_helper:
            self._tooltip_helper.cleanup()

    def _on_memory_update(self, stats: MemoryStats) -> None:
        if not self._chart:
            return

        self._latest_mem_stats = stats

        mem_text = f"{stats.mem_used_formatted} / {stats.mem_total_formatted}"

        if stats.swap_total > 0:
            swap_ram_text = stats.swap_ram_formatted
            swap_ram_percent = stats.swap_ram_percent
            swap_disk_text = stats.swap_disk_formatted
            swap_disk_percent = stats.swap_disk_percent

            self._chart.add_data_point(
                stats.mem_used_percent,
                swap_disk_percent,
                mem_text,
                swap_disk_text,
                swap_ram_percent,
                swap_ram_text,
            )
        else:
            self._chart.add_data_point(
                stats.mem_used_percent, 0.0, mem_text, "N/A", 0.0, ""
            )

    def _update_swap_status(self) -> bool:
        """Update swap status periodically (runs in GLib main loop)."""

        def _fetch_status():
            try:
                status = self._swap_service.get_status(mem_stats=self._latest_mem_stats)
                GLib.idle_add(self._apply_status_update, status)
            except Exception:
                pass

        threading.Thread(target=_fetch_status, daemon=True).start()
        return True  # Keep timer running

    def _apply_status_update(self, status: SwapStatus) -> bool:
        """Apply status update to UI (must run on main thread)."""
        self._latest_swap_status = status

        # Service state
        state_text = status.service_state.value.capitalize()
        is_active = status.service_state == ServiceState.ACTIVE
        update_status_row(self._status_row, state_text)

        if self._status_indicator and self._status_row:
            # Update existing indicator instead of recreating
            dot = self._status_indicator.get_first_child()
            if dot:
                for cls in ["success", "error", "dim-label"]:
                    dot.remove_css_class(cls)
                dot.add_css_class("success" if is_active else "dim-label")

        # Mode
        config = self._config_service.get()
        update_status_row(self._mode_status_row, config.mode.value)

        # Live statistics visibility
        self._update_live_statistics(status)

        # Update settings visibility for Auto mode
        if config.mode == SwapMode.AUTO:
            self._update_settings_visibility()

        return False  # GLib.idle_add: don't repeat

    def _format_bytes(self, size_bytes: int) -> str:
        units = ["B", "KiB", "MiB", "GiB"]
        size = float(size_bytes)
        for unit in units[:-1]:
            if abs(size) < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} {units[-1]}"

    def _update_settings_visibility(self) -> None:
        mode = self._config.mode

        # In AUTO or DISABLED mode, hide all advanced settings
        if mode in (SwapMode.AUTO, SwapMode.DISABLED):
            if self._advanced_expander_group:
                self._advanced_expander_group.set_visible(False)
            return

        # Show advanced settings for manual modes
        if self._advanced_expander_group:
            self._advanced_expander_group.set_visible(True)

        show_zswap = mode == SwapMode.ZSWAP_SWAPFILE
        show_zram = mode in (SwapMode.ZRAM_SWAPFILE, SwapMode.ZRAM_ONLY)
        show_swapfile = mode in (SwapMode.ZSWAP_SWAPFILE, SwapMode.ZRAM_SWAPFILE)

        if self._zswap_group:
            self._zswap_group.set_visible(show_zswap)
        if self._zram_group:
            self._zram_group.set_visible(show_zram)
        if self._swapfile_group:
            self._swapfile_group.set_visible(show_swapfile)

    def _update_live_statistics(self, status: SwapStatus) -> None:
        stats = self._latest_mem_stats

        # --- RAM info (always visible) ---
        if stats:
            update_status_row(self._stats_ram_total_row, stats.mem_total_formatted)
            update_status_row(
                self._stats_ram_used_row,
                f"{stats.mem_used_formatted} ({stats.mem_used_percent:.0f}%)",
            )
            update_status_row(
                self._stats_ram_available_row, stats.format_size(stats.mem_available)
            )
            buffers_cache = stats.mem_buffers + stats.mem_cached
            update_status_row(
                self._stats_ram_buffers_row, stats.format_size(buffers_cache)
            )

            # Swap overview
            if stats.swap_total > 0:
                update_status_row(
                    self._stats_swap_total_row,
                    f"{stats.swap_total_formatted} ({stats.swap_used_percent:.0f}% used)",
                )
                update_status_row(self._stats_swap_in_ram_row, stats.swap_ram_formatted)
                update_status_row(
                    self._stats_swap_on_disk_row, stats.swap_disk_formatted
                )
            else:
                update_status_row(self._stats_swap_total_row, _("None"))
                update_status_row(self._stats_swap_in_ram_row, "-")
                update_status_row(self._stats_swap_on_disk_row, "-")

        # Show/hide swap overview rows
        has_swap = stats is not None and stats.swap_total > 0
        if self._stats_swap_total_row:
            self._stats_swap_total_row.set_visible(True)
        if self._stats_swap_in_ram_row:
            self._stats_swap_in_ram_row.set_visible(has_swap)
        if self._stats_swap_on_disk_row:
            self._stats_swap_on_disk_row.set_visible(has_swap)

        has_any_active = False

        # --- Zswap ---
        zswap_visible = status.zswap.enabled
        if self._stats_zswap_pool_row:
            self._stats_zswap_pool_row.set_visible(zswap_visible)
        if self._stats_zswap_stored_row:
            self._stats_zswap_stored_row.set_visible(zswap_visible)
        if self._stats_zswap_ratio_row:
            self._stats_zswap_ratio_row.set_visible(zswap_visible)
        if zswap_visible:
            has_any_active = True
            pool_text = (
                self._format_bytes(status.zswap.pool_size_bytes)
                if status.zswap.pool_size_bytes > 0
                else "0 B"
            )
            stored_text = (
                self._format_bytes(status.zswap.stored_data_bytes)
                if status.zswap.stored_data_bytes > 0
                else "0 B"
            )
            update_status_row(self._stats_zswap_pool_row, pool_text)
            update_status_row(self._stats_zswap_stored_row, stored_text)
            # Compression ratio
            if status.zswap.stored_data_bytes > 0 and status.zswap.pool_size_bytes > 0:
                ratio = status.zswap.stored_data_bytes / status.zswap.pool_size_bytes
                update_status_row(self._stats_zswap_ratio_row, f"{ratio:.2f}x")
            else:
                update_status_row(self._stats_zswap_ratio_row, "-")

        # --- Zram ---
        zram_visible = status.zram.enabled
        if self._stats_zram_size_row:
            self._stats_zram_size_row.set_visible(zram_visible)
        if self._stats_zram_used_row:
            self._stats_zram_used_row.set_visible(zram_visible)
        if self._stats_zram_ratio_row:
            self._stats_zram_ratio_row.set_visible(zram_visible)
        if zram_visible:
            has_any_active = True
            zram_cap_text = (
                self._format_bytes(status.zram.total_size_bytes)
                if status.zram.total_size_bytes > 0
                else "0 B"
            )
            zram_used_text = (
                self._format_bytes(status.zram.used_bytes)
                if status.zram.used_bytes > 0
                else "0 B"
            )
            update_status_row(self._stats_zram_size_row, zram_cap_text)
            update_status_row(self._stats_zram_used_row, zram_used_text)
            # Zram ratio from stats (used_bytes is real RAM consumed; total_size is virtual)
            if stats and stats.zram_used > 0:
                # Read zram mm_stat for actual compression ratio
                zram_ratio = self._read_zram_compression_ratio()
                update_status_row(self._stats_zram_ratio_row, zram_ratio)
            else:
                update_status_row(self._stats_zram_ratio_row, "-")

        # --- SwapFiles ---
        swapfile_visible = status.swapfile.enabled or status.swapfile.file_count > 0
        if self._stats_swapfile_files_row:
            self._stats_swapfile_files_row.set_visible(swapfile_visible)
        if swapfile_visible:
            has_any_active = True
            if status.swapfile.files:
                total_size = sum(f.size_bytes for f in status.swapfile.files)
                total_used = sum(f.used_bytes for f in status.swapfile.files)
                files_text = f"{len(status.swapfile.files)} files ({self._format_bytes(total_used)} / {self._format_bytes(total_size)})"
            else:
                files_text = (
                    f"{status.swapfile.file_count} / {status.swapfile.max_files}"
                )
            update_status_row(self._stats_swapfile_files_row, files_text)

        if self._stats_expander:
            if not has_any_active:
                self._stats_expander.set_subtitle(_("No active swap systems"))
            else:
                active = []
                if status.zswap.enabled:
                    active.append("Zswap")
                if status.zram.enabled:
                    active.append("Zram")
                if swapfile_visible:
                    active.append("Swap File")
                self._stats_expander.set_subtitle(", ".join(active))

    def _read_zram_compression_ratio(self) -> str:
        """Read compression ratio from zram mm_stat."""
        for path in glob.glob("/sys/block/zram*/mm_stat"):
            try:
                with open(path) as f:
                    fields = f.read().split()
                if len(fields) >= 2:
                    orig = int(fields[0])
                    compr = int(fields[1])
                    if compr > 0:
                        return f"{orig / compr:.2f}x"
            except (OSError, ValueError):
                pass
        return "-"

    def _on_copy_stats_clicked(self, _button: Gtk.Button) -> None:
        """Copy live statistics to clipboard as formatted text."""
        lines = [_("=== BigLinux Swap Manager - Statistics ==="), ""]

        stats = self._latest_mem_stats
        if stats:
            lines.append(f"{_('RAM Total:')}      {stats.mem_total_formatted}")
            lines.append(
                f"{_('RAM Used:')}       {stats.mem_used_formatted} ({stats.mem_used_percent:.0f}%)"
            )
            lines.append(
                f"{_('RAM Available:')}  {stats.format_size(stats.mem_available)}"
            )
            lines.append(
                f"{_('Buffers/Cache:')}  {stats.format_size(stats.mem_buffers + stats.mem_cached)}"
            )
            lines.append("")
            if stats.swap_total > 0:
                lines.append(
                    f"{_('Swap Total:')}     {stats.swap_total_formatted} ({stats.swap_used_percent:.0f}% used)"
                )
                lines.append(f"{_('Swap in RAM:')}    {stats.swap_ram_formatted}")
                lines.append(f"{_('Swap on Disk:')}   {stats.swap_disk_formatted}")
            else:
                lines.append(f"{_('Swap Total:')}     {_('None')}")
            lines.append("")

            # Swap devices detail
            if stats.swap_devices:
                lines.append(_("Swap Devices:"))
                for dev in stats.swap_devices:
                    lines.append(
                        f"  {dev.path}: {stats.format_size(dev.used_bytes)}/{stats.format_size(dev.size_bytes)} (prio {dev.priority})"
                    )
                lines.append("")

        status = self._latest_swap_status or self._swap_service.get_status()
        lines.append(f"{_('Service State:')}  {status.service_state.value}")
        lines.append(f"{_('Mode:')}           {self._config.mode.value}")

        if status.zswap.enabled:
            lines.append("")
            lines.append(
                f"{_('Zswap Pool:')}     {self._format_bytes(status.zswap.pool_size_bytes)}"
            )
            lines.append(
                f"{_('Zswap Stored:')}   {self._format_bytes(status.zswap.stored_data_bytes)}"
            )
            if status.zswap.stored_data_bytes > 0 and status.zswap.pool_size_bytes > 0:
                ratio = status.zswap.stored_data_bytes / status.zswap.pool_size_bytes
                lines.append(f"{_('Zswap Ratio:')}    {ratio:.2f}x")
            lines.append(f"{_('Zswap Compressor:')} {status.zswap.compressor}")

        if status.zram.enabled:
            lines.append("")
            lines.append(
                f"{_('Zram Capacity:')}  {self._format_bytes(status.zram.total_size_bytes)}"
            )
            lines.append(
                f"{_('Zram Used:')}      {self._format_bytes(status.zram.used_bytes)}"
            )
            lines.append(
                f"{_('Zram Ratio:')}     {self._read_zram_compression_ratio()}"
            )

        if status.swapfile.files:
            lines.append("")
            total_size = sum(f.size_bytes for f in status.swapfile.files)
            total_used = sum(f.used_bytes for f in status.swapfile.files)
            lines.append(
                f"{_('Swap Files:')}     {len(status.swapfile.files)} ({self._format_bytes(total_used)} / {self._format_bytes(total_size)})"
            )

        text = "\n".join(lines)
        clipboard = self.get_clipboard()
        clipboard.set(text)
        if self._on_toast:
            self._on_toast(_("Statistics copied to clipboard"), 2)

    # === Callbacks ===

    def _on_mode_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.mode = list(SwapMode)[index]
        if self._mode_description:
            self._mode_description.set_text(SWAP_MODE_DESCRIPTIONS[self._config.mode])
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

    def _on_swapfile_max_count_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.swapfile.max_count = int(value)
        self._check_config_changed()

    def _on_swapfile_min_count_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.swapfile.min_count = int(value)
        self._check_config_changed()

    def _on_swapfile_free_ram_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.swapfile.free_ram_perc = int(value)
        self._check_config_changed()

    def _on_swapfile_free_swap_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.swapfile.free_swap_perc = int(value)
        self._check_config_changed()

    def _on_swapfile_remove_changed(self, value: float) -> None:
        if self._loading:
            return
        self._config.swapfile.remove_free_swap_perc = int(value)
        self._check_config_changed()

    def _on_swapfile_discard_changed(self, index: int) -> None:
        if self._loading:
            return
        self._config.swapfile.discard_policy = list(DiscardPolicy)[index]
        self._check_config_changed()

    def restore_defaults(self) -> None:
        self._config = SwapConfig()
        self._load_state()
        self._update_settings_visibility()
        self._check_config_changed()

    def mark_saved(self) -> None:
        self._original_config = self._deep_copy_config(self._config)
        self._check_config_changed()

    def get_config(self) -> SwapConfig:
        return self._config
