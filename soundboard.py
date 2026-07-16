#!/usr/bin/env python3
"""Mesa de Sons — soundboard local para os .mp3 de ~/Music."""

import os
import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gdk, Gtk, GLib, Gst  # noqa: E402

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


_CYBERPUNK_CSS = b"""
/* Cyberpunk Neon - paleta do omarchy-cyberpunk-neon */
.cyber {
  background-color: #120621;
  background-image:
    radial-gradient(circle at 15% -10%, rgba(189,0,255,0.18), transparent 55%),
    radial-gradient(circle at 100% 115%, rgba(0,240,255,0.14), transparent 55%);
  color: #c792ff;
  font-family: "CaskaydiaMono Nerd Font", "JetBrainsMono Nerd Font", "JetBrains Mono", monospace;
}
.cyber scrolledwindow,
.cyber flowbox,
.cyber flowboxchild,
.cyber stack { background-color: transparent; }

.cyber headerbar {
  background-color: rgba(18,6,33,0.92);
  border-bottom: 1px solid rgba(0,240,255,0.45);
  box-shadow: 0 2px 14px rgba(189,0,255,0.30);
}

.cyber entry {
  background-color: rgba(36,22,51,0.9);
  color: #eddcff;
  border: 1px solid rgba(189,0,255,0.55);
  border-radius: 8px;
  caret-color: #00f0ff;
}
.cyber entry:focus-within {
  border-color: #00f0ff;
  box-shadow: 0 0 10px rgba(0,240,255,0.55);
}

.cyber button.sound-btn {
  background-color: rgba(36,22,51,0.55);
  background-image: linear-gradient(160deg, rgba(189,0,255,0.16), rgba(0,240,255,0.05));
  color: #d9b8ff;
  border: 1px solid rgba(189,0,255,0.55);
  border-radius: 10px;
  font-weight: 700;
  padding: 8px 10px;
  transition: all 160ms ease;
}
.cyber button.sound-btn:hover {
  color: #ffffff;
  border-color: #00f0ff;
  background-image: linear-gradient(160deg, rgba(0,240,255,0.22), rgba(189,0,255,0.16));
  box-shadow: 0 0 16px rgba(0,240,255,0.6), inset 0 0 10px rgba(189,0,255,0.25);
}
.cyber button.sound-btn:active {
  border-color: #ff2a6d;
  color: #ffffff;
  box-shadow: 0 0 20px rgba(255,42,109,0.75);
}
.cyber button.sound-btn.error {
  border-color: #ff2a6d;
  color: #ff2a6d;
  box-shadow: 0 0 18px rgba(255,42,109,0.85);
}

.cyber button.destructive-action {
  background-image: linear-gradient(160deg, #ff2a6d, #bd00ff);
  color: #120621;
  border: 0;
  border-radius: 8px;
  font-weight: 800;
  box-shadow: 0 0 12px rgba(255,42,109,0.55);
}
.cyber button.destructive-action:hover {
  box-shadow: 0 0 20px rgba(255,42,109,0.85);
}

.cyber button.cyber-icon {
  color: #00f0ff;
  background: transparent;
  border: 1px solid rgba(0,240,255,0.35);
  border-radius: 8px;
}
.cyber button.cyber-icon:hover {
  color: #ffffff;
  box-shadow: 0 0 12px rgba(0,240,255,0.6);
}

.cyber scale trough {
  background-color: rgba(36,22,51,0.95);
  border: 1px solid rgba(0,240,255,0.3);
  border-radius: 6px;
  min-height: 6px;
}
.cyber scale highlight {
  background-image: linear-gradient(90deg, #bd00ff, #00f0ff);
  border-radius: 6px;
}
.cyber scale slider {
  background-color: #00f0ff;
  border: 0;
  box-shadow: 0 0 8px rgba(0,240,255,0.8);
  min-width: 14px;
  min-height: 14px;
  border-radius: 50%;
}

.cyber statuspage title { color: #00f0ff; }
.cyber statuspage image { color: #bd00ff; }
"""


def install_cyberpunk_css():
    """Instala o CSS neon no display, sobrescrevendo o tema GTK ativo."""
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_CYBERPUNK_CSS)
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


class SoundboardWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Mesa de Sons")
        self.set_default_size(640, 480)
        self.add_css_class("cyber")
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
        reload_btn.add_css_class("cyber-icon")
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
            btn.add_css_class("sound-btn")
            btn.connect("clicked", self._on_play, path)
            self._flow.append(btn)

        self._sounds = sounds
        self._flow.invalidate_filter()
        self._update_view()

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
        self._update_view()

    def _filter_func(self, child):
        text = self._search.get_text().strip().lower()
        if not text:
            return True
        button = child.get_child()
        return text in button.get_label().lower()

    def _update_view(self):
        """Escolhe entre a grade e o estado vazio (sem sons x sem resultado de busca)."""
        text = self._search.get_text().strip().lower()
        if not self._sounds:
            self._empty.set_title("Nenhum som encontrado")
            self._empty.set_description(f"Coloque arquivos .mp3 em {MUSIC_DIR}")
            self._stack.set_visible_child_name("empty")
        elif text and not any(text in label.lower() for label, _ in self._sounds):
            self._empty.set_title("Nenhum resultado")
            self._empty.set_description("Nenhum som corresponde à busca.")
            self._stack.set_visible_child_name("empty")
        else:
            self._stack.set_visible_child_name("grid")


class SoundboardApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.omarchy.soundboard")

    def do_activate(self):
        install_cyberpunk_css()
        win = self.get_active_window() or SoundboardWindow(self)
        win.present()


def main():
    app = SoundboardApp()
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
