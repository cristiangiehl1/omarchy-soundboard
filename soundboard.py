#!/usr/bin/env python3
"""Mesa de Sons — soundboard local para os .mp3 de ~/Music."""

import os
import re

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

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
