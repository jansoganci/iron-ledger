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

### 1. Başarısız analiz dosyaları

Complete sonrası storage temizliği var. `guardrail_failed` dosyası
Retry için duruyor ve hiç süpürülmüyor.

Bitti: Retry hâlâ dosyayı bulur. Terk edilmiş başarısız run’ın dosyası
belirli bir süre sonra silinir. Silme, kullanıcının açık Retry’sini bozmaz.
Logda dosya içeriği yok.

Yapma: başarısız olur olmaz silme. Complete temizliğini bu işe bağlayıp
başarılı run’ın dosyasını erken silme.

### 2. Yüzde eşikleri

Dosya: `backend/agents/comparison.py`.
Dolar kapıları banda göre (`_gates_from_band`).
`_TIER1_PCT = 10` ve `_TIER2_PCT = 3` sabit.

Bitti: ancak sen yüzde kapılarının da banda göre değişeceğine karar
verirsen. Karar yoksa bu madde açılmaz. Karar sonrası pandas hesaplar,
Claude sayıları görmez, dolar kapılarına dokunulmaz, test eski ve yeni
bandı birlikte kanıtlar.

Yapma: 10 ve 3’ü kendin değiştirme.

### 3. `500k_plus` üst sınırı

Dört bant var. `500k_plus` tavanı `$2_000_000` varsayılanıyla hem
500 bin hem 5 milyona aynı dolar kapısını verir
(`backend/agents/comparison.py`, `backend/api/routers/companies.py`).

Bitti: ancak sen yeni bandı veya tavanı seçersen. Seçim yoksa kod yazılmaz.
Seçim olursa kolon, API literal, migration ve test birlikte gider.
Uygulanmış `0010` dosyası yeniden yazılmaz; yeni numaralı migration açılır.

Yapma: bant adını veya `$2_000_000` rakamını kendin uydurma.

### 4. Anlatı kontrolünün sınırı

`narrative_check.py` kelimeye bakar. Hesap adını anmayan genel cümle
“missing journal entry” dese de yakalanmaz. Kelime kuralı bilinçli sınırdır.

Bitti: ancak yakalanması gereken cümle örnekle sabitlenirse.
Guardrail toleransı gevşetilmez. LLM kendi cümlesini sayı diye onaylamaz.

Yapma: bu maddeyi “rapor düzeltmesi” sanıp sayıları prompt’a hesaplatma.

### 5. Kod stili

`black` 5 dosyayı yeniden biçimlendirmek istiyor.
`flake8` çoğunlukla satır uzunluğu, yüzlerce uyarı.
Pre-push yalnız pytest çalıştırıyor.

Bitti: biçim commit’i davranışı değiştirmez. Finans hesabı aynı testlerle geçer.

Yapma: stil düzeltmesini davranış değişikliğiyle aynı commit’e koyma.

---

## Bilinen, şimdi yapılmaz

Canlı `account_categories` tablosunda RLS açık ve policy yok.
`0001` bu tabloyu RLS’siz kamu araması sayar. Frontend tabloyu doğrudan okumuyor.
Servis rolü RLS’ten geçtiği için bugünkü close bozulmuyor.
Açmadan önce kim okuyor, ona bakılır.

---

## Yapıldı — yeniden açma

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
- Anlatı–kart kelime kontrolü (1 Ekim 2026). Genel cümle sınırı madde 7’de.
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
