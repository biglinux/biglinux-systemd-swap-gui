#!/usr/bin/env python3
"""
Welcome dialog for BigLinux Swap Manager.

Redesigned to match Big Audio Converter style (Adw.Dialog, 2-column layout).
"""

from __future__ import annotations

import json
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from biglinux_swap.config import USER_CONFIG_DIR
from biglinux_swap.i18n import _

logger = logging.getLogger(__name__)

_WELCOME_SEEN_FILE = USER_CONFIG_DIR / "welcome_seen.json"


class WelcomeDialog:
    """
    Welcome dialog shown on first run or via menu.
    Uses Adw.Dialog for a modern, adaptive layout.
    """

    def __init__(self, parent: Gtk.Window) -> None:
        self.parent = parent
        self.dialog = Adw.Dialog()
        self.show_switch: Gtk.Switch | None = None

        # Configure dialog title
        self.dialog.set_title(_("Welcome"))
        self.dialog.set_content_width(850)
        # Allow natural height adjustment

        self._setup_ui()

    def present(self) -> None:
        """Present the dialog attached to parent window."""
        if self.parent:
            self.dialog.present(self.parent)

    def close(self) -> None:
        """Close the dialog."""
        self.dialog.close()

    def _setup_ui(self) -> None:
        """Build the dialog UI."""

        # Main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)

        # --- Header with Icon and Title ---
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        header_box.set_halign(Gtk.Align.CENTER)

        # Icon from theme (now working due to application registration)
        icon_img = Gtk.Image.new_from_icon_name("biglinux-swap")
        icon_img.set_pixel_size(64)

        header_box.append(icon_img)

        title = Gtk.Label()
        title.set_markup(
            f"<span size='xx-large' weight='bold'>{_('Welcome to Swap Manager')}</span>"
        )
        header_box.append(title)
        content_box.append(header_box)

        # --- Features Columns ---
        columns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        columns_box.set_margin_top(18)
        columns_box.set_halign(Gtk.Align.CENTER)
        columns_box.set_hexpand(True)

        # Left Column
        left_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        left_column.set_hexpand(True)
        left_column.set_valign(Gtk.Align.START)  # Align to top

        features_left = [
            (
                "💾 " + _("What is Swap?"),
                _(
                    "Swap is like an extension of your computer's memory. "
                    "When RAM is full, less-used data moves to swap, preventing freezes."
                ),
            ),
            (
                "⚡ " + _("What is Zram?"),
                _(
                    "Zram creates a compressed block device in RAM. "
                    "It's faster than disk swap and perfect for systems with limited disk speed."
                ),
            ),
        ]

        for title, desc in features_left:
            left_column.append(self._create_feature_box(title, desc))

        columns_box.append(left_column)

        # Right Column
        right_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        right_column.set_hexpand(True)
        right_column.set_valign(Gtk.Align.START)

        features_right = [
            (
                "🔄 " + _("What is Zswap?"),
                _(
                    "Zswap captures swap attempts and compresses pages into a RAM cache pool "
                    "before they hit the disk, reducing I/O."
                ),
            ),
            (
                "🎯 " + _("Automatic Mode"),
                _(
                    "Recommended: Auto mode detects your hardware (RAM + Storage) "
                    "and applies the optimal configuration automatically."
                ),
            ),
        ]

        for title, desc in features_right:
            right_column.append(self._create_feature_box(title, desc))

        columns_box.append(right_column)
        content_box.append(columns_box)

        # --- Separator ---
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(12)
        content_box.append(separator)

        # --- Startup Switch ---
        switch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        switch_box.set_margin_top(12)

        switch_label = Gtk.Label(label=_("Show dialog on startup"))
        switch_label.set_xalign(0)
        switch_label.set_hexpand(True)
        switch_box.append(switch_label)

        self.show_switch = Gtk.Switch()
        self.show_switch.set_valign(Gtk.Align.CENTER)
        # Load state
        self.show_switch.set_active(WelcomeDialog.should_show_welcome())
        self.show_switch.connect("notify::active", self._on_switch_toggled)
        switch_box.append(self.show_switch)

        content_box.append(switch_box)

        # --- Close Button ---
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        button_box.set_margin_top(18)
        button_box.set_halign(Gtk.Align.CENTER)

        close_btn = Gtk.Button(label=_("Let's Start"))
        close_btn.add_css_class("suggested-action")
        close_btn.add_css_class("pill")
        close_btn.set_size_request(200, 45)
        close_btn.connect("clicked", lambda _b: self.close())

        button_box.append(close_btn)
        content_box.append(button_box)

        self.dialog.set_child(content_box)

    def _create_feature_box(self, title: str, description: str) -> Gtk.Box:
        """Create a custom feature box."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{title}</b>")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_wrap(True)
        title_label.add_css_class("heading")  # Standard style

        desc_label = Gtk.Label(label=description)
        desc_label.set_halign(Gtk.Align.START)
        desc_label.set_wrap(True)
        desc_label.set_xalign(0)
        desc_label.add_css_class("dim-label")
        desc_label.set_max_width_chars(35)  # Force wrapping for columns

        box.append(title_label)
        box.append(desc_label)
        return box

    def _on_switch_toggled(self, switch: Gtk.Switch, _pspec: object) -> None:
        _save_welcome_preference(switch.get_active())

    @staticmethod
    def should_show_welcome() -> bool:
        """Check if the welcome dialog should be shown."""
        if not _WELCOME_SEEN_FILE.exists():
            return True
        try:
            data = json.loads(_WELCOME_SEEN_FILE.read_text(encoding="utf-8"))
            return data.get("show_welcome_dialog", True)
        except (json.JSONDecodeError, OSError):
            return True


def _save_welcome_preference(show: bool) -> None:
    """Save whether the welcome dialog should appear on startup."""
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {"show_welcome_dialog": show}
        _WELCOME_SEEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error("Error saving welcome preference: %s", e)
