#!/usr/bin/env python3
import json
import os
import threading
import time
import uuid
from datetime import date

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango

APP_ID = "com.tmp.FocusFlow"
DATA_DIR = os.path.join(GLib.get_user_data_dir(), APP_ID)
DATA_FILE = os.path.join(DATA_DIR, "tasks.json")

CSS = """
window { background: @window_bg_color; }
.hero { background: linear-gradient(135deg, #3e257d, #684cc6); border-radius: 18px; }
.hero-title { color: white; font-size: 26px; font-weight: 800; }
.hero-subtitle { color: #e8e0ff; font-size: 14px; }
.hero-number { color: white; font-size: 36px; font-weight: 800; }
.section-title { font-size: 20px; font-weight: 800; }
.muted { color: alpha(@window_fg_color, .62); }
.task-row { padding: 9px 2px; }
.task-title { font-size: 15px; font-weight: 600; }
.task-done { text-decoration: line-through; color: alpha(@window_fg_color, .5); }
.timer-card { background: alpha(@card_bg_color, .72); border-radius: 18px; padding: 20px; }
.timer-value { font-size: 50px; font-weight: 800; font-feature-settings: 'tnum'; }
.pill { border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 700; }
"""


def load_tasks():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_tasks(tasks):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


class FocusFlowWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="FocusFlow")
        self.set_default_size(940, 680)
        self.set_size_request(520, 520)
        self.tasks = load_tasks()
        self.mode = "Focus"
        self.remaining = 25 * 60
        self.running = False
        self.timer_source = None
        self.session_minutes = 0
        self._build_ui()
        self._install_actions()
        self._refresh_tasks()
        self._update_timer()

    def _build_ui(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="FocusFlow"))
        menu = Gio.Menu()
        menu.append("Keyboard shortcuts", "win.shortcuts")
        menu.append("About FocusFlow", "app.about")
        header.set_menu_model(menu)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.append(scroll)
        self.toast_overlay.set_child(outer)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_top(26); content.set_margin_bottom(32)
        content.set_margin_start(32); content.set_margin_end(32)
        scroll.set_child(content)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        hero.add_css_class("hero"); hero.set_margin_bottom(2)
        hero.set_margin_top(0); hero.set_margin_start(0); hero.set_margin_end(0)
        hero.set_size_request(-1, 142)
        hero.set_margin_start(0); hero.set_margin_end(0)
        hero.set_valign(Gtk.Align.CENTER)
        hero_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hero_inner.set_margin_top(22); hero_inner.set_margin_bottom(22); hero_inner.set_margin_start(24)
        hero_title = Gtk.Label(label="Make space for what matters.", xalign=0)
        hero_title.add_css_class("hero-title")
        hero_sub = Gtk.Label(label="A gentle plan for a focused day.", xalign=0)
        hero_sub.add_css_class("hero-subtitle")
        hero_inner.append(hero_title); hero_inner.append(hero_sub)
        hero.append(hero_inner)
        hero_spacer = Gtk.Box(hexpand=True)
        hero.append(hero_spacer)
        hero_stat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hero_stat.set_margin_top(22); hero_stat.set_margin_bottom(22); hero_stat.set_margin_end(24)
        self.progress_number = Gtk.Label(label="0%", xalign=1)
        self.progress_number.add_css_class("hero-number")
        progress_caption = Gtk.Label(label="today", xalign=1)
        progress_caption.add_css_class("hero-subtitle")
        hero_stat.append(self.progress_number); hero_stat.append(progress_caption)
        hero.append(hero_stat)
        content.append(hero)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        top.set_homogeneous(False)
        content.append(top)

        tasks_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        tasks_column.set_hexpand(True)
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Today", xalign=0); title.add_css_class("section-title"); title.set_hexpand(True)
        self.task_count = Gtk.Label(label="0 tasks"); self.task_count.add_css_class("muted")
        title_row.append(title); title_row.append(self.task_count)
        tasks_column.append(title_row)
        self.task_list = Gtk.ListBox()
        self.task_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.task_list.add_css_class("boxed-list")
        tasks_column.append(self.task_list)
        add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.task_entry = Gtk.Entry(placeholder_text="Add a task…", hexpand=True)
        self.task_entry.connect("activate", self._add_task)
        add_button = Gtk.Button(label="Add", icon_name="list-add-symbolic")
        add_button.add_css_class("suggested-action"); add_button.connect("clicked", self._add_task)
        add_row.append(self.task_entry); add_row.append(add_button)
        tasks_column.append(add_row)
        top.append(tasks_column)

        timer_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        timer_column.set_size_request(280, -1)
        timer_title = Gtk.Label(label="Focus timer", xalign=0); timer_title.add_css_class("section-title")
        timer_column.append(timer_title)
        timer_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        timer_card.add_css_class("timer-card")
        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for name in ("Focus", "Short break", "Long break"):
            b = Gtk.ToggleButton(label=name)
            b.set_active(name == "Focus")
            b.connect("toggled", self._mode_toggled, name)
            mode_row.append(b)
        timer_card.append(mode_row)
        self.timer_label = Gtk.Label(label="25:00")
        self.timer_label.add_css_class("timer-value"); self.timer_label.set_margin_top(8); self.timer_label.set_margin_bottom(4)
        timer_card.append(self.timer_label)
        self.timer_status = Gtk.Label(label="Ready when you are", xalign=0)
        self.timer_status.add_css_class("muted"); timer_card.append(self.timer_status)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.start_button = Gtk.Button(label="Start", icon_name="media-playback-start-symbolic")
        self.start_button.add_css_class("suggested-action"); self.start_button.set_hexpand(True)
        self.start_button.connect("clicked", self._toggle_timer)
        reset = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Reset timer")
        reset.connect("clicked", self._reset_timer)
        controls.append(self.start_button); controls.append(reset)
        timer_card.append(controls)
        timer_column.append(timer_card)
        self.session_label = Gtk.Label(label="0 focused minutes today", xalign=0); self.session_label.add_css_class("muted")
        timer_column.append(self.session_label)
        top.append(timer_column)

        stats = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.stats_label = Gtk.Label(label="Small steps add up.", xalign=0); self.stats_label.add_css_class("muted")
        stats.append(self.stats_label)
        content.append(stats)

    def _install_actions(self):
        action = Gio.SimpleAction.new("shortcuts", None); action.connect("activate", self._show_shortcuts); self.add_action(action)
        about = Gio.SimpleAction.new("about", None); about.connect("activate", self._show_about); self.get_application().add_action(about)
        quit_action = Gio.SimpleAction.new("quit", None); quit_action.connect("activate", lambda *_: self.get_application().quit()); self.get_application().add_action(quit_action)
        for name, key in (("add-task", "<Primary>n"), ("toggle-timer", "<Primary>Return")):
            a = Gio.SimpleAction.new(name, None); a.connect("activate", self._add_task if name == "add-task" else self._toggle_timer); self.add_action(a)
            self.get_application().set_accels_for_action(f"win.{name}", [key])
        self.get_application().set_accels_for_action("win.shortcuts", ["<Primary>question"])

    def _show_about(self, *_):
        dialog = Adw.AboutDialog(application_name="FocusFlow", application_icon=APP_ID, version="1.0.0", developer_name="TMP Inc", comments="A proprietary, local-first focus planner for GNOME.", website="https://github.com/tmp-inc/focusflow", issue_url="https://github.com/tmp-inc/focusflow/issues")
        dialog.present(self)

    def _show_shortcuts(self, *_):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, buttons=Gtk.ButtonsType.OK, text="Keyboard shortcuts", secondary_text="Ctrl + N   Add a task\nCtrl + Enter   Start or pause timer\nEnter   Add task when the field is focused")
        dialog.connect("response", lambda d, _: d.destroy()); dialog.present()

    def _mode_toggled(self, button, name):
        if not button.get_active(): return
        group = button.get_parent()
        for child in group:
            if child is not button and isinstance(child, Gtk.ToggleButton): child.set_active(False)
        self.mode = name
        self.remaining = {"Focus": 25, "Short break": 5, "Long break": 15}[name] * 60
        self.running = False
        if self.timer_source: GLib.source_remove(self.timer_source); self.timer_source = None
        self.start_button.set_label("Start"); self._update_timer()

    def _toggle_timer(self, *_):
        if self.running:
            self.running = False
            if self.timer_source: GLib.source_remove(self.timer_source); self.timer_source = None
            self.start_button.set_label("Resume"); self.timer_status.set_text("Paused")
        else:
            self.running = True; self.start_button.set_label("Pause"); self.timer_status.set_text(f"{self.mode} in progress")
            self.timer_source = GLib.timeout_add_seconds(1, self._tick)

    def _tick(self):
        if not self.running: return GLib.SOURCE_REMOVE
        self.remaining -= 1
        if self.remaining <= 0:
            self.remaining = 0; self.running = False; self.start_button.set_label("Start")
            if self.mode == "Focus": self.session_minutes += 25; self._save_session()
            self.toast_overlay.add_toast(Adw.Toast.new(f"{self.mode} complete — nice work!"))
            self.timer_status.set_text("Complete")
            self._update_timer(); return GLib.SOURCE_REMOVE
        self._update_timer(); return GLib.SOURCE_CONTINUE

    def _update_timer(self):
        self.timer_label.set_text(f"{self.remaining // 60:02d}:{self.remaining % 60:02d}")
        self.session_label.set_text(f"{self.session_minutes} focused minutes today")

    def _reset_timer(self, *_):
        self.running = False
        if self.timer_source: GLib.source_remove(self.timer_source); self.timer_source = None
        self.remaining = {"Focus": 25, "Short break": 5, "Long break": 15}[self.mode] * 60
        self.start_button.set_label("Start"); self.timer_status.set_text("Ready when you are"); self._update_timer()

    def _save_session(self):
        self._update_timer()

    def _add_task(self, *_):
        text = self.task_entry.get_text().strip()
        if not text: return
        self.tasks.insert(0, {"id": str(uuid.uuid4()), "title": text, "done": False, "created": date.today().isoformat()})
        save_tasks(self.tasks); self.task_entry.set_text(""); self._refresh_tasks()

    def _toggle_task(self, task_id, check):
        for task in self.tasks:
            if task["id"] == task_id: task["done"] = check.get_active()
        save_tasks(self.tasks); self._refresh_tasks()

    def _delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t["id"] != task_id]; save_tasks(self.tasks); self._refresh_tasks()

    def _refresh_tasks(self):
        while child := self.task_list.get_first_child(): self.task_list.remove(child)
        done = sum(1 for t in self.tasks if t.get("done"))
        self.task_count.set_text(f"{len(self.tasks)} task{'s' if len(self.tasks) != 1 else ''}")
        pct = round(done / len(self.tasks) * 100) if self.tasks else 0
        self.progress_number.set_text(f"{pct}%")
        self.stats_label.set_text("You have a clear runway." if not self.tasks else f"{done} of {len(self.tasks)} complete — keep the momentum gentle.")
        for task in self.tasks:
            row = Gtk.ListBoxRow(); box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); box.add_css_class("task-row")
            check = Gtk.CheckButton(); check.set_active(task.get("done", False)); check.connect("toggled", self._toggle_task, task["id"])
            box.append(check)
            label = Gtk.Label(label=task["title"], xalign=0, hexpand=True); label.add_css_class("task-title")
            if task.get("done"): label.add_css_class("task-done")
            label.set_ellipsize(Pango.EllipsizeMode.END); box.append(label)
            delete = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Delete task", has_frame=False)
            delete.connect("clicked", lambda _, tid=task["id"]: self._delete_task(tid)); box.append(delete)
            row.set_child(box); self.task_list.append(row)


class FocusFlowApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        win = app.get_active_window()
        if not win: win = FocusFlowWindow(app)
        win.present()


if __name__ == "__main__":
    FocusFlowApp().run(None)
