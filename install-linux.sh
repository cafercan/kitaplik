#!/usr/bin/env bash
# Rafta'yı ~/.local/share/rafta/app altına kurar ve uygulama menüsüne ekler.
# Kullanım: ./install-linux.sh            kur / güncelle
#           ./install-linux.sh --uninstall kaldır (ayarlar ve etiketler korunur)
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/rafta/app"
DESKTOP="$HOME/.local/share/applications/rafta.desktop"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/rafta.svg"

# eski adla ("Kitaplık") yapılmış kurulumu temizle
rm -rf "$HOME/.local/share/kitaplik"
rm -f "$HOME/.local/share/applications/kitaplik.desktop" "$HOME/.local/share/icons/hicolor/scalable/apps/kitaplik.svg"

if [ "$1" = "--uninstall" ]; then
    rm -rf "$HOME/.local/share/rafta" "$DESKTOP" "$ICON"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "Rafta kaldırıldı. Ayarlar ve etiketler ~/.config/rafta altında duruyor."
    exit 0
fi

mkdir -p "$APP/static" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
cp "$SRC/rafta.py" "$SRC/rafta.svg" "$APP/"
cp "$SRC/static/index.html" "$APP/static/"
cp "$SRC/rafta.svg" "$ICON"
cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Name=Rafta
GenericName=E-kitap Yöneticisi
Comment=E-kitap etiketleme, filtreleme ve kalite puanı
Exec=python3 "$APP/rafta.py"
Icon=rafta
Terminal=false
Categories=Office;Viewer;
Keywords=ebook;epub;pdf;library;kitap;e-kitap;
StartupWMClass=rafta
DESK
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Rafta kuruldu: $APP"
echo "Uygulama menüsünde 'Rafta' olarak görünür. Güncellemek için bu betiği yeniden çalıştırın."
