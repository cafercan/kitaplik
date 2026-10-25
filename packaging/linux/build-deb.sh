#!/usr/bin/env bash
# Kitaplık için mimariden bağımsız .deb paketi üretir.
# Kullanım: packaging/linux/build-deb.sh [çıktı klasörü]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/dist}"
VER="$(python3 "$ROOT/kitaplik.py" --version)"
PKG="$(mktemp -d)/kitaplik"

install -Dm644 "$ROOT/kitaplik.py" "$PKG/usr/lib/kitaplik/kitaplik.py"
install -Dm644 "$ROOT/kitaplik.svg" "$PKG/usr/lib/kitaplik/kitaplik.svg"
install -Dm644 "$ROOT/static/index.html" "$PKG/usr/lib/kitaplik/static/index.html"
install -Dm644 "$ROOT/kitaplik.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/kitaplik.svg"
install -Dm644 "$ROOT/packaging/icons/kitaplik-256.png" "$PKG/usr/share/icons/hicolor/256x256/apps/kitaplik.png"
install -Dm644 "$ROOT/LICENSE" "$PKG/usr/share/doc/kitaplik/copyright"

install -d "$PKG/usr/bin"
cat > "$PKG/usr/bin/kitaplik" <<'SH'
#!/bin/sh
exec python3 /usr/lib/kitaplik/kitaplik.py "$@"
SH
chmod 755 "$PKG/usr/bin/kitaplik"

install -d "$PKG/usr/share/applications"
cat > "$PKG/usr/share/applications/kitaplik.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=Kitaplık
GenericName=E-kitap Yöneticisi
Comment=E-kitap etiketleme, filtreleme ve kalite puanı
Exec=kitaplik
Icon=kitaplik
Terminal=false
Categories=Office;Viewer;
Keywords=ebook;epub;pdf;library;kitap;e-kitap;
StartupWMClass=kitaplik
DESK
chmod 644 "$PKG/usr/share/applications/kitaplik.desktop"

install -d "$PKG/DEBIAN"
cat > "$PKG/DEBIAN/control" <<CTL
Package: kitaplik
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Recommends: poppler-utils
Maintainer: cafercan <cafercan@outlook.com>
Homepage: https://github.com/cafercan/kitaplik
Description: E-kitap kitaplığı için etiketleme, filtreleme ve kalite puanı
 Yerel bir e-kitap klasöründeki EPUB ve PDF dosyalarını listeler; kapak,
 meta veri, kalite puanı, favori ve etiketleri tek pencerede gösterir.
CTL

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$PKG" "$OUT/kitaplik-$VER-linux-all.deb" >/dev/null
rm -rf "$(dirname "$PKG")"
echo "$OUT/kitaplik-$VER-linux-all.deb"
