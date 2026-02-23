#!/usr/bin/env python3
"""
Memory chart widget using Cairo drawing.

Displays real-time memory and swap usage in a line chart.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from biglinux_swap.config import CHART_MAX_HISTORY
from biglinux_swap.i18n import _

# Import cairo for type hints
try:
    import cairo
except ImportError:
    cairo = None  # type: ignore[assignment]


@dataclass
class MemoryDataPoint:
    """Single data point for memory chart."""

    mem_used_percent: float
    swap_used_percent: float
    zswap_percent: float = 0.0  # Zswap as percentage of total RAM
    # Absolute values for tooltip
    mem_text: str = ""
    swap_text: str = ""
    zswap_text: str = ""


class MemoryChartWidget(Gtk.DrawingArea):
    """
    Custom widget to display memory and swap usage over time.

    Shows a line chart with:
    - Green line: RAM usage percentage
    - Blue line: Swap usage percentage
    - Grid background with percentage labels
    - Hover tooltip showing values at mouse position
    """

    def __init__(self) -> None:
        """Initialize the memory chart widget."""
        super().__init__()

        self._history: deque[MemoryDataPoint] = deque(maxlen=CHART_MAX_HISTORY)

        # Current values for display
        self._mem_used_text = ""
        self._swap_used_text = ""
        self._zswap_text = ""

        # Hover state
        self._hover_x: float | None = None
        self._hover_index: int | None = None

        # Sizing
        self.set_size_request(300, 150)
        self.set_vexpand(False)
        self.set_hexpand(True)

        # Accessibility
        self.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [_("Memory and swap usage chart")],
        )

        # Connect draw signal
        self.set_draw_func(self._on_draw)

        # Mouse tracking for hover
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("motion", self._on_motion)
        motion_controller.connect("leave", self._on_leave)
        self.add_controller(motion_controller)

    def add_data_point(
        self,
        mem_used_percent: float,
        swap_used_percent: float,
        mem_used_text: str = "",
        swap_used_text: str = "",
        zswap_percent: float = 0.0,
        zswap_text: str = "",
    ) -> None:
        """
        Add a new data point and trigger redraw.

        Args:
            mem_used_percent: RAM usage percentage (0-100)
            swap_used_percent: Swap usage percentage (0-100)
            mem_used_text: Formatted text for RAM usage
            swap_used_text: Formatted text for swap usage
            zswap_percent: Zswap pool as percentage of RAM (0-100)
            zswap_text: Formatted text for zswap pool size
        """
        point = MemoryDataPoint(
            mem_used_percent=min(100.0, max(0.0, mem_used_percent)),
            swap_used_percent=min(100.0, max(0.0, swap_used_percent)),
            zswap_percent=min(100.0, max(0.0, zswap_percent)),
            mem_text=mem_used_text,
            swap_text=swap_used_text,
            zswap_text=zswap_text,
        )
        self._history.append(point)
        self._mem_used_text = mem_used_text
        self._swap_used_text = swap_used_text
        self._zswap_text = zswap_text
        self.queue_draw()

    def clear(self) -> None:
        """Clear all data points."""
        self._history.clear()
        self._mem_used_text = ""
        self._swap_used_text = ""
        self._zswap_text = ""
        self.queue_draw()

    def _on_motion(
        self,
        controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
    ) -> None:
        """Handle mouse motion for hover tooltip."""
        self._hover_x = x
        old_index = self._hover_index
        self._update_hover_index()
        if self._hover_index != old_index:
            self.queue_draw()

    def _on_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        """Handle mouse leaving the widget."""
        self._hover_x = None
        self._hover_index = None
        self.queue_draw()

    def _update_hover_index(self) -> None:
        """Calculate which data point the mouse is hovering over."""
        if self._hover_x is None or not self._history:
            self._hover_index = None
            return

        # Get widget dimensions
        width = self.get_width()
        margin_left = 45
        margin_right = 10
        chart_width = width - margin_left - margin_right

        if chart_width <= 0:
            self._hover_index = None
            return

        # Check if mouse is within chart area
        if self._hover_x < margin_left or self._hover_x > width - margin_right:
            self._hover_index = None
            return

        # Calculate which point the mouse is near
        num_points = len(self._history)
        x_step = chart_width / max(CHART_MAX_HISTORY - 1, 1)
        start_x = margin_left + chart_width - (num_points - 1) * x_step

        # Find closest point
        relative_x = self._hover_x - start_x
        index = round(relative_x / x_step) if x_step > 0 else 0
        index = max(0, min(num_points - 1, index))
        self._hover_index = index

    def _on_draw(
        self,
        _area: Gtk.DrawingArea,
        cr: cairo.Context,
        width: int,
        height: int,
    ) -> None:
        """Draw the chart using Cairo."""
        # Theme detection
        style_manager = Adw.StyleManager.get_default()
        is_dark = style_manager.get_dark()

        if is_dark:
            bg_color = (0.0, 0.0, 0.0, 1.0)
            grid_color = (0.3, 0.3, 0.3, 0.5)
            text_color = (0.9, 0.9, 0.9, 1.0)
        else:
            bg_color = (0.12, 0.12, 0.12, 1.0)
            grid_color = (0.3, 0.3, 0.3, 0.5)
            text_color = (0.9, 0.9, 0.9, 1.0)

        # Convert history to list once for performance
        history_list = list(self._history)

        # Rounded rectangle background
        radius = 12.0
        self._draw_rounded_rect(cr, 0, 0, width, height, radius)
        cr.set_source_rgba(*bg_color)
        cr.fill()

        # Clip to rounded rectangle so all drawing respects corners
        self._draw_rounded_rect(cr, 0, 0, width, height, radius)
        cr.clip()

        # Margins
        margin_left = 45
        margin_right = 10
        margin_top = 15
        margin_bottom = 30

        chart_width = width - margin_left - margin_right
        chart_height = height - margin_top - margin_bottom

        if chart_width <= 0 or chart_height <= 0:
            return

        # Draw grid lines
        cr.set_source_rgba(*grid_color)
        cr.set_line_width(1)

        for percent in [25, 50, 75, 100]:
            y = margin_top + chart_height * (1 - percent / 100)
            cr.move_to(margin_left, y)
            cr.line_to(margin_left + chart_width, y)
            cr.stroke()

            # Label
            cr.set_source_rgba(0.6, 0.6, 0.6, 1)
            cr.select_font_face(
                "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            cr.set_font_size(10)
            cr.move_to(5, y + 4)
            cr.show_text(f"{percent}%")

        # Draw 0% line
        y_zero = margin_top + chart_height
        cr.set_source_rgba(*grid_color)
        cr.move_to(margin_left, y_zero)
        cr.line_to(margin_left + chart_width, y_zero)
        cr.stroke()

        cr.set_source_rgba(0.6, 0.6, 0.6, 1)
        cr.move_to(5, y_zero + 4)
        cr.show_text("0%")

        if not self._history:
            # No data - show placeholder text
            cr.set_source_rgba(0.5, 0.5, 0.5, 1)
            cr.set_font_size(14)
            text = _("Collecting data...")
            extents = cr.text_extents(text)
            cr.move_to(
                margin_left + (chart_width - extents.width) / 2,
                margin_top + chart_height / 2,
            )
            cr.show_text(text)
            return

        # Check if we have swap data (not just zswap, but any swap configuration)
        # If the last point has swap text other than empty/"N/A", we show 3-line layout
        last_point = history_list[-1] if history_list else None
        has_swap = last_point and last_point.swap_text and last_point.swap_text != "N/A"

        # Draw RAM line (green)
        self._draw_line(
            cr,
            chart_width,
            chart_height,
            margin_left,
            margin_top,
            [p.mem_used_percent for p in self._history],
            (0.3, 0.85, 0.4, 1.0),  # Green
        )

        # Draw Swap in RAM line (orange) - always draw when swap exists
        if has_swap:
            self._draw_line(
                cr,
                chart_width,
                chart_height,
                margin_left,
                margin_top,
                [p.zswap_percent for p in self._history],
                (0.95, 0.6, 0.2, 1.0),  # Orange
            )

        # Draw Swap line (blue)
        self._draw_line(
            cr,
            chart_width,
            chart_height,
            margin_left,
            margin_top,
            [p.swap_used_percent for p in self._history],
            (0.3, 0.5, 0.95, 1.0),  # Blue
        )

        # Legend at bottom
        legend_y = height - 12
        self._draw_legend(cr, chart_width, margin_left, legend_y, text_color, has_swap)

        # Draw hover indicator and tooltip
        if self._hover_index is not None and 0 <= self._hover_index < len(
            self._history
        ):
            self._draw_hover_tooltip(
                cr,
                width,
                chart_width,
                chart_height,
                margin_left,
                margin_right,
                margin_top,
                history_list,
            )

    def _draw_legend(
        self,
        cr: cairo.Context,
        chart_width: float,
        margin_left: float,
        legend_y: float,
        text_color: tuple[float, float, float, float],
        has_swap: bool,
    ) -> None:
        """Draw the color legend at the bottom of the chart."""
        if has_swap:
            legend_spacing = chart_width / 3

            cr.set_source_rgba(0.3, 0.85, 0.4, 1.0)
            cr.rectangle(margin_left + 5, legend_y - 8, 12, 8)
            cr.fill()
            cr.set_source_rgba(*text_color)
            cr.set_font_size(10)
            cr.move_to(margin_left + 22, legend_y)
            ram_text = (
                _("RAM: {}").format(self._mem_used_text)
                if self._mem_used_text
                else _("RAM")
            )
            cr.show_text(ram_text)

            zswap_x = margin_left + legend_spacing
            cr.set_source_rgba(0.95, 0.6, 0.2, 1.0)
            cr.rectangle(zswap_x, legend_y - 8, 12, 8)
            cr.fill()
            cr.set_source_rgba(*text_color)
            cr.move_to(zswap_x + 17, legend_y)
            zswap_legend = (
                _("Swap RAM: {}").format(self._zswap_text)
                if self._zswap_text
                else _("Swap RAM")
            )
            cr.show_text(zswap_legend)

            swap_x = margin_left + 2 * legend_spacing
            cr.set_source_rgba(0.3, 0.5, 0.95, 1.0)
            cr.rectangle(swap_x, legend_y - 8, 12, 8)
            cr.fill()
            cr.set_source_rgba(*text_color)
            cr.move_to(swap_x + 17, legend_y)
            swap_text = (
                _("Swap Disk: {}").format(self._swap_used_text)
                if self._swap_used_text
                else _("Swap Disk")
            )
            cr.show_text(swap_text)
        else:
            cr.set_source_rgba(0.3, 0.85, 0.4, 1.0)
            cr.rectangle(margin_left + 5, legend_y - 8, 12, 8)
            cr.fill()
            cr.set_source_rgba(*text_color)
            cr.set_font_size(11)
            cr.move_to(margin_left + 22, legend_y)
            ram_text = (
                _("RAM: {}").format(self._mem_used_text)
                if self._mem_used_text
                else _("RAM")
            )
            cr.show_text(ram_text)

            swap_x = margin_left + chart_width / 2
            cr.set_source_rgba(0.3, 0.5, 0.95, 1.0)
            cr.rectangle(swap_x, legend_y - 8, 12, 8)
            cr.fill()
            cr.set_source_rgba(*text_color)
            cr.move_to(swap_x + 17, legend_y)
            swap_text = (
                _("Swap: {}").format(self._swap_used_text)
                if self._swap_used_text
                else _("Swap")
            )
            cr.show_text(swap_text)

    def _draw_hover_tooltip(
        self,
        cr: cairo.Context,
        width: float,
        chart_width: float,
        chart_height: float,
        margin_left: float,
        margin_right: float,
        margin_top: float,
        history_list: list[MemoryDataPoint],
    ) -> None:
        """Draw hover indicator lines, dots, and tooltip box."""
        point = history_list[self._hover_index]
        num_points = len(self._history)
        x_step = chart_width / max(CHART_MAX_HISTORY - 1, 1)
        start_x = margin_left + chart_width - (num_points - 1) * x_step
        hover_x = start_x + self._hover_index * x_step

        # Vertical line
        cr.set_source_rgba(1, 1, 1, 0.3)
        cr.set_line_width(1)
        cr.move_to(hover_x, margin_top)
        cr.line_to(hover_x, margin_top + chart_height)
        cr.stroke()

        # RAM point
        ram_y = margin_top + chart_height * (1 - point.mem_used_percent / 100)
        cr.set_source_rgba(0.3, 0.85, 0.4, 1.0)
        cr.arc(hover_x, ram_y, 4, 0, 2 * math.pi)
        cr.fill()

        # Zswap point
        if point.zswap_percent > 0:
            zswap_y = margin_top + chart_height * (1 - point.zswap_percent / 100)
            cr.set_source_rgba(0.95, 0.6, 0.2, 1.0)
            cr.arc(hover_x, zswap_y, 4, 0, 2 * math.pi)
            cr.fill()

        # Swap point
        swap_y = margin_top + chart_height * (1 - point.swap_used_percent / 100)
        cr.set_source_rgba(0.3, 0.5, 0.95, 1.0)
        cr.arc(hover_x, swap_y, 4, 0, 2 * math.pi)
        cr.fill()

        seconds_ago = num_points - self._hover_index - 1
        time_text = _("{}s ago").format(seconds_ago) if seconds_ago > 0 else _("now")
        has_swap_text = point.swap_text and point.swap_text != "N/A"
        if has_swap_text:
            zswap_display = point.zswap_text if point.zswap_text else "0 B"
            tooltip_text = _("[{}]  RAM: {}  Swap RAM: {}  Swap Disk: {}").format(
                time_text, point.mem_text, zswap_display, point.swap_text
            )
        elif point.mem_text:
            tooltip_text = _("[{}]  RAM: {}").format(time_text, point.mem_text)
        else:
            tooltip_text = _("[{}]  RAM: {}%").format(
                time_text, f"{point.mem_used_percent:.1f}"
            )

        cr.set_font_size(10)
        extents = cr.text_extents(tooltip_text)
        tooltip_x = width - margin_right - extents.width - 10
        tooltip_y = margin_top + 5

        cr.set_source_rgba(0.15, 0.15, 0.15, 0.95)
        cr.rectangle(
            tooltip_x - 5, tooltip_y - 3, extents.width + 10, extents.height + 8
        )
        cr.fill()

        cr.set_source_rgba(0.4, 0.4, 0.4, 1)
        cr.set_line_width(1)
        cr.rectangle(
            tooltip_x - 5, tooltip_y - 3, extents.width + 10, extents.height + 8
        )
        cr.stroke()

        cr.set_source_rgba(0.95, 0.95, 0.95, 1)
        cr.move_to(tooltip_x, tooltip_y + extents.height)
        cr.show_text(tooltip_text)

    @staticmethod
    def _draw_rounded_rect(
        cr: cairo.Context,
        x: float,
        y: float,
        w: float,
        h: float,
        r: float,
    ) -> None:
        """Draw a rounded rectangle path."""
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _draw_line(
        self,
        cr: cairo.Context,
        chart_width: float,
        chart_height: float,
        margin_left: float,
        margin_top: float,
        values: list[float],
        color: tuple[float, float, float, float],
    ) -> None:
        """
        Draw a line on the chart.

        Args:
            cr: Cairo context
            chart_width: Width of chart area
            chart_height: Height of chart area
            margin_left: Left margin
            margin_top: Top margin
            values: List of values (0-100)
            color: RGBA color tuple
        """
        if not values:
            return

        cr.set_source_rgba(*color)
        cr.set_line_width(2)

        num_points = len(values)
        x_step = chart_width / max(CHART_MAX_HISTORY - 1, 1)

        # Start from the right side
        start_x = margin_left + chart_width - (num_points - 1) * x_step

        for i, value in enumerate(values):
            x = start_x + i * x_step
            y = margin_top + chart_height * (1 - value / 100)

            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)

        cr.stroke()

        # Draw area fill with transparency
        cr.set_source_rgba(color[0], color[1], color[2], 0.15)

        # Start again for fill
        for i, value in enumerate(values):
            x = start_x + i * x_step
            y = margin_top + chart_height * (1 - value / 100)

            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)

        # Close path to bottom
        cr.line_to(start_x + (num_points - 1) * x_step, margin_top + chart_height)
        cr.line_to(start_x, margin_top + chart_height)
        cr.close_path()
        cr.fill()
