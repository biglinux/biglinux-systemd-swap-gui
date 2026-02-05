#!/usr/bin/env python3
"""
Main window for BigLinux Swap Manager.

Adwaita ApplicationWindow with single unified view.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from biglinux_swap.config import APP_NAME, SwapConfig, SwapMode
from biglinux_swap.ui.unified_view import UnifiedView
from biglinux_swap.utils import (
    apply_config_with_pkexec,
    enable_systemd_swap,
    stop_systemd_swap,
)
from biglinux_swap.i18n import _


if TYPE_CHECKING:
    from biglinux_swap.services import ConfigService, MeminfoService, SwapService

logger = logging.getLogger(__name__)


class SwapWindow(Adw.ApplicationWindow):
    """
    Main application window.

    Contains:
    - HeaderBar with menu
    - UnifiedView with status and settings
    - ToastOverlay for notifications
    """

    def __init__(
        self,
        application: Adw.Application,
        config_service: ConfigService,
        meminfo_service: MeminfoService,
        swap_service: SwapService,
    ) -> None:
        """
        Initialize the window.

        Args:
            application: Parent application
            config_service: Configuration service
            meminfo_service: Memory info service
            swap_service: Swap status service
        """
        super().__init__(application=application)

        self._config_service = config_service
        self._meminfo_service = meminfo_service
        self._swap_service = swap_service

        # View reference
        self._unified_view: UnifiedView | None = None

        self._setup_window()
        self._setup_ui()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.set_title(APP_NAME)
        self.set_default_size(800, 800)
        self.set_size_request(450, 600)

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        # Toast overlay (root container)
        self._toast_overlay = Adw.ToastOverlay()

        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        self._header = Adw.HeaderBar()

        # Apply button on the left (opposite side of window controls)
        self._apply_btn = Gtk.Button()
        self._apply_btn.set_label("Apply")
        self._apply_btn.add_css_class("suggested-action")
        self._apply_btn.set_tooltip_text("Apply configuration changes")
        self._apply_btn.connect("clicked", self._on_apply_clicked)
        self._apply_btn.set_sensitive(False)  # Disabled until changes are made
        self._header.pack_start(self._apply_btn)

        # Menu button
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Menu")

        # Build menu
        menu = Gio.Menu()
        menu.append("Restore Defaults", "app.restore_defaults")
        menu.append("Refresh", "app.refresh")
        menu.append_section(None, self._create_about_section())
        menu_btn.set_menu_model(menu)

        self._header.pack_end(menu_btn)
        main_box.append(self._header)

        # Unified view (status + settings in one page)
        self._unified_view = UnifiedView(
            config_service=self._config_service,
            swap_service=self._swap_service,
            meminfo_service=self._meminfo_service,
            on_toast=self._show_toast,
            on_apply=self._apply_config,
            on_config_changed=self._on_config_changed,
        )
        self._unified_view.set_vexpand(True)
        main_box.append(self._unified_view)

        self._toast_overlay.set_child(main_box)
        self.set_content(self._toast_overlay)

    def _on_config_changed(self, has_changes: bool) -> None:
        """Handle config changed notification from unified view."""
        self._apply_btn.set_sensitive(has_changes)

    def _show_toast(self, message: str, timeout: int = 3) -> None:
        """
        Show a toast notification.

        Args:
            message: Toast message
            timeout: Display duration in seconds
        """
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self._toast_overlay.add_toast(toast)

    def _show_success_dialog(self, title: str, body: str) -> None:
        """
        Show a success dialog with OK button.

        Args:
            title: Dialog title
            body: Dialog body message
        """
        dialog = Adw.MessageDialog.new(self, title, body)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present()

    def _apply_config(self, config: SwapConfig) -> None:
        """
        Apply configuration changes using pkexec.

        Checks if any swap is in use:
        - If in use: only saves config, requires restart for safety
        - If not in use: applies config and restarts service immediately

        Args:
            config: Configuration to apply
        """
        # Check if any swap (files, zram, partitions) has data in use
        swap_in_use = self._swap_service.has_any_swap_in_use()

        # Handle DISABLED mode
        if config.mode == SwapMode.DISABLED:
            if swap_in_use:
                self._show_success_dialog(
                    "Restart Required",
                    "There is data in swap.\n\n"
                    "For safety, please restart your computer to disable swap.\n"
                    "This prevents system freezes from disabling active swap.",
                )
                return

            self._show_toast("Stopping swap service...")

            def on_stop_complete(success: bool, message: str) -> bool:
                if success:
                    self._show_toast("Swap management disabled")
                    self._config_service.load()
                    if self._unified_view:
                        self._unified_view.mark_saved()
                else:
                    self._show_toast(f"Failed: {message}", 5)
                return False

            def stop_async() -> bool:
                success, message = stop_systemd_swap()
                GLib.idle_add(on_stop_complete, success, message)
                return False

            GLib.timeout_add(100, stop_async)
            return

        # Generate config content
        content = self._config_service.generate_config_content(config)

        # Show applying indicator
        self._show_toast("Applying configuration...")

        # Apply with pkexec in background
        def on_complete(success: bool, needs_restart: bool) -> bool:
            if success:
                self._config_service.load()
                # Mark as saved to disable Apply button
                if self._unified_view:
                    self._unified_view.mark_saved()

                if needs_restart:
                    # Swap in use - only config saved, needs restart
                    self._show_success_dialog(
                        "Restart Required",
                        "Configuration saved successfully.\n\n"
                        "There is data in swap. For safety, please restart\n"
                        "your computer to apply the changes without risk of freezes.",
                    )
                else:
                    # No swap in use - service restarted immediately
                    self._show_success_dialog(
                        "Configuration Applied",
                        "Configuration applied and service restarted successfully.",
                    )
            return False

        def apply_async() -> bool:
            success, message = apply_config_with_pkexec(content)
            if not success:
                GLib.idle_add(lambda: self._show_toast(f"Failed: {message}", 5))
                return False

            # If any swap is in use, don't restart service
            if swap_in_use:
                GLib.idle_add(on_complete, True, True)
                return False

            # No swap in use - restart service to apply immediately
            success2, message2 = enable_systemd_swap()
            if not success2:
                GLib.idle_add(
                    lambda: self._show_toast(f"Config saved but restart failed: {message2}", 5)
                )
                return False

            GLib.idle_add(on_complete, True, False)
            return False

        GLib.timeout_add(100, apply_async)

    def apply_config(self) -> None:
        """Apply current view configuration."""
        if self._unified_view:
            config = self._unified_view.get_config()
            self._apply_config(config)

    def refresh(self) -> None:
        """Refresh data from system."""
        self._config_service.load()
        if self._unified_view:
            self._unified_view._update_swap_status()
        self._show_toast("Refreshed", 1)

    def restore_defaults(self) -> None:
        """Restore default settings."""
        if self._unified_view:
            self._unified_view.restore_defaults()
            self._show_toast("Settings restored to defaults")

    def _on_apply_clicked(self, _button: Gtk.Button) -> None:
        """Handle Apply button click from headerbar."""
        self.apply_config()

    def _create_about_section(self) -> Gio.Menu:
        """Create the about section for the menu."""
        section = Gio.Menu()
        section.append("About", "app.about")
        section.append("Quit", "app.quit")
        return section
