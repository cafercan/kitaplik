#!/usr/bin/env bash
# Kitaplık'ı ~/.local/share/kitaplik/app altına kurar ve uygulama menüsüne ekler.
# Kaynak klasör harici diskte olsa bile kurulu uygulama ondan bağımsız çalışır.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
APP=~/.local/share/kitaplik/app
mkdir -p "$APP/static" ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
cp "$SRC/kitaplik.py" "$SRC/kitaplik.svg" "$APP/"
cp "$SRC/static/index.html" "$APP/static/"
cp "$SRC/kitaplik.svg" ~/.local/share/icons/hicolor/scalable/apps/kitaplik.svg
cat > ~/.local/share/applications/kitaplik.desktop <<DESK
[Desktop Entry]
Type=Application
Name=Kitaplık
GenericName=E-kitap Yöneticisi
Comment=E-kitap etiketleme, filtreleme ve kalite puanı
Exec=python3 "$APP/kitaplik.py"
Icon=kitaplik
Terminal=false
Categories=Office;Viewer;
Keywords=ebook;epub;pdf;kitap;e-kitap;
StartupWMClass=kitaplik
DESK
update-desktop-database ~/.local/share/applications 2>/dev/null || true
gtk-update-icon-cache -q ~/.local/share/icons/hicolor 2>/dev/null || true
echo "Kuruldu: $APP"
echo "Uygulama menüsünde 'Kitaplık' olarak görünür. Güncellemek için bu betiği yeniden çalıştırın."
