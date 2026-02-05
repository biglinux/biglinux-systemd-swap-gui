#!/usr/bin/env python3
"""
Reusable UI components for BigLinux Swap Manager.

Factory functions for creating consistent Adwaita widgets.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from biglinux_swap.i18n import _



def create_preferences_group(
    title: str,
    description: str | None = None,
) -> Adw.PreferencesGroup:
    """
    Create a preferences group with title and optional description.

    Args:
        title: Group title
        description: Optional description text

    Returns:
        Adw.PreferencesGroup: Configured preferences group
    """
    group = Adw.PreferencesGroup()
    group.set_title(title)

    if description:
        group.set_description(description)

    return group


def create_action_row(
    title: str,
    subtitle: str | None = None,
    icon_name: str | None = None,
) -> Adw.ActionRow:
    """
    Create a simple action row.

    Args:
        title: Row title
        subtitle: Optional subtitle
        icon_name: Optional icon name

    Returns:
        Adw.ActionRow: Configured action row
    """
    row = Adw.ActionRow()
    row.set_title(title)

    if subtitle:
        row.set_subtitle(subtitle)

    if icon_name:
        row.set_icon_name(icon_name)

    return row


def create_action_row_with_switch(
    title: str,
    subtitle: str | None = None,
    active: bool = False,
    on_toggled: Callable[[bool], None] | None = None,
) -> tuple[Adw.ActionRow, Gtk.Switch]:
    """
    Create an action row with a switch.

    Args:
        title: Row title
        subtitle: Optional subtitle
        active: Initial switch state
        on_toggled: Callback when switch is toggled

    Returns:
        tuple: (Adw.ActionRow, Gtk.Switch)
    """
    row = Adw.ActionRow()
    row.set_title(title)

    if subtitle:
        row.set_subtitle(subtitle)

    switch = Gtk.Switch()
    switch.set_active(active)
    switch.set_valign(Gtk.Align.CENTER)

    if on_toggled:
        switch.connect("notify::active", lambda s, _: on_toggled(s.get_active()))

    row.add_suffix(switch)
    row.set_activatable_widget(switch)

    return row, switch


def create_action_row_with_scale(
    title: str,
    subtitle: str | None = None,
    min_value: float = 0.0,
    max_value: float = 100.0,
    value: float = 50.0,
    step: float = 1.0,
    digits: int = 0,
    on_changed: Callable[[float], None] | None = None,
    marks: list[tuple[float, str]] | None = None,
    show_value: bool = True,
) -> tuple[Adw.ActionRow, Gtk.Scale]:
    """
    Create an action row with a horizontal scale slider.

    Args:
        title: Row title
        subtitle: Optional subtitle
        min_value: Minimum scale value
        max_value: Maximum scale value
        value: Initial value
        step: Step increment
        digits: Number of decimal digits
        on_changed: Callback when value changes
        marks: Optional list of (value, label) tuples for scale marks
        show_value: Whether to show the current value

    Returns:
        tuple: (Adw.ActionRow, Gtk.Scale)
    """
    row = Adw.ActionRow()
    row.set_title(title)

    if subtitle:
        row.set_subtitle(subtitle)

    # Create scale
    adjustment = Gtk.Adjustment(
        value=value,
        lower=min_value,
        upper=max_value,
        step_increment=step,
        page_increment=step * 10,
    )

    scale = Gtk.Scale(
        orientation=Gtk.Orientation.HORIZONTAL,
        adjustment=adjustment,
    )
    scale.set_digits(digits)
    scale.set_hexpand(True)
    scale.set_size_request(200, -1)
    scale.set_valign(Gtk.Align.CENTER)
    scale.set_draw_value(show_value)

    # Add marks if provided
    if marks:
        for mark_value, mark_label in marks:
            scale.add_mark(mark_value, Gtk.PositionType.BOTTOM, mark_label)

    if on_changed:

        def _on_value_changed(s: Gtk.Scale) -> None:
            on_changed(s.get_value())

        scale.connect("value-changed", _on_value_changed)

    row.add_suffix(scale)

    return row, scale


def create_combo_row(
    title: str,
    subtitle: str | None = None,
    options: list[str] | None = None,
    selected_index: int = 0,
    on_selected: Callable[[int], None] | None = None,
) -> Adw.ComboRow:
    """
    Create a combo row with dropdown options.

    Args:
        title: Row title
        subtitle: Optional subtitle
        options: List of option strings
        selected_index: Initially selected index
        on_selected: Callback when selection changes

    Returns:
        Adw.ComboRow: Configured combo row
    """
    row = Adw.ComboRow()
    row.set_title(title)

    if subtitle:
        row.set_subtitle(subtitle)

    if options:
        model = Gtk.StringList.new(options)
        row.set_model(model)
        row.set_selected(selected_index)

    if on_selected:
        row.connect("notify::selected", lambda r, _: on_selected(r.get_selected()))

    return row


def create_spin_row(
    title: str,
    subtitle: str | None = None,
    min_value: float = 0.0,
    max_value: float = 100.0,
    value: float = 50.0,
    step: float = 1.0,
    digits: int = 0,
    on_changed: Callable[[float], None] | None = None,
) -> Adw.SpinRow:
    """
    Create a spin row with numeric input.

    Args:
        title: Row title
        subtitle: Optional subtitle
        min_value: Minimum value
        max_value: Maximum value
        value: Initial value
        step: Step increment
        digits: Decimal digits
        on_changed: Callback when value changes

    Returns:
        Adw.SpinRow: Configured spin row
    """
    adjustment = Gtk.Adjustment(
        value=value,
        lower=min_value,
        upper=max_value,
        step_increment=step,
        page_increment=step * 10,
    )

    row = Adw.SpinRow()
    row.set_title(title)
    row.set_adjustment(adjustment)
    row.set_digits(digits)

    if subtitle:
        row.set_subtitle(subtitle)

    if on_changed:
        row.connect("notify::value", lambda r, _: on_changed(r.get_value()))

    return row


def create_entry_row(
    title: str,
    text: str = "",
    placeholder: str | None = None,
    on_changed: Callable[[str], None] | None = None,
) -> Adw.EntryRow:
    """
    Create an entry row for text input.

    Args:
        title: Row title
        text: Initial text
        placeholder: Placeholder text
        on_changed: Callback when text changes

    Returns:
        Adw.EntryRow: Configured entry row
    """
    row = Adw.EntryRow()
    row.set_title(title)
    row.set_text(text)

    if placeholder:
        row.set_input_hints(Gtk.InputHints.NO_EMOJI)

    if on_changed:
        row.connect("changed", lambda r: on_changed(r.get_text()))

    return row


def create_expander_row(
    title: str,
    subtitle: str | None = None,
    icon_name: str | None = None,
    expanded: bool = False,
) -> Adw.ExpanderRow:
    """
    Create an expander row.

    Args:
        title: Row title
        subtitle: Optional subtitle
        icon_name: Optional icon name
        expanded: Initially expanded state

    Returns:
        Adw.ExpanderRow: Configured expander row
    """
    row = Adw.ExpanderRow()
    row.set_title(title)
    row.set_expanded(expanded)
    row.set_enable_expansion(True)

    if subtitle:
        row.set_subtitle(subtitle)

    if icon_name:
        row.set_icon_name(icon_name)

    return row


def create_action_button(
    label: str,
    icon_name: str | None = None,
    style: str = "suggested-action",
    on_clicked: Callable[[], None] | None = None,
    tooltip: str | None = None,
) -> Gtk.Button:
    """
    Create an action button with consistent styling.

    Use this factory for primary action buttons in dialogs and views.

    Args:
        label: Button text
        icon_name: Optional icon name
        style: CSS class ('suggested-action', 'destructive-action', 'flat', 'pill')
        on_clicked: Click callback
        tooltip: Optional tooltip text

    Returns:
        Gtk.Button: Styled action button
    """
    if icon_name:
        button = Gtk.Button()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        box.append(icon)

        lbl = Gtk.Label(label=label)
        box.append(lbl)

        button.set_child(box)
    else:
        button = Gtk.Button(label=label)

    button.set_valign(Gtk.Align.CENTER)

    if style:
        button.add_css_class(style)

    if tooltip:
        button.set_tooltip_text(tooltip)

    if on_clicked:
        button.connect("clicked", lambda _: on_clicked())

    return button


def create_navigation_button(
    label: str,
    icon_name: str = "go-next-symbolic",
    subtitle: str | None = None,
    on_clicked: Callable[[], None] | None = None,
) -> Adw.ActionRow:
    """
    Create a navigation row that looks like a button.

    Use this factory for navigation to sub-views/pages.

    Args:
        label: Row title
        icon_name: Arrow icon (default: go-next-symbolic)
        subtitle: Optional description
        on_clicked: Navigation callback

    Returns:
        Adw.ActionRow: Clickable navigation row
    """
    row = Adw.ActionRow()
    row.set_title(label)
    row.set_activatable(True)

    if subtitle:
        row.set_subtitle(subtitle)

    # Add navigation arrow
    arrow = Gtk.Image.new_from_icon_name(icon_name)
    arrow.add_css_class("dim-label")
    row.add_suffix(arrow)

    if on_clicked:
        row.connect("activated", lambda _: on_clicked())

    return row


def create_status_row(
    label: str,
    value: str,
    icon_name: str | None = None,
) -> Adw.ActionRow:
    """
    Create a status display row (read-only).

    Args:
        label: Row title/label
        value: Value to display
        icon_name: Optional prefix icon

    Returns:
        Adw.ActionRow: Status row
    """
    row = Adw.ActionRow()
    row.set_title(label)
    row.set_activatable(False)

    if icon_name:
        row.set_icon_name(icon_name)

    # Value label
    value_label = Gtk.Label(label=value)
    value_label.add_css_class("dim-label")
    value_label.set_valign(Gtk.Align.CENTER)
    row.add_suffix(value_label)

    # Store reference for updates
    row._value_label = value_label  # type: ignore[attr-defined]

    return row


def update_status_row(row: Adw.ActionRow, value: str) -> None:
    """
    Update the value displayed in a status row.

    Args:
        row: Status row created with create_status_row
        value: New value to display
    """
    if hasattr(row, "_value_label"):
        row._value_label.set_text(value)  # type: ignore[attr-defined]


def create_card(
    child: Gtk.Widget,
    margin: int = 12,
) -> Gtk.Frame:
    """
    Create a card-style container.

    Args:
        child: Widget to contain
        margin: Internal margin

    Returns:
        Gtk.Frame: Card frame
    """
    frame = Gtk.Frame()
    frame.add_css_class("card")

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.set_margin_top(margin)
    box.set_margin_bottom(margin)
    box.set_margin_start(margin)
    box.set_margin_end(margin)
    box.append(child)

    frame.set_child(box)
    return frame


def create_status_indicator(
    active: bool = False,
    label: str | None = None,
) -> Gtk.Box:
    """
    Create a status indicator with colored dot.

    Args:
        active: Whether the indicator shows active state
        label: Optional label text

    Returns:
        Gtk.Box: Container with indicator
    """
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    box.set_valign(Gtk.Align.CENTER)

    # Colored dot
    dot = Gtk.Label(label="●")
    if active:
        dot.add_css_class("success")
    else:
        dot.add_css_class("dim-label")
    box.append(dot)

    if label:
        lbl = Gtk.Label(label=label)
        lbl.add_css_class("dim-label")
        box.append(lbl)

    return box


def create_level_bar(
    min_value: float = 0.0,
    max_value: float = 100.0,
    value: float = 0.0,
) -> Gtk.LevelBar:
    """
    Create a level bar for usage visualization.

    Args:
        min_value: Minimum value
        max_value: Maximum value
        value: Initial value

    Returns:
        Gtk.LevelBar: Configured level bar
    """
    level_bar = Gtk.LevelBar()
    level_bar.set_min_value(min_value)
    level_bar.set_max_value(max_value)
    level_bar.set_value(value)
    level_bar.set_hexpand(True)

    # Add standard offset marks
    level_bar.add_offset_value("low", max_value * 0.3)
    level_bar.add_offset_value("high", max_value * 0.7)
    level_bar.add_offset_value("full", max_value * 0.9)

    return level_bar


def create_radio_group(
    options: list[tuple[str, str]],
    selected_index: int = 0,
    on_selected: Callable[[int], None] | None = None,
) -> tuple[Gtk.Box, list[Gtk.CheckButton]]:
    """
    Create a group of radio buttons.

    Args:
        options: List of (label, description) tuples
        selected_index: Initially selected index
        on_selected: Callback when selection changes

    Returns:
        tuple: (Gtk.Box container, list of CheckButton widgets)
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    buttons: list[Gtk.CheckButton] = []
    first_button: Gtk.CheckButton | None = None

    for i, (label, description) in enumerate(options):
        radio = Gtk.CheckButton()
        radio.set_label(label)

        if first_button is None:
            first_button = radio
        else:
            radio.set_group(first_button)

        if i == selected_index:
            radio.set_active(True)

        if on_selected:
            radio.connect(
                "toggled",
                lambda btn, idx=i: on_selected(idx) if btn.get_active() else None,
            )

        row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row_box.append(radio)

        if description:
            desc_label = Gtk.Label(label=description)
            desc_label.add_css_class("dim-label")
            desc_label.add_css_class("caption")
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_margin_start(24)
            row_box.append(desc_label)

        box.append(row_box)
        buttons.append(radio)

    return box, buttons
