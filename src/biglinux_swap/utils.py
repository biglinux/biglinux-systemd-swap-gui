#!/usr/bin/env python3
"""
Utilities module for BigLinux Swap Manager.

Pure Python helpers: polkit operations and tooltip management.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import tempfile
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


def apply_config_with_pkexec(content: str) -> tuple[bool, str]:
    """
    Apply configuration using pkexec.

    Args:
        content: Configuration file content

    Returns:
        Tuple of (success, message)
    """
    try:
        if not shutil.which("pkexec"):
            return False, "pkexec not found"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".conf", prefix="swap-", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Use single pkexec call with bash to copy and set permissions
            result = subprocess.run(
                [
                    "pkexec",
                    "/bin/bash",
                    "-c",
                    f'cp "{tmp_path}" "{CONFIG_PATH}" && chmod 644 "{CONFIG_PATH}"',
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return False, result.stderr.strip() or "Unknown error"

            return True, "Configuration applied successfully.\n\nRestart your computer to apply changes."
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    except (FileNotFoundError, subprocess.SubprocessError, OSError) as e:
        logger.exception("Config apply error")
        return False, str(e)


def restart_systemd_swap() -> tuple[bool, str]:
    """Restart systemd-swap service using pkexec."""
    try:
        result = subprocess.run(
            ["pkexec", "systemctl", "restart", "systemd-swap.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or "Unknown error"
        return True, "Service restarted"
    except subprocess.SubprocessError as e:
        return False, str(e)


def stop_systemd_swap() -> tuple[bool, str]:
    """Stop and disable systemd-swap service using pkexec."""
    try:
        # Stop and disable the service in a single pkexec call
        result = subprocess.run(
            [
                "pkexec",
                "/bin/bash",
                "-c",
                "systemctl stop systemd-swap.service && systemctl disable systemd-swap.service",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or "Unknown error"

        return True, "Service stopped and disabled"
    except subprocess.SubprocessError as e:
        return False, str(e)


def enable_systemd_swap() -> tuple[bool, str]:
    """Enable and start systemd-swap service using pkexec."""
    try:
        # Enable and start the service in a single pkexec call
        result = subprocess.run(
            [
                "pkexec",
                "/bin/bash",
                "-c",
                "systemctl enable systemd-swap.service && systemctl start systemd-swap.service",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or "Unknown error"

        return True, "Service enabled and started"
    except subprocess.SubprocessError as e:
        return False, str(e)


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
# X11 Detection Helper
# =============================================================================


def _is_x11_backend() -> bool:
    """Check if running on X11 backend."""
    try:
        display = Gdk.Display.get_default()
        if display is None:
            return False
        return "X11" in type(display).__name__
    except Exception:
        return False


# =============================================================================
# Tooltip Texts
# =============================================================================


TOOLTIPS = {
    # Mode selection
    "mode_auto": _(
        "Let the system choose the best settings based on your hardware. "
        "Zswap is used when disk space is at least 5x your RAM size. "
        "Otherwise, Zram is used to save disk space."
    ),
    "mode_zswap_swapfile": _(
        "Zswap offers better performance but uses more disk space. "
        "Best for SSD with plenty of free space (5x RAM or more). "
        "Data is compressed in RAM before writing to disk files."
    ),
    "mode_zram_swapfile": _(
        "Zram uses less disk space than Zswap by compressing data in RAM. "
        "Best for HDD or systems with limited disk space. "
        "Swap files on disk serve as backup when RAM is full."
    ),
    "mode_zram_only": _(
        "Uses only compressed RAM, no disk files are created. "
        "Best for systems with very limited disk space. "
        "All swap is handled entirely in memory."
    ),
    "mode_disabled": _(
        "Completely disable swap management. "
        "The systemd-swap service will be stopped. "
        "Not recommended unless you manage swap manually."
    ),
    # Zswap options
    "zswap_toggle": _(
        "Compresses inactive memory before writing to disk. "
        "Reduces disk wear and improves performance."
    ),
    "zswap_compressor": _(
        "LZ4: Faster compression, uses more disk space.\n"
        "ZSTD: Better compression, uses less disk space."
    ),
    "zswap_pool": _(
        "How much RAM to use for compressed cache. "
        "Higher values = less disk writes but less free RAM."
    ),
    "zswap_shrinker": _(
        "Automatically releases compressed memory when system needs more RAM. "
        "Helps prevent out-of-memory situations."
    ),
    "zswap_accept_threshold": _(
        "Only compress pages that achieve this compression ratio or better. "
        "Higher values = only well-compressing data is cached."
    ),
    # Zram options
    "zram_toggle": _(
        "Creates a compressed virtual disk in RAM. "
        "Stores more data without using physical disk."
    ),
    "zram_size": _(
        "Size of compressed RAM disk. Higher values allow storing more compressed data."
    ),
    "zram_algorithm": _(
        "LZ4: Fast but less compression.\nZSTD: Slower but better compression."
    ),
    "zram_mem_limit": _(
        "Maximum actual RAM that zram can use. "
        "Prevents zram from consuming too much memory."
    ),
    "zram_priority": _(
        "Sets the priority for using zram vs other swap. "
        "Higher priority = zram is used first before disk swap."
    ),
    "zram_writeback": _(
        "Allows zram to write incompressible data to disk. "
        "Saves RAM for data that compresses well."
    ),
    # Swapfile options
    "swapfile_toggle": _(
        "Creates swap files on disk when RAM is full. "
        "Files grow and shrink automatically as needed."
    ),
    "swapfile_chunk": _(
        "Initial size when creating new swap files. "
        "Smaller = less disk space, Larger = fewer files."
    ),
    "swapfile_max_chunk": _(
        "Maximum size each swap file can grow to. "
        "Limits how much disk space a single file can use."
    ),
    "swapfile_max_count": _(
        "Maximum number of swap files to create. "
        "More files = more available swap space."
    ),
    "swapfile_scaling": _(
        "How quickly swap files grow when more space is needed. "
        "Higher values = faster growth but more disk usage."
    ),
    "swapfile_path": _(
        "Folder where swap files are stored. "
        "Choose a location on your fastest disk for best performance."
    ),
    # MGLRU options
    "mglru_toggle": _(
        "Protects active programs from being swapped out. "
        "Prevents system freezes when memory is low."
    ),
    "mglru_ttl": _(
        "How long to keep memory before allowing swap. "
        "Lower values = more aggressive swap, Higher = more protection."
    ),
    # Status indicators
    "status_service": _(
        "Shows if the swap management service is running. "
        "Green = active and working, Red = stopped or error."
    ),
    "status_mode": _(
        "Shows the current swap mode being used. "
        "This reflects the active configuration."
    ),
}


# =============================================================================
# Tooltip Helper
# =============================================================================


class TooltipHelper:
    """Manages tooltips for GTK4 widgets."""

    def __init__(self):
        self.active_widget = None
        self.show_timer_id = None
        self._use_native_tooltips = _is_x11_backend()
        self._color_css_provider = None

        if self._use_native_tooltips:
            self.popover = None
            self.label = None
            self.css_provider = None
            return

        self.popover = Gtk.Popover()
        self.popover.set_autohide(False)
        self.popover.set_has_arrow(False)
        self.popover.set_position(Gtk.PositionType.TOP)
        self.popover.set_offset(0, -12)

        self.label = Gtk.Label(
            wrap=True,
            max_width_chars=50,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
            halign=Gtk.Align.START,
        )
        self.popover.set_child(self.label)

        self.css_provider = Gtk.CssProvider()
        css = b"""
        .tooltip-popover { opacity: 0; transition: opacity 250ms ease-in-out; }
        .tooltip-popover.visible { opacity: 1; }
        """
        self.css_provider.load_from_data(css)
        self.popover.add_css_class("tooltip-popover")

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.popover.connect("map", self._on_popover_map)
        GLib.idle_add(self.update_colors)

    def _on_popover_map(self, _popover):
        if self.popover:
            self.popover.add_css_class("visible")

    def add_tooltip(self, widget, tooltip_key: str) -> None:
        """Add tooltip to a widget."""
        tooltip_text = TOOLTIPS.get(tooltip_key, "")

        if self._use_native_tooltips:
            if tooltip_text:
                widget.set_tooltip_text(tooltip_text)
            return

        widget.tooltip_key = tooltip_key
        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("enter", self._on_enter, widget)
        motion_controller.connect("leave", self._on_leave)
        widget.add_controller(motion_controller)

    def _clear_timer(self):
        if self.show_timer_id:
            # Check if source still exists before trying to remove
            context = GLib.MainContext.default()
            source = context.find_source_by_id(self.show_timer_id)
            if source is not None:
                GLib.source_remove(self.show_timer_id)
            self.show_timer_id = None

    def _on_enter(self, _controller, _x, _y, widget):
        if self.active_widget == widget:
            return
        self._clear_timer()
        self._hide_tooltip()
        self.active_widget = widget
        self.show_timer_id = GLib.timeout_add(250, self._show_tooltip)

    def _on_leave(self, _controller):
        self._clear_timer()
        if self.active_widget:
            self._hide_tooltip(animate=True)
            self.active_widget = None

    def _show_tooltip(self):
        if not self.active_widget or not self.popover:
            return GLib.SOURCE_REMOVE

        try:
            if not self.active_widget.get_mapped():
                return GLib.SOURCE_REMOVE
            if self.active_widget.get_native() is None:
                return GLib.SOURCE_REMOVE
        except Exception:
            return GLib.SOURCE_REMOVE

        tooltip_key = getattr(self.active_widget, "tooltip_key", None)
        tooltip_text = TOOLTIPS.get(tooltip_key) if tooltip_key else None
        if not tooltip_text:
            return GLib.SOURCE_REMOVE

        try:
            self.label.set_text(tooltip_text)
            if self.popover.get_parent() is not None:
                self.popover.unparent()
            self.popover.remove_css_class("visible")
            self.popover.set_parent(self.active_widget)
            self.popover.popup()
        except Exception:
            pass

        self.show_timer_id = None
        return GLib.SOURCE_REMOVE

    def _hide_tooltip(self, animate=False):
        if not self.popover or not self.popover.is_visible():
            return

        def do_cleanup():
            try:
                if self.popover:
                    self.popover.popdown()
                    if self.popover.get_parent():
                        self.popover.unparent()
            except Exception:
                pass
            return GLib.SOURCE_REMOVE

        self.popover.remove_css_class("visible")
        if animate:
            GLib.timeout_add(200, do_cleanup)
        else:
            do_cleanup()

    def update_colors(self):
        if self._use_native_tooltips:
            return

        try:
            style_manager = Adw.StyleManager.get_default()
            is_dark = style_manager.get_dark()
            if is_dark:
                bg, fg, border = "#3a3a3a", "#ffffff", "#707070"
            else:
                bg, fg, border = "#fafafa", "#2e2e2e", "#a0a0a0"
        except Exception:
            bg, fg, border = "#3a3a3a", "#ffffff", "#707070"

        css = f"""
        popover.tooltip-popover > contents {{
            background-color: {bg}; color: {fg};
            border: 1px solid {border}; border-radius: 8px;
        }}
        popover.tooltip-popover label {{ color: {fg}; }}
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

    def cleanup(self):
        self._clear_timer()
        if self.popover and self.popover.get_parent():
            with contextlib.suppress(Exception):
                self.popover.unparent()


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
