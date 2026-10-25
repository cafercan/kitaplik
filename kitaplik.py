#!/usr/bin/env python3
"""Kitaplık: yerel e-kitap klasörleri için etiketleme, filtreleme ve kalite puanı arayüzü.

Yalnızca Python standart kütüphanesi kullanır. PDF analizi için `pdfinfo` ve
`pdftotext` (poppler) varsa kullanılır; yoksa PDF'ler temel bilgilerle listelenir.
"""
import html
import json
import os
import platform
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import webbrowser
import zipfile
from concurrent.futures import ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

__version__ = "0.1.0"

APP_DIR = Path(__file__).resolve().parent
# PyInstaller ile paketlendiğinde arayüz dosyaları geçici açma klasöründe durur
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
STATIC = RES_DIR / "static"


def _conf_base():
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


CONF_DIR = _conf_base() / "kitaplik"
CONF_FILE = CONF_DIR / "config.json"
DB_FILE = CONF_DIR / "kitaplik.db"
PORT = int(os.environ.get("KITAPLIK_PORT", "8765"))
# Her açılışta üretilen anahtar: başka sitelerin localhost API'sini kullanmasını engeller
TOKEN = secrets.token_urlsafe(32)

BOOK_EXT = {"epub", "pdf", "mobi", "azw", "azw3", "djvu", "fb2", "doc", "docx", "rtf", "txt", "cbz", "cbr"}
MOJIBAKE = re.compile(r"[ÝÞÐýþð]|Ã[¼§¶±‡]|Ä[±Ÿ]|Å[Ÿž]|�")
HAS_POPPLER = bool(shutil.which("pdfinfo") and shutil.which("pdftotext"))


# ---------------------------------------------------------------- ayarlar

def load_conf():
    try:
        return json.loads(CONF_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_conf(conf):
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    CONF_FILE.write_text(json.dumps(conf, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- veritabanı

def db():
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_FILE, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            root TEXT, path TEXT, size INTEGER, mtime REAL, ext TEXT,
            author TEXT, title TEXT, publisher TEXT, language TEXT, year TEXT,
            subjects TEXT, description TEXT, pages INTEGER, chars INTEGER,
            toc INTEGER, score INTEGER, notes TEXT,
            PRIMARY KEY (root, path));
        CREATE TABLE IF NOT EXISTS tags (
            root TEXT, path TEXT, tag TEXT, PRIMARY KEY (root, path, tag));
        CREATE TABLE IF NOT EXISTS favorites (
            root TEXT, path TEXT, PRIMARY KEY (root, path));
    """)
    return con


# ---------------------------------------------------------------- analiz

def mojibake_ratio(text):
    return len(MOJIBAKE.findall(text)) / max(1, len(text)) * 1000 if text else 0


def name_meta(path):
    """'Yazar - Kitap Adı.ext' biçimindeki dosya adından yazar/başlık çıkarır."""
    stem = Path(path).stem
    if " - " in stem:
        author, title = stem.split(" - ", 1)
        return author.strip(), title.strip()
    return "", stem.strip()


def opf_field(opf, tag):
    m = re.search(rf"<dc:{tag}[^>]*>(.*?)</dc:{tag}>", opf, re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def analyze_epub(full):
    z = zipfile.ZipFile(full)
    names = z.namelist()
    info = {}
    try:
        container = z.read("META-INF/container.xml").decode("utf-8", "ignore")
        opf = z.read(re.search(r'full-path="([^"]+)"', container).group(1)).decode("utf-8", "ignore")
        info = {
            "author": opf_field(opf, "creator"),
            "title": opf_field(opf, "title"),
            "publisher": opf_field(opf, "publisher"),
            "language": opf_field(opf, "language"),
            "year": opf_field(opf, "date")[:4],
            "subjects": ", ".join(html.unescape(s).strip() for s in re.findall(r"<dc:subject[^>]*>(.*?)</dc:subject>", opf, re.S | re.I)),
            "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", opf_field(opf, "description")))[:2000],
        }
    except (KeyError, AttributeError):
        pass
    pages = [n for n in names if re.search(r"\.x?html?$", n, re.I)]
    images = [n for n in names if re.search(r"\.(jpe?g|png|gif|webp)$", n, re.I)]
    text = " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore")) for n in pages)
    text = html.unescape(re.sub(r"\s+", " ", text))
    toc = sum(len(re.findall(r"<navPoint", z.read(n).decode("utf-8", "ignore"))) for n in names if n.endswith(".ncx"))

    score, notes = 70, []
    if len(text) < 3000 and len(images) > 10:
        score, notes = 30, ["taranmış sayfa resimleri"]
    elif len(text) < 30000:
        score -= 20
        notes.append("çok kısa metin")
    if toc > 3:
        score += 15
    else:
        notes.append("içindekiler yok")
    if any("cover" in n.lower() for n in images):
        score += 10
    if mojibake_ratio(text[:200000]) > 2:
        score -= 25
        notes.append("bozuk Türkçe karakter")
    info.update(chars=len(text), toc=toc, score=score, notes=notes)
    return info


def analyze_pdf(full):
    if not HAS_POPPLER:
        return {"score": 50, "notes": ["pdf analizi için poppler kurulu değil"]}
    meta = subprocess.run(["pdfinfo", full], capture_output=True, text=True, errors="ignore", timeout=30).stdout
    get = lambda k: (re.search(rf"^{k}:\s*(.*)$", meta, re.M) or [None, ""])[1].strip()
    pages = int(get("Pages") or 0)
    text = subprocess.run(["pdftotext", "-l", "15", full, "-"], capture_output=True, text=True, errors="ignore", timeout=60).stdout
    per_page = len(text.strip()) / max(1, min(15, pages or 1))
    notes = []
    if per_page < 100:
        score = 15
        notes.append("taranmış, metin katmanı yok")
    elif re.search(r"ABBYY|FineReader|scan|Digitized|ClearScan|Sender|Canon|Xerox", meta, re.I):
        score = 40
        notes.append("taranmış + OCR")
    else:
        score = 65
    if mojibake_ratio(text) > 2:
        score -= 20
        notes.append("bozuk Türkçe karakter")
    if 0 < pages < 20:
        score -= 10
        notes.append(f"{pages} sayfa")
    author, title = get("Author"), get("Title")
    # PDF meta verisi çoğu zaman "Microsoft Word - x.doc" gibi çöp içerir
    junk = re.compile(r"microsoft|\.docx?$|\.indd|untitled|^www|^user$|^admin", re.I)
    return {
        "author": "" if junk.search(author) else author,
        "title": "" if junk.search(title) else title,
        "pages": pages, "chars": len(text), "score": score, "notes": notes,
    }


def analyze(root, rel):
    full = os.path.join(root, rel)
    st = os.stat(full)
    ext = rel.rsplit(".", 1)[-1].lower()
    author, title = name_meta(rel)
    row = {"root": root, "path": rel, "size": st.st_size, "mtime": st.st_mtime, "ext": ext,
           "author": "", "title": "", "publisher": "", "language": "", "year": "", "subjects": "",
           "description": "", "pages": 0, "chars": 0, "toc": 0, "score": 40, "notes": []}
    try:
        if ext == "epub":
            row.update(analyze_epub(full))
        elif ext == "pdf":
            row.update(analyze_pdf(full))
        elif ext in ("mobi", "azw", "azw3", "fb2", "cbz", "cbr"):
            row["score"] = 60
        else:
            row["notes"] = ["eski/ham biçim"]
    except Exception as e:  # bozuk dosya taramayı durdurmasın
        row.update(score=0, notes=[f"açılamıyor ({type(e).__name__})"])
    # dosya adı (kullanıcının düzenlediği) gömülü meta veriden daha güvenilir
    row["author"] = author or row["author"]
    row["title"] = title or row["title"]
    row["score"] = max(0, min(100, row["score"]))
    row["notes"] = ", ".join(row["notes"])
    return row


# ---------------------------------------------------------------- tarama

class Scanner:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"running": False, "done": 0, "total": 0, "root": None}

    def start(self, root):
        with self.lock:
            if self.state["running"]:
                return
            self.state = {"running": True, "done": 0, "total": 0, "root": root}
        threading.Thread(target=self._run, args=(root,), daemon=True).start()

    def _run(self, root):
        try:
            con = db()
            known = {r["path"]: (r["size"], r["mtime"]) for r in con.execute("SELECT path, size, mtime FROM files WHERE root=?", (root,))}
            found, todo = set(), []
            for d, dirs, files in os.walk(root):
                dirs[:] = [x for x in dirs if not x.startswith(".")]
                for f in files:
                    if f.startswith(".") or f.rsplit(".", 1)[-1].lower() not in BOOK_EXT:
                        continue
                    # arayüz ve veritabanı her sistemde "/" ayırıcı kullanır
                    rel = os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/")
                    found.add(rel)
                    st = os.stat(os.path.join(d, f))
                    if known.get(rel) != (st.st_size, st.st_mtime):
                        todo.append(rel)
            gone = set(known) - found
            con.executemany("DELETE FROM files WHERE root=? AND path=?", [(root, p) for p in gone])
            con.commit()
            self.state["total"] = len(todo)
            with ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
                for row in pool.map(analyze, [root] * len(todo), todo, chunksize=16):
                    con.execute(f"INSERT OR REPLACE INTO files ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
                    self.state["done"] += 1
                    if self.state["done"] % 100 == 0:
                        con.commit()
            con.commit()
            con.close()
        finally:
            self.state["running"] = False


scanner = Scanner()


# ---------------------------------------------------------------- yardımcılar

def open_path(path, reveal=False):
    system = platform.system()
    if system == "Darwin":
        cmd = ["open", "-R", path] if reveal else ["open", path]
    elif system == "Windows":
        cmd = ["explorer", "/select,", path] if reveal else None
        if not reveal:
            os.startfile(path)  # type: ignore[attr-defined]
            return
    else:
        cmd = ["xdg-open", os.path.dirname(path) if reveal else path]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def inside(root, rel):
    """Yolun seçili kök klasörün içinde kaldığını doğrular."""
    full = os.path.realpath(os.path.join(root, rel))
    return full if full.startswith(os.path.realpath(root) + os.sep) else None


def epub_cover(full):
    z = zipfile.ZipFile(full)
    names = z.namelist()
    images = [n for n in names if re.search(r"\.(jpe?g|png|gif|webp|svg)$", n, re.I)]
    try:
        container = z.read("META-INF/container.xml").decode("utf-8", "ignore")
        opf_path = re.search(r'full-path="([^"]+)"', container).group(1)
        opf = z.read(opf_path).decode("utf-8", "ignore")
        cid = re.search(r'<meta[^>]*name="cover"[^>]*content="([^"]+)"', opf) or re.search(r'<meta[^>]*content="([^"]+)"[^>]*name="cover"', opf)
        href = None
        if cid:
            m = re.search(rf'<item[^>]*id="{re.escape(cid.group(1))}"[^>]*href="([^"]+)"', opf) or \
                re.search(rf'<item[^>]*href="([^"]+)"[^>]*id="{re.escape(cid.group(1))}"', opf)
            href = m and m.group(1)
        if not href:
            m = re.search(r'<item[^>]*properties="cover-image"[^>]*href="([^"]+)"', opf) or \
                re.search(r'<item[^>]*href="([^"]+)"[^>]*properties="cover-image"', opf)
            href = m and m.group(1)
        if href:
            cand = os.path.normpath(os.path.join(os.path.dirname(opf_path), href)).replace("\\", "/")
            if cand in names:
                return z.read(cand), cand
    except (KeyError, AttributeError):
        pass
    covers = [n for n in images if "cover" in n.lower()] or images
    if covers:
        best = max(covers, key=lambda n: z.getinfo(n).file_size) if not any("cover" in n.lower() for n in covers) else covers[0]
        return z.read(best), best
    return None, None


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, body, ctype="application/json; charset=utf-8", code=200, headers=None):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def root(self):
        return load_conf().get("root")

    def allowed(self, q=None):
        """Host başlığı (DNS rebinding) ve oturum anahtarı (CSRF) denetimi."""
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return False
        token = self.headers.get("X-Kitaplik-Token") or (q or {}).get("t")
        return secrets.compare_digest(token or "", TOKEN)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path.startswith("/api/") and not self.allowed(q):
            return self.send({"error": "yetkisiz"}, code=403)
        if url.path in ("/", "/index.html"):
            if not self.allowed(q):
                return self.send(b"Yetkisiz", "text/plain; charset=utf-8", 403)
            return self.send((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/state":
            return self.send({"root": self.root(), "scan": scanner.state, "poppler": HAS_POPPLER, "version": __version__})
        if url.path == "/api/browse":
            path = q.get("path") or self.root() or str(Path.home())
            path = os.path.abspath(os.path.expanduser(path))
            try:
                dirs = sorted((d.name for d in os.scandir(path) if d.is_dir() and not d.name.startswith(".")), key=str.lower)
            except OSError as e:
                return self.send({"error": str(e)}, code=400)
            return self.send({"path": path, "parent": os.path.dirname(path), "dirs": dirs})
        if url.path == "/api/files":
            root = self.root()
            if not root:
                return self.send([])
            con = db()
            tags = {}
            for r in con.execute("SELECT path, tag FROM tags WHERE root=?", (root,)):
                tags.setdefault(r["path"], []).append(r["tag"])
            favs = {r["path"] for r in con.execute("SELECT path FROM favorites WHERE root=?", (root,))}
            rows = []
            for r in con.execute("SELECT * FROM files WHERE root=?", (root,)):
                d = dict(r)
                del d["root"]
                d["tags"] = sorted(tags.get(d["path"], []))
                d["fav"] = d["path"] in favs
                rows.append(d)
            con.close()
            return self.send(rows)
        if url.path == "/api/cover":
            root = self.root()
            full = root and inside(root, q.get("path", ""))
            if not full or not full.lower().endswith(".epub"):
                return self.send(b"", "text/plain", 404)
            try:
                data, name = epub_cover(full)
            except Exception:
                data = None
            if not data:
                return self.send(b"", "text/plain", 404)
            ext = name.rsplit(".", 1)[-1].lower()
            # kapak kitabın içinden gelir, güvenilmez: SVG içindeki betikler hiçbir koşulda çalışmasın
            return self.send(data, {"jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}.get(ext, f"image/{ext}"),
                             headers={"Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
                                      "Content-Disposition": f"inline; filename=cover.{ext}"})
        self.send({"error": "bulunamadı"}, code=404)

    def do_POST(self):
        url = urlparse(self.path)
        # JSON içerik türü zorunlu: tarayıcılar bunu CORS ön kontrolü olmadan gönderemez
        if not self.allowed() or not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self.send({"error": "yetkisiz"}, code=403)
        data = self.body()
        root = self.root()
        if url.path == "/api/root":
            path = os.path.abspath(os.path.expanduser(data.get("path", "")))
            if not os.path.isdir(path):
                return self.send({"error": "klasör yok"}, code=400)
            conf = load_conf()
            conf["root"] = path
            save_conf(conf)
            scanner.start(path)
            return self.send({"ok": True})
        if url.path == "/api/scan":
            if root:
                scanner.start(root)
            return self.send({"ok": True})
        if url.path == "/api/open":
            full = root and inside(root, data.get("path", ""))
            if not full or not os.path.exists(full):
                return self.send({"error": "dosya yok"}, code=404)
            open_path(full, bool(data.get("reveal")))
            return self.send({"ok": True})
        if url.path == "/api/tags":
            con = db()
            paths = data.get("paths", [])
            for tag in data.get("add", []):
                tag = tag.strip()
                if tag:
                    con.executemany("INSERT OR IGNORE INTO tags VALUES (?,?,?)", [(root, p, tag) for p in paths])
            for tag in data.get("remove", []):
                con.executemany("DELETE FROM tags WHERE root=? AND path=? AND tag=?", [(root, p, tag) for p in paths])
            con.commit()
            con.close()
            return self.send({"ok": True})
        if url.path == "/api/tag-admin":
            # etiketi tüm kitaplarda yeniden adlandır (hedef varsa birleşir) ya da sil
            action, tag, to = data.get("action"), data.get("tag", ""), (data.get("to") or "").strip()
            con = db()
            if action == "rename" and to and to != tag:
                con.execute("INSERT OR IGNORE INTO tags SELECT root, path, ? FROM tags WHERE root=? AND tag=?", (to, root, tag))
                con.execute("DELETE FROM tags WHERE root=? AND tag=?", (root, tag))
            elif action == "delete":
                con.execute("DELETE FROM tags WHERE root=? AND tag=?", (root, tag))
            con.commit()
            con.close()
            return self.send({"ok": True})
        if url.path == "/api/fav":
            con = db()
            rows = [(root, p) for p in data.get("paths", [])]
            if data.get("on"):
                con.executemany("INSERT OR IGNORE INTO favorites VALUES (?,?)", rows)
            else:
                con.executemany("DELETE FROM favorites WHERE root=? AND path=?", rows)
            con.commit()
            con.close()
            return self.send({"ok": True})
        self.send({"error": "bulunamadı"}, code=404)


def gtk_window(url):
    """Linux: sistemde kurulu GTK + WebKit ile yerel pencere (ek kurulum gerekmez)."""
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    # dock'ta menüdeki kısayolla eşleşsin (StartupWMClass=kitaplik)
    GLib.set_prgname("kitaplik")
    GLib.set_application_name("Kitaplık")
    win = Gtk.Window(title="Kitaplık")
    icon = RES_DIR / "kitaplik.svg"
    if icon.exists():
        win.set_icon_from_file(str(icon))
    win.set_default_size(1400, 860)
    view = WebKit2.WebView()
    view.load_uri(url)
    win.add(view)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


def pywebview_window(url):
    """macOS (ve pywebview kuruluysa diğer sistemler): yerel WebKit penceresi."""
    import webview
    webview.create_window("Kitaplık", url, width=1400, height=860)
    webview.start()


def show_window(url):
    attempts = [pywebview_window] if platform.system() == "Darwin" else [gtk_window, pywebview_window]
    for attempt in attempts:
        try:
            attempt(url)
            return
        except (ImportError, ValueError):
            continue
    print("Yerel pencere açılamadı (macOS'ta: pip3 install pywebview). Tarayıcıda açılıyor.")
    webbrowser.open(url)
    threading.Event().wait()


def log(msg):
    # konsolsuz paketlenmiş uygulamalarda (Windows --windowed) stdout yoktur;
    # KITAPLIK_LOG verilirse mesajlar o dosyaya da yazılır
    if sys.stdout:
        print(msg, flush=True)
    if os.environ.get("KITAPLIK_LOG"):
        with open(os.environ["KITAPLIK_LOG"], "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def selftest():
    """Pencere açmadan uçtan uca dener: derleme sunucusunda paketin çalıştığını doğrular."""
    import tempfile
    import time
    import urllib.request

    lib = tempfile.mkdtemp(prefix="kitaplik-test-")
    os.makedirs(os.path.join(lib, "Roman"))
    with zipfile.ZipFile(os.path.join(lib, "Roman", "Yazar Adı - Deneme Kitabı.epub"), "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="c.opf"/></rootfiles></container>')
        z.writestr("c.opf", "<package><metadata><dc:title>Deneme</dc:title><dc:language>tr</dc:language></metadata></package>")
        z.writestr("ch1.xhtml", "<html><body>" + "Merhaba dünya. " * 3000 + "</body></html>")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    headers = {"X-Kitaplik-Token": TOKEN, "Content-Type": "application/json"}

    def call(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        with urllib.request.urlopen(urllib.request.Request(base + path, data, headers)) as r:
            return r.read()

    conf = load_conf()
    try:
        assert b"Kitapl" in call(f"/?t={TOKEN}"), "arayüz yüklenmedi"
        call("/api/root", {"path": lib})
        for _ in range(100):
            if not json.loads(call("/api/state"))["scan"]["running"]:
                break
            time.sleep(0.1)
        files = json.loads(call("/api/files"))
        assert len(files) == 1, f"beklenen 1 kitap, bulunan {len(files)}"
        f = files[0]
        assert f["path"] == "Roman/Yazar Adı - Deneme Kitabı.epub", f["path"]
        assert f["author"] == "Yazar Adı" and f["score"] >= 40, f
        call("/api/fav", {"paths": [f["path"]], "on": True})
        assert json.loads(call("/api/files"))[0]["fav"], "favori kaydedilmedi"
        if platform.system() != "Linux":
            import webview  # noqa: F401  paketlenmiş uygulamada pencere kütüphanesi olmalı
    finally:
        save_conf(conf)  # kullanıcının seçili klasörünü geri koy
        con = db()
        for table in ("files", "tags", "favorites"):
            con.execute(f"DELETE FROM {table} WHERE root=?", (os.path.abspath(lib),))
        con.commit()
        con.close()
        shutil.rmtree(lib, ignore_errors=True)
    log(f"Kitaplık {__version__} selftest: OK")


def main():
    if "--version" in sys.argv:
        log(__version__)
        return
    if "--selftest" in sys.argv:
        try:
            selftest()
        except BaseException as e:  # hata penceresi açılmasın, çıkış koduyla bildir
            import traceback
            log(f"selftest HATA: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            os._exit(1)
        os._exit(0)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        # sabit port doluysa rastgele bir port kullan
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    root = load_conf().get("root")
    if root and os.path.isdir(root):
        scanner.start(root)  # değişen dosyaları güncelle
    url = f"http://127.0.0.1:{server.server_address[1]}/?t={TOKEN}"
    try:
        if "--headless" in sys.argv:
            threading.Event().wait()
        elif "--browser" in sys.argv:
            webbrowser.open(url)
            threading.Event().wait()
        else:
            show_window(url)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    # paketlenmiş uygulamada çoklu işlemci taraması için gerekli
    import multiprocessing
    multiprocessing.freeze_support()
    main()
