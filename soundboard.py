#!/usr/bin/env python3
"""Mesa de Sons — soundboard local para os .mp3 de ~/Music."""

import os
import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gtk, GLib, Gst  # noqa: E402

Gst.init(None)

MUSIC_DIR = os.path.expanduser("~/Music")

_HASH_RE = re.compile(r"_[A-Za-z0-9]{5,10}$")
_TOOL_SUFFIX_RE = re.compile(r"(-mp3cut|-sound-effect)$", re.IGNORECASE)


def pretty_label(filename):
    """Converte um nome de arquivo .mp3 em um rótulo legível para o botão."""
    base = os.path.basename(filename)
    stem = re.sub(r"\.mp3$", "", base, flags=re.IGNORECASE)

    # (2) remove hash de download: precisa ter maiúscula E minúscula
    m = _HASH_RE.search(stem)
    if m:
        suffix = m.group(0)[1:]  # sem o "_"
        if any(c.islower() for c in suffix) and any(c.isupper() for c in suffix):
            stem = stem[: m.start()]

    # (3) remove sufixos de ferramenta
    stem = _TOOL_SUFFIX_RE.sub("", stem)

    # (4) separadores -> espaço
    words = re.sub(r"[-_]+", " ", stem).split()
    label = " ".join(w.capitalize() for w in words)

    if not label:
        fallback_stem = re.sub(r"\.mp3$", "", base, flags=re.IGNORECASE)
        label = re.sub(r"[-_]+", " ", fallback_stem).title().replace(" ", "")
    return label


def scan_sounds(directory=MUSIC_DIR):
    """Lista (label, caminho_abs) dos .mp3 no diretório, ordenados por label."""
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    sounds = []
    for name in entries:
        path = os.path.join(directory, name)
        if name.lower().endswith(".mp3") and os.path.isfile(path):
            sounds.append((pretty_label(name), os.path.abspath(path)))
    sounds.sort(key=lambda item: item[0].lower())
    return sounds


class SoundPlayer:
    """Reprodutor de um som por vez usando GStreamer playbin."""

    def __init__(self):
        """Initialise playbin and connect bus watch. Note: automatic EOS/ERROR handling requires a running GLib main loop (provided by the GTK app)."""
        self._playbin = Gst.ElementFactory.make("playbin", "player")
        if self._playbin is None:
            raise RuntimeError("Não foi possível criar o elemento playbin do GStreamer")
        self._volume = 1.0
        self._playbin.set_property("volume", self._volume)
        bus = self._playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)

    def _on_message(self, _bus, message):
        t = message.type
        if t in (Gst.MessageType.EOS, Gst.MessageType.ERROR):
            self._playbin.set_state(Gst.State.NULL)

    def play(self, path):
        self._playbin.set_state(Gst.State.NULL)
        self._playbin.set_property("uri", Gst.filename_to_uri(path))
        self._playbin.set_property("volume", self._volume)
        self._playbin.set_state(Gst.State.PLAYING)

    def stop(self):
        self._playbin.set_state(Gst.State.NULL)

    def set_volume(self, fraction):
        self._volume = max(0.0, min(1.0, float(fraction)))
        self._playbin.set_property("volume", self._volume)


class SoundboardWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Mesa de Sons")
        self.set_default_size(640, 480)
        self._player = SoundPlayer()

        header = Adw.HeaderBar()

        self._search = Gtk.SearchEntry(placeholder_text="Buscar som...")
        self._search.set_hexpand(True)
        self._search.connect("search-changed", self._on_search)

        self._volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._volume.set_value(100)
        self._volume.set_size_request(140, -1)
        self._volume.set_draw_value(False)
        self._volume.connect("value-changed", self._on_volume)

        stop_btn = Gtk.Button(label="⏹ Parar tudo")
        stop_btn.add_css_class("destructive-action")
        stop_btn.connect("clicked", lambda _b: self._player.stop())

        reload_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        reload_btn.set_tooltip_text("Reler ~/Music")
        reload_btn.connect("clicked", lambda _b: self.reload())

        header.pack_start(self._volume)
        header.set_title_widget(self._search)
        header.pack_end(stop_btn)
        header.pack_end(reload_btn)

        self._flow = Gtk.FlowBox()
        self._flow.set_valign(Gtk.Align.START)
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_max_children_per_line(6)
        self._flow.set_min_children_per_line(2)
        self._flow.set_column_spacing(8)
        self._flow.set_row_spacing(8)
        self._flow.set_margin_top(12)
        self._flow.set_margin_bottom(12)
        self._flow.set_margin_start(12)
        self._flow.set_margin_end(12)
        self._flow.set_filter_func(self._filter_func)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(self._flow)

        self._empty = Adw.StatusPage(
            icon_name="audio-volume-muted-symbolic",
            title="Nenhum som encontrado",
            description=f"Coloque arquivos .mp3 em {MUSIC_DIR}",
        )

        self._stack = Gtk.Stack()
        self._stack.add_named(scroller, "grid")
        self._stack.add_named(self._empty, "empty")

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self._stack)
        self.set_content(toolbar)

        self.reload()

    def reload(self):
        child = self._flow.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._flow.remove(child)
            child = nxt

        sounds = scan_sounds()
        for label, path in sounds:
            btn = Gtk.Button(label=label)
            btn.set_hexpand(True)
            btn.set_size_request(-1, 64)
            btn.connect("clicked", self._on_play, path)
            self._flow.append(btn)

        self._stack.set_visible_child_name("grid" if sounds else "empty")
        self._flow.invalidate_filter()

    def _on_play(self, button, path):
        try:
            self._player.play(path)
        except Exception:
            button.add_css_class("error")
            GLib.timeout_add(1000, self._clear_error, button)

    def _clear_error(self, button):
        button.remove_css_class("error")
        return GLib.SOURCE_REMOVE

    def _on_volume(self, scale):
        self._player.set_volume(scale.get_value() / 100.0)

    def _on_search(self, _entry):
        self._flow.invalidate_filter()

    def _filter_func(self, child):
        text = self._search.get_text().strip().lower()
        if not text:
            return True
        button = child.get_child()
        return text in button.get_label().lower()


class SoundboardApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.omarchy.soundboard")

    def do_activate(self):
        win = self.get_active_window() or SoundboardWindow(self)
        win.present()


def main():
    app = SoundboardApp()
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
