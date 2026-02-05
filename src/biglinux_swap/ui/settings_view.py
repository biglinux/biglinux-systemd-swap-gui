#!/usr/bin/env python3
"""
Settings view for BigLinux Swap Manager.

Provides interface to configure all swap-related settings.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from biglinux_swap.config import (
    CHUNK_SIZE_DEFAULT,
    CHUNK_SIZE_OPTIONS,
    COMPRESSOR_NAMES,
    MAX_CHUNK_SIZE_DEFAULT,
    MAX_CHUNK_SIZE_OPTIONS,
    MGLRU_TTL_NAMES,
    SWAP_MODE_DESCRIPTIONS,
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
    ZRAM_SIZE_DEFAULT,
    ZRAM_SIZE_MAX,
    ZRAM_SIZE_MIN,
    ZSWAP_ACCEPT_THRESHOLD_DEFAULT,
    ZSWAP_ACCEPT_THRESHOLD_MAX,
    ZSWAP_ACCEPT_THRESHOLD_MIN,
    ZSWAP_MAX_POOL_DEFAULT,
    ZSWAP_MAX_POOL_MAX,
    ZSWAP_MAX_POOL_MIN,
    ZSWAP_MAX_POOL_STEP,
    Compressor,
    MglruTtl,
    SwapConfig,
    SwapMode,
)
from biglinux_swap.services import is_mglru_supported
from biglinux_swap.ui.components import (
    create_action_button,
    create_action_row_with_scale,
    create_action_row_with_switch,
    create_combo_row,
    create_entry_row,
    create_expander_row,
    create_preferences_group,
    create_radio_group,
    create_spin_row,
)

if TYPE_CHECKING:
    from biglinux_swap.services import ConfigService

logger = logging.getLogger(__name__)


class SettingsView(Adw.NavigationPage):
    """
    Settings view for configuring swap options.

    Contains:
    - Swap mode selection
    - Zswap configuration
    - Zram configuration
    - SwapFile configuration
    - MGLRU settings
    """

    def __init__(
        self,
        config_service: ConfigService,
        on_toast: Callable[[str, int], None] | None = None,
        on_config_changed: Callable[[SwapConfig], None] | None = None,
    ) -> None:
        """
        Initialize the settings view.

        Args:
            config_service: Configuration service
            on_toast: Callback for toast notifications
            on_config_changed: Callback when config changes
        """
        super().__init__(title="Settings", tag="settings")

        self._config_service = config_service
        self._on_toast = on_toast
        self._on_config_changed = on_config_changed

        # Current config being edited
        self._config: SwapConfig = config_service.get()

        # Prevent callbacks during load
        self._loading = True

        # Widget references
        self._mode_buttons: list[Gtk.CheckButton] = []

        # Zswap widgets
        self._zswap_compressor_combo: Adw.ComboRow | None = None
        self._zswap_pool_scale: Gtk.Scale | None = None
        self._zswap_shrinker_switch: Gtk.Switch | None = None
        self._zswap_threshold_spin: Adw.SpinRow | None = None

        # Zram widgets
        self._zram_size_scale: Gtk.Scale | None = None
        self._zram_alg_combo: Adw.ComboRow | None = None
        self._zram_limit_scale: Gtk.Scale | None = None
        self._zram_writeback_switch: Gtk.Switch | None = None

        # SwapFile widgets
        self._swapfile_enabled_switch: Gtk.Switch | None = None
        self._swapfile_path_entry: Adw.EntryRow | None = None
        self._swapfile_chunk_combo: Adw.ComboRow | None = None
        self._swapfile_max_chunk_combo: Adw.ComboRow | None = None
        self._swapfile_max_count_spin: Adw.SpinRow | None = None
        self._swapfile_scaling_spin: Adw.SpinRow | None = None

        # Expander references for showing/hiding
        self._zswap_expander: Adw.ExpanderRow | None = None
        self._zram_expander: Adw.ExpanderRow | None = None
        self._swapfile_expander: Adw.ExpanderRow | None = None

        self._setup_ui()
        self._load_state()
        self._loading = False

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # Clamp for content width
        clamp = Adw.Clamp()
        clamp.set_maximum_size(600)
        clamp.set_margin_top(12)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)

        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # === Swap Mode Section ===
        mode_group = create_preferences_group(
            "Swap Mode",
            "Select how swap should be managed",
        )

        # Create radio options
        mode_options = [
            (SWAP_MODE_NAMES[mode], SWAP_MODE_DESCRIPTIONS[mode]) for mode in SwapMode
        ]

        mode_box, self._mode_buttons = create_radio_group(
            mode_options,
            selected_index=0,
            on_selected=self._on_mode_changed,
        )
        mode_group.add(mode_box)
        main_box.append(mode_group)

        # === Zswap Section ===
        zswap_group = create_preferences_group("Zswap Configuration")

        self._zswap_expander = create_expander_row(
            "Zswap Settings",
            subtitle="Compressed RAM cache + disk writeback",
            icon_name="drive-harddisk-symbolic",
            expanded=True,
        )

        # Compressor selection
        compressor_names = [COMPRESSOR_NAMES[c] for c in Compressor]
        self._zswap_compressor_combo = create_combo_row(
            "Compressor",
            subtitle="Compression algorithm",
            options=compressor_names,
            on_selected=self._on_zswap_compressor_changed,
        )
        self._zswap_expander.add_row(self._zswap_compressor_combo)

        # Pool size
        pool_row, self._zswap_pool_scale = create_action_row_with_scale(
            "Max Pool Size",
            subtitle="Maximum RAM percentage for compressed cache",
            min_value=ZSWAP_MAX_POOL_MIN,
            max_value=ZSWAP_MAX_POOL_MAX,
            value=ZSWAP_MAX_POOL_DEFAULT,
            step=ZSWAP_MAX_POOL_STEP,
            on_changed=self._on_zswap_pool_changed,
        )
        self._zswap_expander.add_row(pool_row)

        # Shrinker
        shrinker_row, self._zswap_shrinker_switch = create_action_row_with_switch(
            "Shrinker",
            subtitle="Proactively move cold pages to disk",
            active=True,
            on_toggled=self._on_zswap_shrinker_changed,
        )
        self._zswap_expander.add_row(shrinker_row)

        # Accept threshold
        self._zswap_threshold_spin = create_spin_row(
            "Accept Threshold",
            subtitle="Resume accepting when pool drops to this %",
            min_value=ZSWAP_ACCEPT_THRESHOLD_MIN,
            max_value=ZSWAP_ACCEPT_THRESHOLD_MAX,
            value=ZSWAP_ACCEPT_THRESHOLD_DEFAULT,
            on_changed=self._on_zswap_threshold_changed,
        )
        self._zswap_expander.add_row(self._zswap_threshold_spin)

        zswap_group.add(self._zswap_expander)
        main_box.append(zswap_group)

        # === Zram Section ===
        zram_group = create_preferences_group("Zram Configuration")

        self._zram_expander = create_expander_row(
            "Zram Settings",
            subtitle="Compressed block device in RAM",
            icon_name="drive-removable-media-symbolic",
            expanded=True,
        )

        # Size
        size_row, self._zram_size_scale = create_action_row_with_scale(
            "Virtual Size",
            subtitle="Uncompressed size (actual RAM usage is less)",
            min_value=ZRAM_SIZE_MIN,
            max_value=ZRAM_SIZE_MAX,
            value=ZRAM_SIZE_DEFAULT,
            step=5,
            on_changed=self._on_zram_size_changed,
        )
        self._zram_expander.add_row(size_row)

        # Algorithm
        alg_names = [COMPRESSOR_NAMES[c] for c in Compressor]
        self._zram_alg_combo = create_combo_row(
            "Algorithm",
            subtitle="Compression algorithm",
            options=alg_names,
            selected_index=0,  # lz4
            on_selected=self._on_zram_alg_changed,
        )
        self._zram_expander.add_row(self._zram_alg_combo)

        # Memory limit
        limit_row, self._zram_limit_scale = create_action_row_with_scale(
            "Memory Limit",
            subtitle="Max physical RAM zram can use (OOM protection)",
            min_value=ZRAM_MEM_LIMIT_MIN,
            max_value=ZRAM_MEM_LIMIT_MAX,
            value=ZRAM_MEM_LIMIT_DEFAULT,
            step=5,
            on_changed=self._on_zram_limit_changed,
        )
        self._zram_expander.add_row(limit_row)

        # Writeback
        wb_row, self._zram_writeback_switch = create_action_row_with_switch(
            "Writeback",
            subtitle="Move incompressible/idle pages to disk",
            active=False,
            on_toggled=self._on_zram_writeback_changed,
        )
        self._zram_expander.add_row(wb_row)

        zram_group.add(self._zram_expander)
        main_box.append(zram_group)

        # === SwapFile Section ===
        swapfile_group = create_preferences_group("SwapFile Configuration")

        self._swapfile_expander = create_expander_row(
            "SwapFile Settings",
            subtitle="Dynamic swap files",
            icon_name="document-new-symbolic",
            expanded=True,
        )

        # Enabled
        enabled_row, self._swapfile_enabled_switch = create_action_row_with_switch(
            "Enabled",
            subtitle="Enable dynamic swap file creation",
            active=True,
            on_toggled=self._on_swapfile_enabled_changed,
        )
        self._swapfile_expander.add_row(enabled_row)

        # Path
        self._swapfile_path_entry = create_entry_row(
            "Path",
            text="/swapfile",
            on_changed=self._on_swapfile_path_changed,
        )
        self._swapfile_expander.add_row(self._swapfile_path_entry)

        # Chunk size
        self._swapfile_chunk_combo = create_combo_row(
            "Chunk Size",
            subtitle="Base size for each swap file",
            options=CHUNK_SIZE_OPTIONS,
            selected_index=CHUNK_SIZE_OPTIONS.index(CHUNK_SIZE_DEFAULT),
            on_selected=self._on_swapfile_chunk_changed,
        )
        self._swapfile_expander.add_row(self._swapfile_chunk_combo)

        # Max chunk size
        self._swapfile_max_chunk_combo = create_combo_row(
            "Max Chunk Size",
            subtitle="Maximum size per swap file",
            options=MAX_CHUNK_SIZE_OPTIONS,
            selected_index=MAX_CHUNK_SIZE_OPTIONS.index(MAX_CHUNK_SIZE_DEFAULT),
            on_selected=self._on_swapfile_max_chunk_changed,
        )
        self._swapfile_expander.add_row(self._swapfile_max_chunk_combo)

        # Max count
        self._swapfile_max_count_spin = create_spin_row(
            "Max Files",
            subtitle="Maximum number of swap files (kernel limit: 32)",
            min_value=SWAPFILE_MAX_COUNT_MIN,
            max_value=SWAPFILE_MAX_COUNT_MAX,
            value=SWAPFILE_MAX_COUNT_DEFAULT,
            on_changed=self._on_swapfile_max_count_changed,
        )
        self._swapfile_expander.add_row(self._swapfile_max_count_spin)

        # Scaling step
        self._swapfile_scaling_spin = create_spin_row(
            "Scaling Step",
            subtitle="Double size every N files",
            min_value=SWAPFILE_SCALING_STEP_MIN,
            max_value=SWAPFILE_SCALING_STEP_MAX,
            value=SWAPFILE_SCALING_STEP_DEFAULT,
            on_changed=self._on_swapfile_scaling_changed,
        )
        self._swapfile_expander.add_row(self._swapfile_scaling_spin)

        swapfile_group.add(self._swapfile_expander)
        main_box.append(swapfile_group)

        # === MGLRU Section (only if kernel supports it) ===
        self._mglru_combo: Adw.ComboRow | None = None

        if is_mglru_supported():
            mglru_group = create_preferences_group(
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
            mglru_group.add(self._mglru_combo)
            main_box.append(mglru_group)

        # === Restore Defaults Button ===
        restore_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        restore_box.set_halign(Gtk.Align.CENTER)
        restore_box.set_margin_top(24)

        restore_btn = create_action_button(
            "Restore Defaults",
            style="destructive-action",
            on_clicked=self._on_restore_defaults,
            tooltip="Reset all settings to defaults",
        )
        restore_box.append(restore_btn)
        main_box.append(restore_box)

        clamp.set_child(main_box)
        scrolled.set_child(clamp)
        self.set_child(scrolled)

    def _load_state(self) -> None:
        """Load current configuration into UI."""
        self._loading = True

        config = self._config

        # Mode selection
        mode_index = list(SwapMode).index(config.mode)
        if mode_index < len(self._mode_buttons):
            self._mode_buttons[mode_index].set_active(True)

        # Zswap settings
        compressor_index = list(Compressor).index(config.zswap.compressor)
        if self._zswap_compressor_combo:
            self._zswap_compressor_combo.set_selected(compressor_index)

        if self._zswap_pool_scale:
            self._zswap_pool_scale.set_value(config.zswap.max_pool_percent)

        if self._zswap_shrinker_switch:
            self._zswap_shrinker_switch.set_active(config.zswap.shrinker_enabled)

        if self._zswap_threshold_spin:
            self._zswap_threshold_spin.set_value(config.zswap.accept_threshold)

        # Zram settings
        if self._zram_size_scale:
            self._zram_size_scale.set_value(config.zram.size_percent)

        alg_index = list(Compressor).index(config.zram.alg)
        if self._zram_alg_combo:
            self._zram_alg_combo.set_selected(alg_index)

        if self._zram_limit_scale:
            self._zram_limit_scale.set_value(config.zram.mem_limit_percent)

        if self._zram_writeback_switch:
            self._zram_writeback_switch.set_active(config.zram.writeback_enabled)

        # SwapFile settings
        if self._swapfile_enabled_switch:
            self._swapfile_enabled_switch.set_active(config.swapfile.enabled)

        if self._swapfile_path_entry:
            self._swapfile_path_entry.set_text(config.swapfile.path)

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
                else 3
            )
            self._swapfile_max_chunk_combo.set_selected(max_chunk_index)

        if self._swapfile_max_count_spin:
            self._swapfile_max_count_spin.set_value(config.swapfile.max_count)

        if self._swapfile_scaling_spin:
            self._swapfile_scaling_spin.set_value(config.swapfile.scaling_step)

        # MGLRU
        mglru_index = list(MglruTtl).index(config.mglru_min_ttl)
        if hasattr(self, "_mglru_combo") and self._mglru_combo:
            self._mglru_combo.set_selected(mglru_index)

        # Update visibility based on mode
        self._update_section_visibility()

        self._loading = False

    def _update_section_visibility(self) -> None:
        """Update section visibility based on current mode."""
        mode = self._config.mode

        # Zswap visible for AUTO, ZSWAP_SWAPFILE (hidden when DISABLED)
        zswap_visible = mode in (
            SwapMode.AUTO,
            SwapMode.ZSWAP_SWAPFILE,
        )
        if self._zswap_expander:
            parent = self._zswap_expander.get_parent()
            if parent:
                parent.get_parent().set_visible(zswap_visible)

        # Zram visible for AUTO, ZRAM_SWAPFILE, ZRAM_ONLY (hidden when DISABLED)
        zram_visible = mode in (
            SwapMode.AUTO,
            SwapMode.ZRAM_SWAPFILE,
            SwapMode.ZRAM_ONLY,
        )
        if self._zram_expander:
            parent = self._zram_expander.get_parent()
            if parent:
                parent.get_parent().set_visible(zram_visible)

        # SwapFile visible for AUTO, ZSWAP_SWAPFILE, ZRAM_SWAPFILE (hidden when DISABLED)
        swapfile_visible = mode in (
            SwapMode.AUTO,
            SwapMode.ZSWAP_SWAPFILE,
            SwapMode.ZRAM_SWAPFILE,
        )
        if self._swapfile_expander:
            parent = self._swapfile_expander.get_parent()
            if parent:
                parent.get_parent().set_visible(swapfile_visible)

    def _notify_change(self) -> None:
        """Notify about configuration change."""
        if not self._loading and self._on_config_changed:
            self._on_config_changed(self._config)

    # === Mode callbacks ===

    def _on_mode_changed(self, index: int) -> None:
        """Handle mode selection change."""
        if self._loading:
            return
        self._config.mode = list(SwapMode)[index]
        self._update_section_visibility()
        self._notify_change()

    # === Zswap callbacks ===

    def _on_zswap_compressor_changed(self, index: int) -> None:
        """Handle zswap compressor change."""
        if self._loading:
            return
        self._config.zswap.compressor = list(Compressor)[index]
        self._notify_change()

    def _on_zswap_pool_changed(self, value: float) -> None:
        """Handle zswap pool size change."""
        if self._loading:
            return
        self._config.zswap.max_pool_percent = int(value)
        self._notify_change()

    def _on_zswap_shrinker_changed(self, active: bool) -> None:
        """Handle zswap shrinker toggle."""
        if self._loading:
            return
        self._config.zswap.shrinker_enabled = active
        self._notify_change()

    def _on_zswap_threshold_changed(self, value: float) -> None:
        """Handle zswap threshold change."""
        if self._loading:
            return
        self._config.zswap.accept_threshold = int(value)
        self._notify_change()

    # === Zram callbacks ===

    def _on_zram_size_changed(self, value: float) -> None:
        """Handle zram size change."""
        if self._loading:
            return
        self._config.zram.size_percent = int(value)
        self._notify_change()

    def _on_zram_alg_changed(self, index: int) -> None:
        """Handle zram algorithm change."""
        if self._loading:
            return
        self._config.zram.alg = list(Compressor)[index]
        self._notify_change()

    def _on_zram_limit_changed(self, value: float) -> None:
        """Handle zram limit change."""
        if self._loading:
            return
        self._config.zram.mem_limit_percent = int(value)
        self._notify_change()

    def _on_zram_writeback_changed(self, active: bool) -> None:
        """Handle zram writeback toggle."""
        if self._loading:
            return
        self._config.zram.writeback_enabled = active
        self._notify_change()

    # === SwapFile callbacks ===

    def _on_swapfile_enabled_changed(self, active: bool) -> None:
        """Handle swapfile enabled toggle."""
        if self._loading:
            return
        self._config.swapfile.enabled = active
        self._notify_change()

    def _on_swapfile_path_changed(self, text: str) -> None:
        """Handle swapfile path change."""
        if self._loading:
            return
        self._config.swapfile.path = text
        self._notify_change()

    def _on_swapfile_chunk_changed(self, index: int) -> None:
        """Handle swapfile chunk size change."""
        if self._loading:
            return
        self._config.swapfile.chunk_size = CHUNK_SIZE_OPTIONS[index]
        self._notify_change()

    def _on_swapfile_max_chunk_changed(self, index: int) -> None:
        """Handle swapfile max chunk size change."""
        if self._loading:
            return
        self._config.swapfile.max_chunk_size = MAX_CHUNK_SIZE_OPTIONS[index]
        self._notify_change()

    def _on_swapfile_max_count_changed(self, value: float) -> None:
        """Handle swapfile max count change."""
        if self._loading:
            return
        self._config.swapfile.max_count = int(value)
        self._notify_change()

    def _on_swapfile_scaling_changed(self, value: float) -> None:
        """Handle swapfile scaling step change."""
        if self._loading:
            return
        self._config.swapfile.scaling_step = int(value)
        self._notify_change()

    # === MGLRU callback ===

    def _on_mglru_changed(self, index: int) -> None:
        """Handle MGLRU setting change."""
        if self._loading:
            return
        self._config.mglru_min_ttl = list(MglruTtl)[index]
        self._notify_change()

    # === Restore defaults ===

    def _on_restore_defaults(self) -> None:
        """Restore default configuration."""
        self._config = SwapConfig()
        self._load_state()
        self._notify_change()

        if self._on_toast:
            self._on_toast("Settings restored to defaults", 3)

    def get_config(self) -> SwapConfig:
        """Get current configuration."""
        return self._config
