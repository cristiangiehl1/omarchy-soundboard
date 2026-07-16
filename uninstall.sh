#!/usr/bin/env bash
# Remove o launcher e a entrada de menu do omarchy-soundboard.
set -euo pipefail

rm -f "$HOME/.local/bin/omarchy-soundboard"
rm -f "$HOME/.local/share/applications/omarchy-soundboard.desktop"
echo "omarchy-soundboard desinstalado (launcher e .desktop removidos)."
