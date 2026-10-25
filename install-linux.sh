#!/usr/bin/env bash
# Kitaplık'ı ~/.local/share/kitaplik/app altına kurar ve uygulama menüsüne ekler.
# Kullanım: ./install-linux.sh            kur / güncelle
#           ./install-linux.sh --uninstall kaldır (ayarlar ve etiketler korunur)
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/kitaplik/app"
DESKTOP="$HOME/.local/share/applications/kitaplik.desktop"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/kitaplik.svg"

if [ "$1" = "--uninstall" ]; then
    rm -rf "$HOME/.local/share/kitaplik" "$DESKTOP" "$ICON"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "Kitaplık kaldırıldı. Ayarlar ve etiketler ~/.config/kitaplik altında duruyor."
    exit 0
fi

mkdir -p "$APP/static" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
cp "$SRC/kitaplik.py" "$SRC/kitaplik.svg" "$APP/"
cp "$SRC/static/index.html" "$APP/static/"
cp "$SRC/kitaplik.svg" "$ICON"
cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Name=Kitaplık
GenericName=E-kitap Yöneticisi
Comment=E-kitap etiketleme, filtreleme ve kalite puanı
Exec=python3 "$APP/kitaplik.py"
Icon=kitaplik
Terminal=false
Categories=Office;Viewer;
Keywords=ebook;epub;pdf;library;kitap;e-kitap;
StartupWMClass=kitaplik
DESK
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Kitaplık kuruldu: $APP"
echo "Uygulama menüsünde 'Kitaplık' olarak görünür. Güncellemek için bu betiği yeniden çalıştırın."
