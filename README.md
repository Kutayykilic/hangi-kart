# Hangi Kart?

Harcamanı yaz ("Migros'ta 1500 TL market"), Akbank (Axess, Akbank Mobil, Wings), QNB, DenizBank / Maximum kampanyalarından
hangisinin ne kadar kazandıracağını sıralasın.

## Çalıştırma

```bash
python3 server.py        # http://localhost:8000
```

İlk açılışta kampanyalar otomatik çekilir. Sonra sayfanın altındaki "Kampanyaları güncelle" ile
ya da elle `python3 scraper/scrape.py` ile yenilenir. Gereken paketler: `requests`, `beautifulsoup4`.

## Yapı

- `scraper/scrape.py` – kaynaklar:
  - Axess: `axess.com.tr/ajax/kampanya-ajax.aspx` (kategori bazlı, sayfalı; önce oturum çerezi alınmalı)
  - DenizBank: `denizbank.com/api/campaign/search` (JSON)
  - Maximum: `maximum.com.tr/kampanyalar` JSON-LD içindeki `Offer` kayıtları. DenizBank kartları
    6 Aralık 2026'da Maximum altyapısına geçiyor, bu yüzden dahil.
- `scraper/extract.py` – kampanya metninden regex ile tarih, kazanç (TL / % / her X TL'ye Y TL),
  min. harcama, katılım yöntemi (SMS anahtar kelimesi vb.) ve indirim kodu çıkarır.
- `web/` – arama, eşleştirme ve kazanç tahmini tarayıcıda (`app.js`).
- `server.py` – statik dosyalar + `/api/refresh`.

Tahminler sezgiseldir; kampanya metnini kontrol etmeden harcama yapma.

## Yayın ve otomatik güncelleme

`.github/workflows/update.yml` her gün 07:00'de (TR) kampanyaları çeker, `data/campaigns.json`'u
repoya kaydeder ve `web/` + veriyi GitHub Pages'e yayınlar. Elle tetiklemek için: `gh workflow run update.yml`.
Çekilen kampanya sayısı 100'ün altındaysa (ör. bankalar IP'yi engellerse) eski veri korunur.

Site bir PWA'dır: iPhone'da Safari → Paylaş → "Ana Ekrana Ekle", Android'de Chrome → "Uygulamayı yükle".
