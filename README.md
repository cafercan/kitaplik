# Kitaplık

Seçilen bir klasör altındaki e-kitaplar (EPUB, PDF, MOBI, DJVU, DOC…) için küçük bir masaüstü uygulaması:

- **Meta bilgi:** yazar, başlık, yayınevi, dil, yıl, konu, açıklama, kapak, sayfa/karakter sayısı
- **Kalite puanı (0–100):** metin tabanlı mı, taranmış mı, OCR var mı, içindekiler/kapak, bozuk Türkçe karakter
- **Etiketleme:** tek tek ya da çoklu seçimle toplu etiket ekleme/çıkarma
- **Filtreleme:** arama, klasör, etiket, biçim, puan aralığı, kalite notları
- **Aç:** dosyayı sistemin varsayılan uygulamasında açar ya da klasörde gösterir
- Son seçilen klasör hatırlanır; açılışta yalnızca değişen dosyalar yeniden taranır.

Yalnızca Python 3 standart kütüphanesini kullanır. Arayüz yerel bir pencerede açılır.

## Çalıştırma

**Linux** (GTK + WebKit2GTK 4.1, Ubuntu'da varsayılan olarak kurulu):

```bash
python3 kitaplik.py
./install-linux.sh   # ~/.local/share/kitaplik/app altına kurar, menüye ekler
```

**macOS:** `Kitaplik.command` dosyasına çift tıklayın (ilk açılışta `pywebview` kurulur) ya da:

```bash
pip3 install --user pywebview
python3 kitaplik.py
```

PDF analizi için `pdfinfo`/`pdftotext` gerekir: Linux'ta `poppler-utils`, macOS'ta `brew install poppler`.

Seçenekler: `--browser` (pencere yerine tarayıcıda aç), `--headless` (yalnızca sunucu).

## Klavye

`↑ ↓` gezin · `Enter` aç · `Space` seç · `/` aramaya git

## Veriler

Ayarlar ve etiketler `~/.config/kitaplik/` altında (`config.json`, `kitaplik.db`) saklanır;
kitap dosyalarına dokunulmaz. Etiketler dosyanın klasöre göre yoluna bağlıdır; bir dosya
uygulama dışında taşınır ya da yeniden adlandırılırsa etiketi kaybolur.
