#!/usr/bin/env python3
"""Mesa de Sons — soundboard local para os .mp3 de ~/Music."""

import os
import re

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
