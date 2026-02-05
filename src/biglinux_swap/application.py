#!/usr/bin/env python3
"""
Application class for BigLinux Swap Manager.

Adwaita Application with lazy service initialization.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from biglinux_swap.config import APP_ICON, APP_ID, APP_NAME, APP_VERSION
from biglinux_swap.i18n import _
from biglinux_swap.services import ConfigService, MeminfoService, SwapService
from biglinux_swap.window import SwapWindow

if TYPE_CHECKING:
    pass

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
        action: Gio.SimpleAction,  # noqa: ARG002
        param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle quit action."""
        self.quit()

    def _on_about(
        self,
        action: Gio.SimpleAction,  # noqa: ARG002
        param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Show about dialog."""
        about = Adw.AboutDialog.new()
        about.set_application_name(APP_NAME)
        about.set_version(APP_VERSION)
        about.set_developer_name("BigLinux")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments("Configure swap settings for optimal performance")
        about.set_website("https://www.biglinux.com.br")
        about.set_issue_url(
            "https://github.com/biglinux/biglinux-systemd-swap-gui/issues"
        )
        about.set_application_icon(APP_ICON)

        about.set_developers(
            [
                "BigLinux Team",
            ]
        )

        about.set_copyright("© 2025 BigLinux")

        if self._window:
            about.present(self._window)

    def _on_apply_config(
        self,
        action: Gio.SimpleAction,  # noqa: ARG002
        param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle apply config action."""
        if self._window:
            self._window.apply_config()

    def _on_refresh(
        self,
        action: Gio.SimpleAction,  # noqa: ARG002
        param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle refresh action."""
        if self._window:
            self._window.refresh()

    def _on_restore_defaults(
        self,
        action: Gio.SimpleAction,  # noqa: ARG002
        param: GLib.Variant | None,  # noqa: ARG002
    ) -> None:
        """Handle restore defaults action."""
        if self._window:
            self._window.restore_defaults()


# Need to import Gtk for License enum
from gi.repository import Gtk  # noqa: E402
