#!/usr/bin/env python3
"""
Utilities module for BigLinux Swap Manager.

Pure Python helpers: polkit operations and tooltip management.
"""

from __future__ import annotations

import contextlib
import logging
import shlex
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from biglinux_swap.config import CONFIG_PATH
from biglinux_swap.i18n import _

logger = logging.getLogger(__name__)


# =============================================================================
# Polkit Utilities
# =============================================================================


def apply_config_with_pkexec(
    content: str,
    on_complete: Callable[[bool, str], None] | None = None,
) -> None:
    """Apply configuration using pkexec (non-blocking)."""

    def _run():
        try:
            if not shutil.which("pkexec"):
                if on_complete:
                    GLib.idle_add(on_complete, False, _("pkexec not found"))
                return

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".conf", prefix="swap-", delete=False
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            cmd = [
                "pkexec",
                "/bin/bash",
                "-c",
                f"cp {shlex.quote(tmp_path)} {shlex.quote(str(CONFIG_PATH))} && chmod 644 {shlex.quote(str(CONFIG_PATH))}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            Path(tmp_path).unlink(missing_ok=True)
            success = result.returncode == 0
            msg = result.stderr.strip() if not success else ""
            if on_complete:
                GLib.idle_add(on_complete, success, msg)
        except subprocess.TimeoutExpired:
            if on_complete:
                GLib.idle_add(on_complete, False, _("Operation timed out"))
        except Exception as e:
            logger.exception("Config apply error")
            if on_complete:
                GLib.idle_add(on_complete, False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def restart_systemd_swap(
    on_complete: Callable[[bool, str], None] | None = None,
) -> None:
    """Restart systemd-swap service using pkexec (non-blocking)."""

    def _run():
        try:
            result = subprocess.run(
                ["pkexec", "systemctl", "restart", "systemd-swap.service"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            success = result.returncode == 0
            msg = result.stderr.strip() if not success else ""
            if on_complete:
                GLib.idle_add(on_complete, success, msg)
        except Exception as e:
            if on_complete:
                GLib.idle_add(on_complete, False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def stop_systemd_swap(on_complete: Callable[[bool, str], None] | None = None) -> None:
    """Stop and disable systemd-swap service using pkexec (non-blocking)."""

    def _run():
        try:
            result = subprocess.run(
                [
                    "pkexec",
                    "/bin/bash",
                    "-c",
                    "systemctl stop systemd-swap.service && systemctl disable systemd-swap.service",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            success = result.returncode == 0
            msg = result.stderr.strip() if not success else ""
            if on_complete:
                GLib.idle_add(on_complete, success, msg)
        except Exception as e:
            if on_complete:
                GLib.idle_add(on_complete, False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def enable_systemd_swap(on_complete: Callable[[bool, str], None] | None = None) -> None:
    """Enable and start systemd-swap service using pkexec (non-blocking)."""

    def _run():
        try:
            result = subprocess.run(
                [
                    "pkexec",
                    "/bin/bash",
                    "-c",
                    "systemctl enable systemd-swap.service && systemctl start systemd-swap.service",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            success = result.returncode == 0
            msg = result.stderr.strip() if not success else ""
            if on_complete:
                GLib.idle_add(on_complete, success, msg)
        except Exception as e:
            if on_complete:
                GLib.idle_add(on_complete, False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def check_pkexec_available() -> bool:
    """Check if pkexec is available."""
    return shutil.which("pkexec") is not None


def run_as_root(command: list[str]) -> tuple[bool, str, str]:
    """Run a command as root using pkexec."""
    try:
        result = subprocess.run(
            ["pkexec", *command], capture_output=True, text=True, check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.SubprocessError as e:
        return False, "", str(e)


# =============================================================================
# Tooltip Texts
# =============================================================================

TOOLTIPS = {
    # Mode selection
    "mode": _(
        "Auto: Detects the best settings based on your hardware.\n"
        "Zswap is used when disk space is at least 5x your RAM.\n"
        "Otherwise, Zram is used to save disk space.\n\n"
        "In Auto mode, all parameters are optimized automatically\n"
        "and advanced settings are hidden."
    ),
    # Zswap options
    "zswap_compressor": _(
        "Zstd: Better compression ratio, stores more data in less RAM.\n"
        "Recommended for most systems — modern CPUs handle it efficiently.\n\n"
        "LZ4: Faster but lower compression. Only useful if CPU is very slow."
    ),
    "zswap_pool": _(
        "Maximum percentage of RAM reserved for the zswap compressed cache.\n"
        "Higher = more data cached in RAM before writing to disk.\n"
        "Lower = more free RAM for applications.\n\n"
        "Recommended: 25-50% depending on workload."
    ),
    # Zram options
    "zram_size": _(
        "Virtual (uncompressed) size of the zram block device.\n"
        "With compression, actual RAM usage is much less.\n"
        "Example: 80% with 3:1 compression uses ~27% of real RAM.\n\n"
        "Higher values allow storing more compressed data."
    ),
    "zram_algorithm": _(
        "Zstd: Better compression ratio, saves more memory.\n"
        "Recommended for all systems — modern CPUs handle it well.\n\n"
        "LZ4: Faster but compresses less. May waste RAM."
    ),
    # Swapfile options
    "swapfile_enabled": _(
        "Creates swap files on disk when RAM is full.\n"
        "Files grow and shrink automatically as needed.\n"
        "Uses progressive scaling: starts small, doubles as demand increases.\n\n"
        "Requires a supported filesystem (btrfs, ext4, or xfs)."
    ),
    "swapfile_chunk": _(
        "Base size for each new swap file.\n"
        "With progressive scaling, this is the starting size.\n"
        "Files 1-4: base size, Files 5-8: 2x, Files 9-12: 4x, etc.\n\n"
        "512MB: Good for most systems.\n"
        "1GB: Better for systems with 8GB+ RAM."
    ),
    # Live Statistics — RAM
    "stats_ram_total": _(
        "Total physical memory (RAM) installed in the system.\n"
        "This is the hardware limit — applications and OS share this pool."
    ),
    "stats_ram_used": _(
        "Memory currently in use by applications and the system.\n"
        "Includes active processes, libraries, and kernel allocations."
    ),
    "stats_ram_available": _(
        "Memory available for new allocations.\n"
        "Includes free RAM plus reclaimable file cache and buffers.\n"
        "This is the practical indicator of how much RAM is free."
    ),
    "stats_ram_buffers": _(
        "Memory used for disk buffers and file cache.\n"
        "The kernel reclaims this automatically when applications need RAM.\n"
        "High values here are normal and indicate efficient disk caching."
    ),
    # Live Statistics — Swap overview
    "stats_swap_total": _(
        "Total swap space available across all backends.\n"
        "Combines zram (compressed in RAM), zswap, and disk swap files."
    ),
    "stats_swap_in_ram": _(
        "Swap data stored in compressed RAM (zswap pool or zram).\n"
        "Faster than disk swap — data is compressed and kept in memory."
    ),
    "stats_swap_on_disk": _(
        "Swap data written to disk (swap files or partitions).\n"
        "Slower than in-RAM swap. Used when compressed cache is full."
    ),
    # Live Statistics — Zswap
    "stats_zswap_pool": _(
        "RAM used by the zswap compressed cache pool.\n"
        "Zswap intercepts pages being swapped out and compresses them in RAM\n"
        "before they reach the disk, reducing I/O significantly."
    ),
    "stats_zswap_stored": _(
        "Original (uncompressed) size of data stored in zswap.\n"
        "Compare with Pool size to see how much RAM compression saves."
    ),
    "stats_zswap_ratio": _(
        "Compression ratio of zswap data.\n"
        "Higher = more data fits in less RAM. Typical zstd ratio: 2-4x.\n"
        "Example: 3.0x means 3 GB of data fits in ~1 GB of RAM."
    ),
    # Live Statistics — Zram
    "stats_zram_capacity": _(
        "Virtual (uncompressed) size of the zram block device.\n"
        "This is the maximum amount of data zram can hold before compression.\n"
        "Actual RAM usage depends on the compression ratio."
    ),
    "stats_zram_used": _(
        "Data currently stored in zram, compressed in RAM.\n"
        "With zstd compression, actual RAM usage is typically 30-50% of this."
    ),
    "stats_zram_ratio": _(
        "Compression ratio of zram data.\n"
        "Formula: original data size / compressed size.\n"
        "Higher = better compression. Typical zstd ratio: 2-4x."
    ),
    # Live Statistics — Swap files
    "stats_swapfiles": _(
        "Number of dynamic swap files and their total usage.\n"
        "Files are created and removed automatically as demand changes."
    ),
    "stats_copy": _(
        "Copy all current statistics to the clipboard.\n"
        "Useful for sharing diagnostics or reporting issues."
    ),
    # Status indicators
    "status_service": _(
        "Shows if the swap management service is running.\n"
        "Green = active and managing swap automatically.\n"
        "Gray = stopped or not installed."
    ),
    "status_mode": _(
        "The current swap mode in use.\n"
        "In Auto mode, the system detects the optimal configuration."
    ),
    # HeaderBar
    "header_about": _("View application information and version."),
    "header_menu": _("Access main menu, restore defaults, and quit."),
    "header_apply": _("Apply current configuration changes to the system."),
}


class TooltipHelper:
    """
    Manages custom tooltips using Widget-Anchored Gtk.Popover.

    Adapted from big-audio-converter's portable TooltipHelper.
    Uses CSS-styled popovers with fade animation instead of native tooltips,
    providing a more consistent and visually appealing experience.
    """

    def __init__(self) -> None:
        self.active_popover: Gtk.Popover | None = None
        self.active_widget: Gtk.Widget | None = None
        self.show_timer_id: int | None = None
        self.hide_timer_id: int | None = None
        self.closing_popover: Gtk.Popover | None = None
        self._color_css_provider: Gtk.CssProvider | None = None
        self._colors_initialized: bool = False
        self._tracked_windows: set[Gtk.Window] = set()
        self._widgets_with_tooltips: set[Gtk.Widget] = set()

        # Connect to Adwaita style manager for automatic theme updates
        with contextlib.suppress(Exception):
            style_manager = Adw.StyleManager.get_default()
            style_manager.connect("notify::dark", self._on_theme_changed)
            style_manager.connect("notify::color-scheme", self._on_theme_changed)

    def _on_theme_changed(
        self, _style_manager: Adw.StyleManager, _pspec: object
    ) -> None:
        GLib.idle_add(self._apply_default_colors)

    def _apply_default_colors(self) -> int:
        try:
            style_manager = Adw.StyleManager.get_default()
            is_dark = style_manager.get_dark()
            bg_color = "#1a1a1a" if is_dark else "#fafafa"
            fg_color = "#ffffff" if is_dark else "#2e2e2e"
        except Exception:
            bg_color = "#2a2a2a"
            fg_color = "#ffffff"
        self._apply_css(bg_color, fg_color)
        return GLib.SOURCE_REMOVE

    def _ensure_colors_initialized(self) -> None:
        if not self._colors_initialized:
            self._apply_default_colors()
            self._colors_initialized = True

    def _apply_css(self, bg_color: str, fg_color: str) -> None:
        luminance = self._luminance(bg_color)
        is_dark = luminance < 0.5
        tooltip_bg = self._adjust_bg(bg_color)
        border_color = "#707070" if is_dark else "#a0a0a0"

        css = f"""
popover.custom-tooltip-static {{
    background: transparent;
    box-shadow: none;
    padding: 12px;
    opacity: 0;
    transition: opacity 200ms ease-in-out;
}}
popover.custom-tooltip-static.visible {{
    opacity: 1;
}}
popover.custom-tooltip-static > contents {{
    background-color: {tooltip_bg};
    color: {fg_color};
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid {border_color};
}}
popover.custom-tooltip-static label {{
    color: {fg_color};
}}
"""
        display = Gdk.Display.get_default()
        if not display:
            return

        if self._color_css_provider:
            with contextlib.suppress(Exception):
                Gtk.StyleContext.remove_provider_for_display(
                    display, self._color_css_provider
                )

        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        with contextlib.suppress(Exception):
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 100
            )
            self._color_css_provider = provider

    @staticmethod
    def _luminance(color: str) -> float:
        try:
            h = color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (0.299 * r + 0.587 * g + 0.114 * b) / 255
        except Exception:
            return 0.5

    @staticmethod
    def _adjust_bg(bg_color: str) -> str:
        try:
            h = bg_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            adj = 40 if lum < 0.5 else -20
            r = max(0, min(255, r + adj))
            g = max(0, min(255, g + adj))
            b = max(0, min(255, b + adj))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return bg_color

    def add_tooltip(self, widget: Gtk.Widget, tooltip_key: str) -> None:
        """Add a custom popover tooltip to a widget."""
        tooltip_text = TOOLTIPS.get(tooltip_key, "")
        if not tooltip_text:
            return

        widget._custom_tooltip_text = tooltip_text  # type: ignore[attr-defined]
        widget.set_tooltip_text(None)  # Disable native tooltip
        self._add_controller(widget)
        self._widgets_with_tooltips.add(widget)
        self._setup_window_focus_tracking(widget)

    def _setup_window_focus_tracking(self, widget: Gtk.Widget) -> None:
        def on_realize(w: Gtk.Widget) -> None:
            root = w.get_root()
            if (
                root
                and isinstance(root, Gtk.Window)
                and root not in self._tracked_windows
            ):
                self._tracked_windows.add(root)
                root.connect("notify::is-active", self._on_window_active_changed)
                root.connect("notify::maximized", self._on_window_state_changed)
                root.connect("notify::fullscreened", self._on_window_state_changed)

        if widget.get_realized():
            on_realize(widget)
        else:
            widget.connect("realize", on_realize)

    def _on_window_state_changed(self, _window: Gtk.Window, _pspec: object) -> None:
        self._clear_timer()
        self.hide(immediate=True)
        self.active_widget = None
        self._popdown_all_cached()

    def _on_window_active_changed(self, window: Gtk.Window, _pspec: object) -> None:
        if not window.get_property("is-active"):
            self._clear_timer()
            self.hide(immediate=True)
            self.active_widget = None
            self._popdown_all_cached()

    def _add_controller(self, widget: Gtk.Widget) -> None:
        if getattr(widget, "_has_custom_tooltip_controller", False):
            return

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", self._on_enter, widget)
        motion.connect("leave", self._on_leave)
        widget.add_controller(motion)

        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_click)
        widget.add_controller(click)

        widget._has_custom_tooltip_controller = True  # type: ignore[attr-defined]

    def _on_click(self, *_args: object) -> None:
        self._clear_timer()
        self.hide(immediate=True)
        self.active_widget = None

    def _clear_timer(self) -> None:
        if self.show_timer_id:
            GLib.source_remove(self.show_timer_id)
            self.show_timer_id = None
        if self.hide_timer_id:
            GLib.source_remove(self.hide_timer_id)
            self.hide_timer_id = None
        if self.closing_popover:
            with contextlib.suppress(Exception):
                self.closing_popover.popdown()
                self.closing_popover.remove_css_class("visible")
            self.closing_popover = None

    def _on_enter(
        self, _ctrl: Gtk.EventControllerMotion, _x: float, _y: float, widget: Gtk.Widget
    ) -> None:
        if self.active_widget and self.active_widget != widget:
            self.hide(immediate=True)
        self._clear_timer()
        self.active_widget = widget
        self.show_timer_id = GLib.timeout_add(150, self._show_tooltip_impl)

    def _on_leave(self, ctrl: Gtk.EventControllerMotion) -> None:
        widget = ctrl.get_widget()
        if self.active_widget == widget:
            self._clear_timer()
            self.hide()
            self.active_widget = None

    def _get_widget_popover(self, widget: Gtk.Widget) -> tuple[Gtk.Popover, Gtk.Label]:
        if not hasattr(widget, "_custom_tooltip_popover"):
            popover = Gtk.Popover()
            popover.set_has_arrow(False)
            popover.set_position(Gtk.PositionType.TOP)
            popover.set_can_target(False)
            popover.set_focusable(False)
            popover.set_autohide(False)
            popover.add_css_class("custom-tooltip-static")

            label = Gtk.Label(wrap=True, max_width_chars=45)
            label.set_halign(Gtk.Align.CENTER)
            popover.set_child(label)
            popover.set_parent(widget)

            widget._custom_tooltip_popover = (popover, label)  # type: ignore[attr-defined]
        return widget._custom_tooltip_popover  # type: ignore[attr-defined]

    def _show_tooltip_impl(self) -> bool:
        self.show_timer_id = None
        if not self.active_widget:
            return GLib.SOURCE_REMOVE

        self._ensure_colors_initialized()

        text = getattr(self.active_widget, "_custom_tooltip_text", None)
        if not text or not self.active_widget.get_mapped():
            return GLib.SOURCE_REMOVE

        root = self.active_widget.get_root()
        if root and isinstance(root, Gtk.Window) and not root.is_active():
            return GLib.SOURCE_REMOVE

        try:
            popover, label = self._get_widget_popover(self.active_widget)
            label.set_text(text)

            alloc = self.active_widget.get_allocation()
            rect = Gdk.Rectangle()
            rect.x = 0
            rect.y = 0
            rect.width = alloc.width
            rect.height = alloc.height
            popover.set_pointing_to(rect)
            popover.popup()
            popover.set_visible(True)
            popover.add_css_class("visible")
            self.active_popover = popover
        except Exception:
            logger.exception("Error showing tooltip")

        return GLib.SOURCE_REMOVE

    def hide(self, immediate: bool = False) -> None:
        if not self.active_popover:
            return

        popover_to_hide = self.active_popover
        self.active_popover = None
        self.closing_popover = popover_to_hide

        with contextlib.suppress(Exception):
            popover_to_hide.remove_css_class("visible")

        if immediate:
            with contextlib.suppress(Exception):
                popover_to_hide.popdown()
            self.closing_popover = None
        else:

            def do_popdown() -> bool:
                with contextlib.suppress(Exception):
                    popover_to_hide.popdown()
                self.hide_timer_id = None
                self.closing_popover = None
                return GLib.SOURCE_REMOVE

            if self.hide_timer_id:
                GLib.source_remove(self.hide_timer_id)
            self.hide_timer_id = GLib.timeout_add(300, do_popdown)

    def _popdown_all_cached(self) -> None:
        """Force popdown all cached tooltip popovers on every tracked widget."""
        for widget in self._widgets_with_tooltips:
            with contextlib.suppress(Exception):
                if hasattr(widget, "_custom_tooltip_popover"):
                    popover, _ = widget._custom_tooltip_popover
                    popover.popdown()

    def cleanup(self) -> None:
        """Cleanup all tooltips on shutdown."""
        self._clear_timer()
        self.hide(immediate=True)
        for widget in self._widgets_with_tooltips:
            data = getattr(widget, "_custom_tooltip_popover", None)
            if data:
                popover, _ = data
                popover.popdown()
                popover.unparent()
        self._widgets_with_tooltips.clear()


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "TooltipHelper",
    "TOOLTIPS",
    "apply_config_with_pkexec",
    "check_pkexec_available",
    "enable_systemd_swap",
    "restart_systemd_swap",
    "run_as_root",
    "stop_systemd_swap",
]
