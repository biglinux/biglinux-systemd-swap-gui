#!/usr/bin/env python3
"""
Application class for BigLinux Swap Manager.

Adwaita Application with lazy service initialization.
"""

from __future__ import annotations

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from biglinux_swap.config import APP_ID, APP_NAME, APP_VERSION
from biglinux_swap.i18n import _
from biglinux_swap.services import ConfigService, MeminfoService, SwapService
from biglinux_swap.ui.welcome_dialog import WelcomeDialog
from biglinux_swap.window import SwapWindow


logger = logging.getLogger(__name__)


class SwapApplication(Adw.Application):
    """
    Main application class for BigLinux Swap Manager.

    Implements lazy service initialization and manages
    the application lifecycle.
    """

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        # Services (lazy-initialized)
        self._config_service: ConfigService | None = None
        self._meminfo_service: MeminfoService | None = None
        self._swap_service: SwapService | None = None

        # Window reference
        self._window: SwapWindow | None = None

    @property
    def config_service(self) -> ConfigService:
        """Lazy-initialized config service."""
        if self._config_service is None:
            self._config_service = ConfigService()
        return self._config_service

    @property
    def meminfo_service(self) -> MeminfoService:
        """Lazy-initialized meminfo service."""
        if self._meminfo_service is None:
            self._meminfo_service = MeminfoService()
        return self._meminfo_service

    @property
    def swap_service(self) -> SwapService:
        """Lazy-initialized swap service."""
        if self._swap_service is None:
            self._swap_service = SwapService()
        return self._swap_service

    def do_startup(self) -> None:
        """Handle application startup."""
        Adw.Application.do_startup(self)

        # Register local icons if available (for development/local execution)
        project_root = Path(__file__).resolve().parent.parent.parent
        icon_path = project_root / "usr" / "share" / "icons"
        if icon_path.exists():
            display = Gdk.Display.get_default()
            if display:
                theme = Gtk.IconTheme.get_for_display(display)
                theme.add_search_path(str(icon_path))

        # Set up application actions
        self._setup_actions()

        logger.debug("Application started")

    def _setup_actions(self) -> None:
        """Set up application actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Apply action
        apply_action = Gio.SimpleAction.new("apply-config", None)
        apply_action.connect("activate", self._on_apply_config)
        self.add_action(apply_action)

        # Refresh action
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self._on_refresh)
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])

        # Welcome action
        welcome_action = Gio.SimpleAction.new("welcome", None)
        welcome_action.connect("activate", self._on_welcome)
        self.add_action(welcome_action)

        # Restore defaults action
        restore_defaults_action = Gio.SimpleAction.new("restore_defaults", None)
        restore_defaults_action.connect("activate", self._on_restore_defaults)
        self.add_action(restore_defaults_action)

    def do_activate(self) -> None:
        """Handle application activation."""
        if not self._window:
            self._window = SwapWindow(
                application=self,
                config_service=self.config_service,
                meminfo_service=self.meminfo_service,
                swap_service=self.swap_service,
            )
            # Show welcome dialog on first run
            if WelcomeDialog.should_show_welcome():
                welcome = WelcomeDialog(self._window)
                welcome.present()

        self._window.present()

    def do_shutdown(self) -> None:
        """Handle application shutdown."""
        # Stop meminfo monitoring
        if self._meminfo_service:
            self._meminfo_service.stop_monitoring()

        logger.debug("Application shutdown")
        Adw.Application.do_shutdown(self)

    def _on_quit(
        self,
        _action: Gio.SimpleAction,  # noqa: ARG002
        _param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle quit action."""
        self.quit()

    def _on_about(
        self,
        _action: Gio.SimpleAction,  # noqa: ARG002
        _param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Show about dialog."""
        about = Adw.AboutDialog.new()
        about.set_application_name(APP_NAME)
        about.set_version(APP_VERSION)
        about.set_developer_name("BigLinux")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments(_("Configure swap settings for optimal performance"))
        about.set_website("https://www.biglinux.com.br")
        about.set_issue_url(
            "https://github.com/biglinux/biglinux-systemd-swap-gui/issues"
        )
        about.set_application_icon("biglinux-swap")

        about.set_developers(
            [
                "BigLinux Team",
            ]
        )

        about.set_copyright("© 2025-2026 BigLinux")

        if self._window:
            about.present(self._window)

    def _on_apply_config(
        self,
        _action: Gio.SimpleAction,  # noqa: ARG002
        _param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle apply config action."""
        if self._window:
            self._window.apply_config()

    def _on_refresh(
        self,
        _action: Gio.SimpleAction,  # noqa: ARG002
        _param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle refresh action."""
        if self._window:
            self._window.refresh()

    def _on_restore_defaults(
        self,
        _action: Gio.SimpleAction,  # noqa: ARG002
        _param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle restore defaults action."""
        if self._window:
            self._window.restore_defaults()

    def _on_welcome(
        self,
        _action: Gio.SimpleAction,  # noqa: ARG002
        _param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Show welcome dialog."""
        if self._window:
            welcome = WelcomeDialog(self._window)
            welcome.present()
