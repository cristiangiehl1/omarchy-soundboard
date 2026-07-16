#!/usr/bin/env python3
"""Mesa de Sons - soundboard local cyberpunk para os .mp3 de ~/Music."""

import array
import math
import os
import re
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gdk, GLib, Gst, Gtk, Pango  # noqa: E402

import cairo  # noqa: E402

# Permite imports irmãos mesmo quando executado via symlink em ~/.local/bin.
import sys  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

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


# ---------------------------------------------------------------------------
# Categorias (cor de destaque por tipo de som)
# ---------------------------------------------------------------------------

# (nome, cor hex, slug css, palavras-chave)
CATEGORY_RULES = [
    ("Games", "#00f0ff", "games",
     ("league", "lol", "first-blood", "first blood", "shaco", "lulu",
      "volibear", "dark-souls", "dark souls", "you-died", "you died", "retroarch")),
    ("Anime", "#bd00ff", "anime",
     ("kurapika", "naruto", "goku", "anime", "hxh", "otaku")),
    ("Música", "#05ffa1", "music",
     ("summer", "when-i-met", "when i met", "music", "song", "beat", "remix")),
    ("Memes", "#ff2a6d", "memes",
     ("risada", "cariani", "macaquito", "messi", "megatron", "brutal",
      "meme", "globo", "cu")),
]
DEFAULT_CATEGORY = ("Outros", "#c792ff", "other")


def detect_category(name):
    """Devolve (categoria, cor_hex, slug) a partir do nome/rótulo do som."""
    low = name.lower()
    for cat, color, slug, keys in CATEGORY_RULES:
        if any(k in low for k in keys):
            return cat, color, slug
    return DEFAULT_CATEGORY


def hex_to_rgb(hex_color):
    """'#rrggbb' -> (r, g, b) em 0..1."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Áudio: duração e envelope de waveform (via ffprobe/ffmpeg)
# ---------------------------------------------------------------------------


def probe_duration(path):
    """Duração em segundos (0.0 se falhar)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=15,
        )
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def compute_waveform(path, buckets=44):
    """Envelope de amplitude (lista 0..1) via ffmpeg (mono, 8 kHz, s16le)."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", "8000",
             "-f", "s16le", "-"],
            capture_output=True, timeout=25,
        )
        data = proc.stdout
    except (OSError, subprocess.SubprocessError):
        return []
    samples = array.array("h")
    samples.frombytes(data[: len(data) // 2 * 2])
    if not samples:
        return []
    n = len(samples)
    size = max(1, n // buckets)
    peaks = []
    for i in range(0, n, size):
        chunk = samples[i:i + size]
        if chunk:
            peaks.append(max(abs(x) for x in chunk) / 32768.0)
    top = max(peaks) if peaks else 1.0
    top = top or 1.0
    return [p / top for p in peaks[:buckets]]


def fmt_duration(seconds):
    if not seconds or seconds <= 0:
        return ""
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Player (GStreamer) com spectrum reativo e progresso
# ---------------------------------------------------------------------------


class SoundPlayer:
    """Reprodutor de um som por vez com análise de espectro em tempo real.

    Observação: o tratamento automático de EOS/ERROR e as mensagens de
    spectrum exigem um GLib main loop rodando (fornecido pelo app GTK).
    `on_stopped()` é chamado ao terminar/falhar/parar; `on_spectrum(bars)`
    recebe uma lista de alturas 0..1 por banda enquanto toca.
    """

    SPEC_BANDS = 14
    SPEC_THRESHOLD = -70
    _MAG_RE = re.compile(r"magnitude=\(float\)\{([^}]*)\}")

    def __init__(self, on_stopped=None, on_spectrum=None):
        self._playbin = Gst.ElementFactory.make("playbin", "player")
        if self._playbin is None:
            raise RuntimeError("Não foi possível criar o elemento playbin do GStreamer")
        self._on_stopped = on_stopped
        self._on_spectrum = on_spectrum
        self._volume = 1.0
        self._playbin.set_property("volume", self._volume)

        spectrum = Gst.ElementFactory.make("spectrum", "spectrum")
        if spectrum is not None:
            spectrum.set_property("bands", self.SPEC_BANDS)
            spectrum.set_property("threshold", self.SPEC_THRESHOLD)
            spectrum.set_property("post-messages", True)
            spectrum.set_property("interval", 50_000_000)  # 50 ms
            self._playbin.set_property("audio-filter", spectrum)

        bus = self._playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)

    def _on_message(self, _bus, message):
        t = message.type
        if t == Gst.MessageType.ELEMENT:
            s = message.get_structure()
            if s is not None and s.get_name() == "spectrum" and self._on_spectrum:
                mm = self._MAG_RE.search(s.to_string())
                if mm:
                    thr = self.SPEC_THRESHOLD
                    bars = []
                    for x in mm.group(1).split(","):
                        try:
                            v = (float(x) - thr) / (-thr)
                        except ValueError:
                            v = 0.0
                        bars.append(min(1.0, max(0.0, v)))
                    self._on_spectrum(bars)
        elif t in (Gst.MessageType.EOS, Gst.MessageType.ERROR):
            self._playbin.set_state(Gst.State.NULL)
            if self._on_stopped is not None:
                self._on_stopped()

    def play(self, path):
        self._playbin.set_state(Gst.State.NULL)
        self._playbin.set_property("uri", Gst.filename_to_uri(path))
        self._playbin.set_property("volume", self._volume)
        self._playbin.set_state(Gst.State.PLAYING)

    def stop(self):
        self._playbin.set_state(Gst.State.NULL)
        if self._on_stopped is not None:
            self._on_stopped()

    def set_volume(self, fraction):
        self._volume = max(0.0, min(1.0, float(fraction)))
        self._playbin.set_property("volume", self._volume)

    def get_progress(self):
        """Fração 0..1 da posição atual (0.0 se desconhecido)."""
        ok_p, pos = self._playbin.query_position(Gst.Format.TIME)
        ok_d, dur = self._playbin.query_duration(Gst.Format.TIME)
        if ok_p and ok_d and dur > 0:
            return max(0.0, min(1.0, pos / dur))
        return 0.0


# ---------------------------------------------------------------------------
# Fundo synthwave animado (Cairo)
# ---------------------------------------------------------------------------


class SynthwaveBackground(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._phase = 0.0
        self._last = None
        self.set_draw_func(self._draw)
        self.add_tick_callback(self._tick)

    def _tick(self, _widget, clock):
        now = clock.get_frame_time()  # microssegundos
        if self._last is not None:
            dt = (now - self._last) / 1_000_000.0
            self._phase = (self._phase + dt * 0.35) % 1.0
            self.queue_draw()
        self._last = now
        return GLib.SOURCE_CONTINUE

    def _draw(self, _area, cr, w, h):
        # fundo em gradiente violeta
        g = cairo.LinearGradient(0, 0, 0, h)
        g.add_color_stop_rgb(0.0, 0x12 / 255, 0x06 / 255, 0x21 / 255)
        g.add_color_stop_rgb(0.65, 0x1a / 255, 0x07 / 255, 0x33 / 255)
        g.add_color_stop_rgb(1.0, 0x24 / 255, 0x0b / 255, 0x40 / 255)
        cr.set_source(g)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        horizon = h * 0.66
        cx = w / 2

        # sol neon
        sun_r = min(w, h) * 0.18
        sun = cairo.RadialGradient(cx, horizon, sun_r * 0.2, cx, horizon, sun_r)
        sun.add_color_stop_rgba(0.0, 1.0, 0.16, 0.42, 0.35)
        sun.add_color_stop_rgba(1.0, 0.74, 0.0, 1.0, 0.0)
        cr.set_source(sun)
        cr.arc(cx, horizon, sun_r, 0, 2 * math.pi)
        cr.fill()

        # linha do horizonte
        cr.set_line_width(1.5)
        cr.set_source_rgba(0.0, 0.94, 1.0, 0.35)
        cr.move_to(0, horizon)
        cr.line_to(w, horizon)
        cr.stroke()

        # grade em perspectiva: verticais convergindo
        cr.set_line_width(1)
        cols = 14
        for i in range(-cols, cols + 1):
            x_bottom = cx + i * (w / cols)
            cr.set_source_rgba(0.0, 0.94, 1.0, 0.08)
            cr.move_to(cx, horizon)
            cr.line_to(x_bottom, h)
            cr.stroke()

        # horizontais rolando em direção ao observador
        rows = 12
        for j in range(rows):
            t = ((j + self._phase) % rows) / rows
            y = horizon + (h - horizon) * (t * t)
            alpha = 0.14 * (1 - t) + 0.02
            cr.set_source_rgba(0.74, 0.0, 1.0, alpha)
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.stroke()

        # scanlines (CRT) sutis
        cr.set_source_rgba(0, 0, 0, 0.10)
        y = 0
        while y < h:
            cr.rectangle(0, y, w, 1)
            y += 3
        cr.fill()


# ---------------------------------------------------------------------------
# Área de visualização de cada card (waveform / equalizer / progresso)
# ---------------------------------------------------------------------------


class SoundVizArea(Gtk.DrawingArea):
    def __init__(self, accent_rgb):
        super().__init__()
        self.set_hexpand(True)
        self.set_content_height(26)
        self._accent = accent_rgb
        self.waveform = []
        self.spectrum = []
        self.progress = 0.0
        self.playing = False
        self.set_draw_func(self._draw)

    def _draw(self, _area, cr, w, h):
        r, g, b = self._accent
        if self.playing and self.spectrum:
            n = len(self.spectrum)
            bw = w / n
            for i, v in enumerate(self.spectrum):
                bh = max(2.0, v * h)
                cr.rectangle(i * bw + 1, h - bh, bw - 2, bh)
            cr.set_source_rgba(r, g, b, 0.9)
            cr.fill()
            # linha de progresso
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.85)
            cr.rectangle(0, h - 2, w * self.progress, 2)
            cr.fill()
        elif self.waveform:
            n = len(self.waveform)
            bw = w / n
            for i, v in enumerate(self.waveform):
                bh = max(1.0, v * (h * 0.9))
                cr.rectangle(i * bw + bw * 0.15, (h - bh) / 2, bw * 0.7, bh)
            cr.set_source_rgba(r, g, b, 0.35)
            cr.fill()


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------


class SoundboardWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Mesa de Sons")
        self.set_default_size(720, 540)
        self.add_css_class("cyber")

        self._playing_card = None
        self._active_cat = None
        self._progress_source = 0
        self._player = SoundPlayer(
            on_stopped=self._on_player_stopped,
            on_spectrum=self._on_spectrum,
        )

        # --- header neon ---
        header = Adw.HeaderBar()
        title = Gtk.Label(label="◢ SOUNDBOARD ◣")
        title.add_css_class("neon-title")

        self._volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._volume.set_value(100)
        self._volume.set_size_request(130, -1)
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
        header.set_title_widget(title)
        header.pack_end(stop_btn)
        header.pack_end(reload_btn)

        # --- subbarra: busca + chips de categoria ---
        self._search = Gtk.SearchEntry(placeholder_text="Buscar som...")
        self._search.set_hexpand(True)
        self._search.connect("search-changed", self._on_search)

        self._chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._chips_box.add_css_class("chips")

        subbar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        subbar.add_css_class("subbar")
        subbar.append(self._search)
        subbar.append(self._chips_box)

        # --- grade de cards ---
        self._flow = Gtk.FlowBox()
        self._flow.set_valign(Gtk.Align.START)
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_max_children_per_line(4)
        self._flow.set_min_children_per_line(2)
        self._flow.set_column_spacing(10)
        self._flow.set_row_spacing(10)
        self._flow.set_margin_top(10)
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

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(subbar)
        content.append(self._stack)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(content)

        # fundo synthwave por trás de tudo
        overlay = Gtk.Overlay()
        overlay.set_child(SynthwaveBackground())
        overlay.add_overlay(toolbar)
        self.set_content(overlay)

        self.reload()

    # --- construção dos cards ---

    def reload(self):
        self._stop_progress()
        self._playing_card = None
        child = self._flow.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._flow.remove(child)
            child = nxt

        sounds = scan_sounds()
        cats = []
        for label, path in sounds:
            card = self._make_card(label, path)
            self._flow.append(card)
            if card._category not in cats:
                cats.append(card._category)

        self._build_chips(cats)
        self._flow.invalidate_filter()
        self._update_view()

    def _make_card(self, label, path):
        cat, color, slug = detect_category(label)
        accent = hex_to_rgb(color)

        card = Gtk.Button()
        card.add_css_class("sound-btn")
        card.add_css_class(f"cat-{slug}")
        card.set_hexpand(True)
        card._sound_name = label
        card._category = cat

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name = Gtk.Label(label=label, xalign=0.0)
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.add_css_class("card-name")
        tag = Gtk.Label(label=cat.upper())
        tag.add_css_class("card-tag")
        tag.add_css_class(f"fg-{slug}")
        top.append(name)
        top.append(tag)

        meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        viz = SoundVizArea(accent)
        viz.set_hexpand(True)
        dur = Gtk.Label(label="")
        dur.add_css_class("card-dur")
        meta.append(viz)
        meta.append(dur)

        box.append(top)
        box.append(meta)
        card.set_child(box)
        card._viz = viz

        card.connect("clicked", self._on_play, path)
        self._load_meta_async(path, viz, dur)
        return card

    def _load_meta_async(self, path, viz, dur_label):
        def worker():
            wave = compute_waveform(path)
            secs = probe_duration(path)

            def apply():
                viz.waveform = wave
                viz.queue_draw()
                dur_label.set_text(fmt_duration(secs))
                return GLib.SOURCE_REMOVE

            GLib.idle_add(apply)

        threading.Thread(target=worker, daemon=True).start()

    # --- chips de categoria ---

    def _build_chips(self, cats):
        child = self._chips_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._chips_box.remove(child)
            child = nxt

        self._active_cat = None
        self._chips = []
        all_chip = Gtk.ToggleButton(label="Tudo", active=True)
        all_chip.add_css_class("chip")
        all_chip.connect("toggled", self._on_chip, None)
        self._chips_box.append(all_chip)
        self._chips.append((all_chip, None))

        for cat in cats:
            chip = Gtk.ToggleButton(label=cat)
            chip.add_css_class("chip")
            _, _, slug = detect_category(cat.lower())
            chip.add_css_class(f"chip-{slug}")
            chip.connect("toggled", self._on_chip, cat)
            self._chips_box.append(chip)
            self._chips.append((chip, cat))

        self._chips_box.set_visible(len(cats) > 1)

    def _on_chip(self, button, cat):
        if not button.get_active():
            # não deixa desmarcar o ativo clicando nele de novo
            if self._active_cat == cat:
                button.set_active(True)
            return
        self._active_cat = cat
        for chip, chip_cat in self._chips:
            if chip is not button and chip.get_active():
                chip.set_active(False)
        self._flow.invalidate_filter()
        self._update_view()

    # --- reprodução / estados ---

    def _on_play(self, card, path):
        try:
            self._player.play(path)
        except Exception:
            card.add_css_class("error")
            GLib.timeout_add(1000, self._clear_error, card)
            return
        self._set_playing(card)
        self._start_progress()

    def _set_playing(self, card):
        if self._playing_card is not None and self._playing_card is not card:
            self._playing_card.remove_css_class("playing")
            self._playing_card._viz.playing = False
            self._playing_card._viz.spectrum = []
            self._playing_card._viz.queue_draw()
        self._playing_card = card
        card.add_css_class("playing")
        card._viz.playing = True
        card._viz.progress = 0.0

    def _on_player_stopped(self):
        self._stop_progress()
        if self._playing_card is not None:
            self._playing_card.remove_css_class("playing")
            viz = self._playing_card._viz
            viz.playing = False
            viz.spectrum = []
            viz.progress = 0.0
            viz.queue_draw()
            self._playing_card = None

    def _on_spectrum(self, bars):
        if self._playing_card is not None:
            self._playing_card._viz.spectrum = bars
            self._playing_card._viz.queue_draw()

    def _start_progress(self):
        self._stop_progress()
        self._progress_source = GLib.timeout_add(90, self._tick_progress)

    def _stop_progress(self):
        if self._progress_source:
            GLib.source_remove(self._progress_source)
            self._progress_source = 0

    def _tick_progress(self):
        if self._playing_card is None:
            self._progress_source = 0
            return GLib.SOURCE_REMOVE
        self._playing_card._viz.progress = self._player.get_progress()
        self._playing_card._viz.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _clear_error(self, card):
        card.remove_css_class("error")
        return GLib.SOURCE_REMOVE

    def _on_volume(self, scale):
        self._player.set_volume(scale.get_value() / 100.0)

    def _on_search(self, _entry):
        self._flow.invalidate_filter()
        self._update_view()

    def _filter_func(self, child):
        card = child.get_child()
        if self._active_cat is not None and card._category != self._active_cat:
            return False
        text = self._search.get_text().strip().lower()
        if not text:
            return True
        return text in card._sound_name.lower()

    def _update_view(self):
        sounds_exist = self._flow.get_first_child() is not None
        if not sounds_exist:
            self._empty.set_title("Nenhum som encontrado")
            self._empty.set_description(f"Coloque arquivos .mp3 em {MUSIC_DIR}")
            self._stack.set_visible_child_name("empty")
            return
        # algum card visível após o filtro?
        text = self._search.get_text().strip().lower()
        visible = False
        child = self._flow.get_first_child()
        while child is not None:
            card = child.get_child()
            cat_ok = self._active_cat is None or card._category == self._active_cat
            txt_ok = not text or text in card._sound_name.lower()
            if cat_ok and txt_ok:
                visible = True
                break
            child = child.get_next_sibling()
        if visible:
            self._stack.set_visible_child_name("grid")
        else:
            self._empty.set_title("Nenhum resultado")
            self._empty.set_description("Nenhum som corresponde ao filtro.")
            self._stack.set_visible_child_name("empty")


# ---------------------------------------------------------------------------
# CSS cyberpunk + animações
# ---------------------------------------------------------------------------

_CYBERPUNK_CSS = b"""
@keyframes neon-pulse {
  0%   { border-color: #00f0ff; box-shadow: 0 0 8px rgba(0,240,255,0.55), inset 0 0 6px rgba(189,0,255,0.30); }
  50%  { border-color: #ff2a6d; box-shadow: 0 0 22px rgba(255,42,109,0.9), inset 0 0 12px rgba(255,42,109,0.40); }
  100% { border-color: #00f0ff; box-shadow: 0 0 8px rgba(0,240,255,0.55), inset 0 0 6px rgba(189,0,255,0.30); }
}
@keyframes border-flow {
  0%,100% { border-bottom-color: rgba(0,240,255,0.45); }
  50%     { border-bottom-color: rgba(189,0,255,0.65); }
}
@keyframes knob-glow {
  0%,100% { box-shadow: 0 0 6px rgba(0,240,255,0.7); }
  50%     { box-shadow: 0 0 15px rgba(0,240,255,1.0); }
}
@keyframes title-glow {
  0%,100% { color: #00f0ff; }
  50%     { color: #bd00ff; }
}

.cyber { background-color: #120621; color: #c792ff;
  font-family: "CaskaydiaMono Nerd Font", "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; }
.cyber overlay,
.cyber toolbarview,
.cyber scrolledwindow,
.cyber flowbox,
.cyber flowboxchild,
.cyber stack,
.cyber box { background-color: transparent; }

.cyber headerbar {
  background-color: rgba(18,6,33,0.80);
  border-bottom: 1px solid rgba(0,240,255,0.45);
  box-shadow: 0 2px 14px rgba(189,0,255,0.30);
  animation: border-flow 4s ease-in-out infinite;
}
.neon-title {
  font-weight: 800;
  letter-spacing: 2px;
  text-shadow: 0 0 8px rgba(0,240,255,0.7);
  animation: title-glow 5s ease-in-out infinite;
}

.subbar {
  padding: 10px 12px 4px 12px;
  background-color: rgba(18,6,33,0.55);
  border-bottom: 1px solid rgba(189,0,255,0.20);
}
.chips button.chip {
  background-color: rgba(36,22,51,0.7);
  color: #c792ff;
  border: 1px solid rgba(189,0,255,0.45);
  border-radius: 20px;
  padding: 2px 12px;
  min-height: 0;
  font-size: 11px;
}
.chips button.chip:checked {
  color: #120621;
  background-image: linear-gradient(160deg, #00f0ff, #bd00ff);
  border-color: #00f0ff;
  box-shadow: 0 0 10px rgba(0,240,255,0.5);
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
  background-color: rgba(30,10,53,0.55);
  border: 1px solid rgba(189,0,255,0.55);
  border-radius: 12px;
  padding: 10px 12px;
  transition: all 160ms ease;
}
.cyber button.sound-btn:hover {
  background-color: rgba(40,16,66,0.75);
  box-shadow: 0 0 16px rgba(0,240,255,0.45), inset 0 0 10px rgba(189,0,255,0.25);
}
.cyber button.sound-btn:active { box-shadow: 0 0 20px rgba(255,42,109,0.75); }
.cyber button.sound-btn.error { border-color: #ff2a6d; box-shadow: 0 0 18px rgba(255,42,109,0.85); }
.cyber button.sound-btn.playing {
  background-image: linear-gradient(160deg, rgba(0,240,255,0.18), rgba(255,42,109,0.14));
  animation: neon-pulse 1.05s ease-in-out infinite;
}

/* cor de borda por categoria */
.cyber button.sound-btn.cat-games  { border-color: rgba(0,240,255,0.60); }
.cyber button.sound-btn.cat-anime  { border-color: rgba(189,0,255,0.60); }
.cyber button.sound-btn.cat-music  { border-color: rgba(5,255,161,0.60); }
.cyber button.sound-btn.cat-memes  { border-color: rgba(255,42,109,0.60); }
.cyber button.sound-btn.cat-other  { border-color: rgba(199,146,255,0.50); }

.card-name { color: #eddcff; font-weight: 700; }
.card-tag  { font-size: 9px; font-weight: 800; letter-spacing: 1px; opacity: 0.9; }
.card-dur  { color: #7a6a99; font-size: 10px; }
.fg-games { color: #00f0ff; } .fg-anime { color: #bd00ff; }
.fg-music { color: #05ffa1; } .fg-memes { color: #ff2a6d; }
.fg-other { color: #c792ff; }
.chip-games:checked { background-image: linear-gradient(160deg,#00f0ff,#00b8ff); }
.chip-anime:checked { background-image: linear-gradient(160deg,#bd00ff,#d580ff); }
.chip-music:checked { background-image: linear-gradient(160deg,#05ffa1,#00f0ff); }
.chip-memes:checked { background-image: linear-gradient(160deg,#ff2a6d,#bd00ff); }

.cyber button.destructive-action {
  background-image: linear-gradient(160deg, #ff2a6d, #bd00ff);
  color: #120621; border: 0; border-radius: 8px; font-weight: 800;
  box-shadow: 0 0 12px rgba(255,42,109,0.55);
}
.cyber button.destructive-action:hover { box-shadow: 0 0 20px rgba(255,42,109,0.85); }

.cyber button.cyber-icon {
  color: #00f0ff; background: transparent;
  border: 1px solid rgba(0,240,255,0.35); border-radius: 8px;
}
.cyber button.cyber-icon:hover { color: #ffffff; box-shadow: 0 0 12px rgba(0,240,255,0.6); }

.cyber scale { min-height: 20px; }
.cyber scale trough {
  background-color: rgba(36,22,51,0.95);
  border: 1px solid rgba(0,240,255,0.3);
  border-radius: 6px; min-height: 8px;
}
.cyber scale highlight { background-image: linear-gradient(90deg, #bd00ff, #00f0ff); border-radius: 6px; }
.cyber scale slider {
  background-color: #00f0ff; border: 0; margin: 0;
  box-shadow: 0 0 8px rgba(0,240,255,0.8);
  min-width: 16px; min-height: 16px; border-radius: 50%;
  animation: knob-glow 2.6s ease-in-out infinite;
}

.cyber statuspage title { color: #00f0ff; }
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
