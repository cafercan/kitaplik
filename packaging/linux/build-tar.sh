#!/usr/bin/env bash
# Kitaplık için taşınabilir Linux paketi (.tar.gz): istenen klasöre açılıp çalıştırılır.
# C Launcher, kullanıcı bir kurulum klasörü seçtiğinde .deb yerine bunu kullanır.
# Gereken sistem paketleri .deb ile aynıdır: python3, python3-gi, gir1.2-webkit2-4.1.
# Kullanım: packaging/linux/build-tar.sh [çıktı klasörü]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/dist}"
VER="$(python3 "$ROOT/kitaplik.py" --version)"
WORK="$(mktemp -d)"
APP="$WORK/kitaplik"

install -Dm644 "$ROOT/kitaplik.py" "$APP/kitaplik.py"
install -Dm644 "$ROOT/kitaplik.svg" "$APP/kitaplik.svg"
install -Dm644 "$ROOT/static/index.html" "$APP/static/index.html"
install -Dm644 "$ROOT/LICENSE" "$APP/LICENSE"
cat > "$APP/kitaplik" <<'SH'
#!/bin/sh
exec python3 "$(dirname "$(readlink -f "$0")")/kitaplik.py" "$@"
SH
chmod 755 "$APP/kitaplik"

mkdir -p "$OUT"
tar -C "$WORK" --owner=0 --group=0 -czf "$OUT/kitaplik-$VER-linux-portable.tar.gz" kitaplik
rm -rf "$WORK"
echo "$OUT/kitaplik-$VER-linux-portable.tar.gz"
