#!/usr/bin/env bash
# Uygulama menüsüne "Kitaplık" kısayolu ekler.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/kitaplik.desktop <<DESK
[Desktop Entry]
Type=Application
Name=Kitaplık
Comment=E-kitap etiketleme, filtreleme ve kalite puanı
Exec=python3 "$DIR/kitaplik.py"
Icon=accessories-dictionary
Terminal=false
Categories=Office;Viewer;
DESK
echo "Kısayol eklendi: uygulama menüsünde 'Kitaplık'"
