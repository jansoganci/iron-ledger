# Kalan işler

*9 Ekim 2026. Kaynak: güncel `main` (`c93ca0e`) + canlı Supabase kontrolü.
Kâr tablosu tutarı, GL varsa GL'dir; destek dosyası üstüne eklenmez.
Claude matematik yapmaz.*

Tek canlı backlog burasıdır. Ayrı bir “Documents” listesi açılmaz.
Bitmiş planları buraya geri kopyalama.

**Çalışma kuralı:** tek seferde bir madde, yukarıdan aşağı.
Bir maddenin “Bitti” satırı geçmeden sonrakine geçilmez.
Madde bitince bu dosyada “yapıldı” olur.
Commit, bu turdaki kod işleri bitince bir kez atılır.
Çelişince kod kazanır.

**Sıra (değişmez):** aşağıdaki ürün işi → canlı Supabase SQL en son
(uygulayan insan; `supabase db push` yok) → Cloudflare en son.

---

## Sıradaki iş — tek tek

### 1. Kod stili — son iki satır

`backend/adapters/anthropic_llm.py` satır 59 ve 74 hâlâ 88 karakterden uzun.
Bu dosyaya düzenleme, yerel “inline prompt” hook’u geçersiz JSON döndürdüğü
için editörde engelleniyor. Hook düzelince iki satır bölünür; davranış değişmez.

Pre-push yalnız pytest çalıştırıyor (black/flake8 yok).

---

## Bilinen, şimdi yapılmaz

Çok dosyalı run’da Retry yalnız ilk dosyayı tek dosyalık akışla yeniden
çalıştırır (`uploads.py` `run_retry` → `run_parser_until_preview`,
`storage_key` = ilk anahtar). Tüm anahtarlar `parse_preview.file_keys`
içinde duruyor. Düzeltme ayrı iş; temizlikle karıştırılmaz.

Canlı `account_categories` tablosunda RLS açık ve policy yok.
`0001` bu tabloyu RLS’siz kamu araması sayar. Frontend tabloyu doğrudan okumuyor.
Servis rolü RLS’ten geçtiği için bugünkü close bozulmuyor.
Açmadan önce kim okuyor, ona bakılır.

---

## Yapıldı — yeniden açma

- Kod stili (9 Ekim 2026, ayrı commit). `.flake8` black ile aynı: 88 sütun,
  E203 yok sayılır. `black --check backend tests` temiz; `flake8` 900 → 2
  (yalnız `anthropic_llm.py`). Kullanılmayan importlar silindi,
  `supabase_repos.py` importları başa alındı, uzun satırlar bölündü.
  Davranış aynı: değişen her dosyanın AST’i commit öncesiyle karşılaştırıldı.
- 7 günlük upload temizliği (9 Ekim 2026). Klasör (`kullanıcı/ay`) bazında:
  o şirket ve ayın en yeni run’ı 7 günden eskiyse klasördeki tüm dosyalar
  silinir; çok dosyalı yüklemenin artıkları da gider. Uygulama içinde,
  açılıştan 60 sn sonra ve günde bir. Silmeden önce ikinci okuma; bozuk
  veya kök adres reddedilir; okunamayan zaman damgası saklar; logda yalnız
  sayılar. Süresi dolan dosyada onay/Retry `UPLOAD_EXPIRED` der.
  Migration yok (`runs.updated_at` zaten var).
- `500k_plus` dolar kapıları bant tabanından (9 Ekim 2026): `R = $500,000`,
  kapılar $12,500 / $2,500. 250k–500k bandından düzgün devam eder.
  Bant seçmemiş şirket $50k / $10k güvenli varsayılanında kalır.
  Yeni bant, migration, API değişmedi. Yeni bant: ilk gerçek $1M+ müşteride.
- Yüzde eşikleri kararı (9 Ekim 2026): %10 / %3 sabit kalır, banda göre
  değişmez. Ölçeklenen kısım dolar kapısıdır.
- Genel “missing journal entry” cümlesi (9 Ekim 2026): hiçbir kart
  `missing_je` değilken olumsuzlanmamış ifade reddedilir, bir kez yeniden
  denenir, ikinci seferde rapor yazılmaz. Karar son kart sınıfına göredir
  (Claude’un birleştirmede ezilen sınıfı saymaz). Opus yükseltmesi de aynı.
- İşlemci ücreti yalnız settlement dosyasında ve GL’nin altında yanar
  (9 Ekim 2026). Bant %3–8 durur. Tedarikçi dosyasındaki aynı yüzde
  `stale_reference` kalır. Settlement GL’den büyükse ücret sayılmaz.
- Ay kapanışı yazımdan hemen önce bir kez daha okunur (9 Ekim 2026).
  Karşılaştırma anomalileri değiştirmez, rapor yazılmaz, Opus yayınlamaz.
  `RunStatus` listesine yeni durum eklenmedi. Çeyrek rapor kilide girmez.
- Kapalı ayda Retry zaten 409 ve düz mesaj
  (`test_closed_month_refuses_replace_upload_and_retry_and_writes_nothing`).
  Canlıda sahte başarısız rapor üretilmedi.
- Migrasyon `0010` canlıda duruyor. Dosyası yeniden yazılmaz.
- `compute_hints` hata yolu sessiz boş ipucu değil (9 Ekim 2026).
  `hints_unavailable` başarılı “özel bir şey yok” sonucundan ayrıdır.
  Run düşmez. Sınıf `stale_reference` olmaz. Logda hata tipi var, hücre yok.
  Tarih sütunundaki dar `except` duruyor.
- Data sayfası yılbaşından bugüne tablosu (`c93ca0e`, 9 Ekim 2026).
  Sunucu GL’den Decimal ile hesaplar. Boş ay “—” ve toplama girmez.
  Chrome: Redhawk 2026, Haziran’a kadar. Mayıs geliri $35,890.00, net kâr $2,810.00.
- Üç Dil 2 hatası (`bdaaf7b`, 3 Ekim 2026): boş bordro çökmez,
  bir kontrole iki dosya sahte fark göstermez, kapalı ay düz mesaj verir.
- Migrasyon `0013` canlıda uygulı (9 Ekim 2026 okuma). Bordro eşlemesi hatırlanır.
- Sözleşme dosyası toplamı hatırlanır; kayıtlı eşleşmelerin kendi sayfası var (`6c73423`).
- Dönem kilidi (`96cf24e`, `0012` canlıda). Retry kenarı madde 8’de.
- Anlatı–kart kelime kontrolü (1 Ekim 2026). Genel cümle kuralı 9 Ekim’de eklendi.
- Sekme gizliyken yoklama, yenilemede bekleyen run, Excel kaynak sütunu (`a5ee407`).
- TrueCost adı, kapalı kayıt, Railway/Cloudflare yüzeyi (`origin/main`, 7 Ekim 2026).
- Aynı dönemi yeniden üretme, kalıcı kaynak eşlemeleri (`0011`),
  uydurma classification token, guardrail Stage 1, Dil 1, çeyrek rapor.

---

## Parkta — tetikleyici gelmeden açma

| İş | Tetikleyici |
|---|---|
| Truck stock / van inventory (Kova Item 2) | Gerçek count-vs-GL workbook |
| Central-station tahakkuk (Item 3) | Bayiden central-station faturası (Item 4 bitti) |
| WIP / professional services (Item 6) | O dikeye satış kararı |
| pgvector, ERP API, multi-user, budget vs actuals, draft JE | Post-MVP |
| Redis rate-limit, mypy strict, CI/CD, çok alıcılı mail | Post-MVP |
| Banka satır eşleştirme, 7. sınıf, Claude’un N/M sayması | Bilinçli yasak |

Detay spec: `docs/sprint/kova2-implementation-plan.md` (Item 2 / 3 / 6).
