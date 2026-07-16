#!/usr/bin/env bash
# Instala o omarchy-soundboard: launcher no PATH + entrada no menu.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"

mkdir -p "$BIN_DIR" "$APP_DIR"

chmod +x "$SCRIPT_DIR/soundboard.py"
ln -sf "$SCRIPT_DIR/soundboard.py" "$BIN_DIR/omarchy-soundboard"
cp "$SCRIPT_DIR/omarchy-soundboard.desktop" "$APP_DIR/omarchy-soundboard.desktop"

echo "Instalado:"
echo "  launcher: $BIN_DIR/omarchy-soundboard -> $SCRIPT_DIR/soundboard.py"
echo "  desktop:  $APP_DIR/omarchy-soundboard.desktop"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "AVISO: $BIN_DIR não está no PATH; adicione-o para usar o comando 'omarchy-soundboard'." ;;
esac
