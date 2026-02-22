"""Pauskollen - Visual timer and pause exercises for children with ADHD/NPF."""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk, Gio
import gettext
import locale
import os
import math
import json
import time

__version__ = "0.1.0"

APP_ID = "se.danielnylander.pauskollen"
LOCALE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'share', 'locale')
if not os.path.isdir(LOCALE_DIR):
    LOCALE_DIR = "/usr/share/locale"

try:
    locale.bindtextdomain(APP_ID, LOCALE_DIR)
    gettext.bindtextdomain(APP_ID, LOCALE_DIR)
    gettext.textdomain(APP_ID)
except Exception:
    pass
_ = gettext.gettext


# Breathing exercises
EXERCISES = [
    {"name": N_("Deep Breathing"), "icon": "🌬️",
     "steps": [N_("Breathe in slowly... 1, 2, 3, 4"), N_("Hold... 1, 2, 3"), N_("Breathe out slowly... 1, 2, 3, 4, 5")],
     "durations": [4, 3, 5]},
    {"name": N_("Body Scan"), "icon": "🧘",
     "steps": [N_("Close your eyes"), N_("Feel your feet on the floor"), N_("Relax your legs"), N_("Relax your tummy"), N_("Relax your shoulders"), N_("Relax your face"), N_("Open your eyes")],
     "durations": [3, 4, 4, 4, 4, 4, 3]},
    {"name": N_("Counting"), "icon": "🔢",
     "steps": [N_("Count slowly to 10"), N_("Now count backwards from 10"), N_("Take a deep breath")],
     "durations": [10, 10, 4]},
    {"name": N_("Stretching"), "icon": "🤸",
     "steps": [N_("Stretch your arms up high"), N_("Touch your toes"), N_("Roll your shoulders"), N_("Shake your hands"), N_("Stand still and breathe")],
     "durations": [5, 5, 5, 5, 4]},
    {"name": N_("5-4-3-2-1 Grounding"), "icon": "👁️",
     "steps": [N_("Name 5 things you can SEE"), N_("Name 4 things you can TOUCH"), N_("Name 3 things you can HEAR"), N_("Name 2 things you can SMELL"), N_("Name 1 thing you can TASTE")],
     "durations": [8, 8, 8, 6, 5]},
]

def N_(s): return s


class TimerWidget(Gtk.DrawingArea):
    """Circular countdown timer."""

    def __init__(self):
        super().__init__()
        self.total_seconds = 0
        self.remaining_seconds = 0
        self.set_content_width(200)
        self.set_content_height(200)
        self.set_draw_func(self._draw)

    def _draw(self, area, cr, width, height):
        cx, cy = width / 2, height / 2
        radius = min(width, height) / 2 - 10

        # Background circle
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.2)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.fill()

        # Progress arc
        if self.total_seconds > 0:
            fraction = self.remaining_seconds / self.total_seconds
            cr.set_source_rgba(0.4, 0.2, 0.8, 0.8)
            cr.set_line_width(8)
            start_angle = -math.pi / 2
            end_angle = start_angle + 2 * math.pi * fraction
            cr.arc(cx, cy, radius - 4, start_angle, end_angle)
            cr.stroke()

        # Time text
        minutes = int(self.remaining_seconds) // 60
        seconds = int(self.remaining_seconds) % 60
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(36)
        text = f"{minutes}:{seconds:02d}"
        extents = cr.text_extents(text)
        cr.move_to(cx - extents.width / 2, cy + extents.height / 2)
        cr.show_text(text)

    def set_time(self, total, remaining):
        self.total_seconds = total
        self.remaining_seconds = remaining
        self.queue_draw()


class PauskollenWindow(Adw.ApplicationWindow):
    """Main window."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Pauskollen"))
        self.set_default_size(500, 600)

        self._timer_id = None
        self._remaining = 0
        self._total = 0
        self._exercise_step = 0
        self._current_exercise = None
        self._custom_minutes = 5

        # Header bar
        header = Adw.HeaderBar()
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu = Gio.Menu()
        menu.append(_("About"), "app.about")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        # Main content
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # === Timer page ===
        timer_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        timer_page.set_margin_top(24)
        timer_page.set_margin_bottom(24)
        timer_page.set_margin_start(24)
        timer_page.set_margin_end(24)

        # Timer display
        self._timer_widget = TimerWidget()
        timer_page.append(self._timer_widget)

        # Status label
        self._status_label = Gtk.Label(label=_("Choose a timer or exercise"))
        self._status_label.add_css_class("title-3")
        timer_page.append(self._status_label)

        # Timer presets
        presets_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        presets_box.set_halign(Gtk.Align.CENTER)
        for mins in [1, 2, 5, 10, 15]:
            btn = Gtk.Button(label=f"{mins} min")
            btn.add_css_class("pill")
            btn.connect("clicked", self._on_preset_clicked, mins)
            presets_box.append(btn)
        timer_page.append(presets_box)

        # Control buttons
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        ctrl_box.set_halign(Gtk.Align.CENTER)

        self._start_btn = Gtk.Button(label=_("Start"))
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.add_css_class("pill")
        self._start_btn.connect("clicked", self._on_start)
        ctrl_box.append(self._start_btn)

        self._stop_btn = Gtk.Button(label=_("Stop"))
        self._stop_btn.add_css_class("destructive-action")
        self._stop_btn.add_css_class("pill")
        self._stop_btn.set_sensitive(False)
        self._stop_btn.connect("clicked", self._on_stop)
        ctrl_box.append(self._stop_btn)

        self._reset_btn = Gtk.Button(label=_("Reset"))
        self._reset_btn.add_css_class("pill")
        self._reset_btn.connect("clicked", self._on_reset)
        ctrl_box.append(self._reset_btn)

        timer_page.append(ctrl_box)

        self._stack.add_titled(timer_page, "timer", _("Timer"))

        # === Exercises page ===
        exercises_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        exercises_page.set_margin_top(16)
        exercises_page.set_margin_bottom(16)
        exercises_page.set_margin_start(16)
        exercises_page.set_margin_end(16)

        ex_label = Gtk.Label(label=_("Pause Exercises"))
        ex_label.add_css_class("title-2")
        exercises_page.append(ex_label)

        exercises_scroll = Gtk.ScrolledWindow()
        exercises_scroll.set_vexpand(True)
        ex_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        for i, ex in enumerate(EXERCISES):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_margin_start(8)
            row.set_margin_end(8)
            row.set_margin_top(4)
            row.set_margin_bottom(4)

            icon = Gtk.Label(label=ex["icon"])
            icon.add_css_class("title-1")
            row.append(icon)

            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info.set_hexpand(True)
            name = Gtk.Label(label=_(ex["name"]), xalign=0)
            name.add_css_class("title-4")
            info.append(name)

            total_time = sum(ex["durations"])
            time_label = Gtk.Label(label=_("%d seconds") % total_time, xalign=0)
            time_label.add_css_class("dim-label")
            info.append(time_label)
            row.append(info)

            btn = Gtk.Button(label=_("Start"))
            btn.add_css_class("suggested-action")
            btn.add_css_class("pill")
            btn.connect("clicked", self._on_exercise_start, i)
            row.append(btn)

            ex_list.append(row)

        exercises_scroll.set_child(ex_list)
        exercises_page.append(exercises_scroll)

        # Exercise progress
        self._exercise_label = Gtk.Label(label="")
        self._exercise_label.add_css_class("title-3")
        self._exercise_label.set_wrap(True)
        self._exercise_label.set_visible(False)
        exercises_page.append(self._exercise_label)

        self._exercise_progress = Gtk.ProgressBar()
        self._exercise_progress.set_visible(False)
        exercises_page.append(self._exercise_progress)

        self._stack.add_titled(exercises_page, "exercises", _("Exercises"))

        # View switcher in header
        switcher = Adw.ViewSwitcher()
        switcher.set_stack(self._stack)
        header.set_title_widget(switcher)

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)
        main_box.append(self._stack)
        self.set_content(main_box)

        # Keyboard shortcuts
        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(ctrl)

        # Init timer display
        self._timer_widget.set_time(0, 0)

    def _on_key_pressed(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_space:
            if self._timer_id:
                self._on_stop(None)
            else:
                self._on_start(None)
            return True
        if keyval == Gdk.KEY_Escape:
            self._on_reset(None)
            return True
        return False

    def _on_preset_clicked(self, btn, minutes):
        self._on_stop(None)
        self._total = minutes * 60
        self._remaining = self._total
        self._timer_widget.set_time(self._total, self._remaining)
        self._status_label.set_text(_("%d minute pause") % minutes)

    def _on_start(self, btn):
        if self._remaining <= 0:
            self._remaining = self._custom_minutes * 60
            self._total = self._remaining
        if self._timer_id:
            return
        self._timer_id = GLib.timeout_add(1000, self._tick)
        self._start_btn.set_sensitive(False)
        self._stop_btn.set_sensitive(True)
        self._status_label.set_text(_("Running..."))

    def _on_stop(self, btn):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self._start_btn.set_sensitive(True)
        self._stop_btn.set_sensitive(False)
        self._status_label.set_text(_("Paused"))

    def _on_reset(self, btn):
        self._on_stop(None)
        self._remaining = 0
        self._total = 0
        self._timer_widget.set_time(0, 0)
        self._status_label.set_text(_("Choose a timer or exercise"))
        self._current_exercise = None

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
            self._timer_widget.set_time(self._total, self._remaining)
            
            # Update exercise step if running
            if self._current_exercise is not None:
                self._update_exercise_step()
            
            return True
        else:
            self._timer_id = None
            self._status_label.set_text(_("Time's up! 🎉"))
            self._start_btn.set_sensitive(True)
            self._stop_btn.set_sensitive(False)
            self._exercise_label.set_visible(False)
            self._exercise_progress.set_visible(False)
            self._current_exercise = None
            return False

    def _on_exercise_start(self, btn, index):
        self._on_stop(None)
        ex = EXERCISES[index]
        self._current_exercise = ex
        self._exercise_step = 0
        self._total = sum(ex["durations"])
        self._remaining = self._total
        self._timer_widget.set_time(self._total, self._remaining)
        
        self._exercise_label.set_text(_(ex["steps"][0]))
        self._exercise_label.set_visible(True)
        self._exercise_progress.set_fraction(0)
        self._exercise_progress.set_visible(True)
        
        self._stack.set_visible_child_name("timer")
        self._status_label.set_text(_(ex["name"]))
        self._on_start(None)

    def _update_exercise_step(self):
        if self._current_exercise is None:
            return
        ex = self._current_exercise
        elapsed = self._total - self._remaining
        cumulative = 0
        for i, dur in enumerate(ex["durations"]):
            cumulative += dur
            if elapsed < cumulative:
                if i != self._exercise_step:
                    self._exercise_step = i
                    self._exercise_label.set_text(_(ex["steps"][i]))
                self._exercise_progress.set_fraction(elapsed / self._total)
                return
        self._exercise_progress.set_fraction(1.0)


class PauskollenApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.connect("activate", self._on_activate)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

    def _on_activate(self, app):
        win = PauskollenWindow(application=app)
        win.present()

    def _on_about(self, action, param):
        about = Adw.AboutDialog(
            application_name=_("Pauskollen"),
            application_icon=APP_ID,
            version=__version__,
            developer_name="Daniel Nylander",
            website="https://github.com/yeager/pauskollen",
            issue_url="https://github.com/yeager/pauskollen/issues",
            license_type=Gtk.License.GPL_3_0,
            comments=_("Visual timer and regulation exercises for children with ADHD/NPF"),
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
        )
        about.present(self.get_active_window())


def main():
    app = PauskollenApp()
    app.run()


if __name__ == "__main__":
    main()
