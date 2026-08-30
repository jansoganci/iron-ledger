# Ay Sonu Kapanış: Sektör Süreçleri ve Başlangıç Sektörü

*Month Proof ürün araştırması — 24 Ağustos 2026.*  
*Amaç: ürünü pivot etmeden, mevcut close akışını gerçek 4–5 günlük kapanışa tamamlamak.*  
*Kaynak: ABD SMB close pratikleri (QuickBooks / FloQast / CPA checklist) + sektör literatürü + mevcut kod tabanı.*

---

## Karar (kısa)

**Pivot yok.** Mevcut motor (Excel/CSV → GL ile kaynaklar arası mutabakat → flux anlatısı → guardrail) durur.

**Başlangıç sektörü: saha hizmeti** (kurulum + abonelik/izleme — güvenlik, HVAC, tesisat). 5–40 kişi, QuickBooks, ofis müdürü / fractional controller, 4–5 günde owner’a paket.

**İkinci sektör:** profesyonel hizmet / IT danışmanlık (timesheet + retainer). Aynı omurga, bir yargı satırı fazla.

**Şimdi girilmez:** SaaS (ASC 606 şelalesi), üretim (stok/WIP), inşaat (WIP çizelgesi). Bunlar ayrı motor ister; girmek pivot olur.

Süreç “garip” çünkü ürün close’un **sonuna** (yorum) oturmuş. Gerçek kapanış **baştan** gider: nakit → alt defter vs GL → tahakkuk → flux → kilit.

---

## 1. Her sektörde aynı omurga

Sıra tesadüf değil. Sonraki adımda bulunan hata, öncekini yeniden yaptırır. ABD SMB close (Catalyst CPA 2026 checklist, FloQast/BlackLine disiplin, QuickBooks closing date) aynı kapılardan geçer.

### Gün 0 — Kesim (cutoff)

Ayın son 1–2 iş günü. Fatura, gider raporu, timesheet, tamamlanan iş bu tarihe kadar girilir. Atlanırsa 3. günde eksik fatura çıkar. SMB’de bu genelde bir e-posta setidir.

### Gün 1 — Nakit

Banka + kredi kartı ekstresi, GL nakit hesabına kuruşuna eşitlenir. Stripe/Shopify varsa merchant/payout hesabı da. CPA pratikte kural: nakit doğru değilse gerisi yanlıştır.

Month Proof **bilinçli olarak** banka satır eşleştirme yapmaz (ayrı ürün; şemayı bozar). Close’u yalan söylememek için pakette sınır yazılır: banka/kart mutabakatı araç dışında tamamlandı, controller teyit etti.

### Gün 2 — Alt defter = GL

Her kontrol hesabı dış kaynağa bağlanır, kuruşuna:

- AR aging toplamı = GL alacak
- AP aging toplamı = GL borç
- Bordro kaydı (Gusto / ADP / Paychex) = GL maaş + işveren vergisi
- Fatura / iş kaydı = GL gelir

Bu, ürünün asıl otomasyon yüzeyi: **dosya toplamı vs GL satırı.**

### Gün 3 — Tahakkuk, erteleme, reclass

Fatura yok ama gider bu aya ait → tahakkuk. Yıllık yazılım peşin → prepaid (aylık dilim). Yanlış hesaba gitmiş tutar → reclass. Burası yargı; ajan hesaplamaz, açık madde üretir. Önceki ayın timing farkı bu ay dönmeli; dönmediyse hata.

### Gün 4 — Flux (varyans)

Ön trial balance + P&L. Satır satır geçen ay ve/veya bütçe. Material sapmaya yazılı yorum. Ürünün bugün yaptığı iş **burası.** Close’un son %20’si; ilk %80 bitmeden yazılırsa güvenilmezdir.

### Gün 5 — Paket ve kilit

P&L, bilanço, AR/AP aging, açık maddeler, imza. QuickBooks’ta closing date + şifre. Close rapor yazılınca bitmez; dönem kilitlenip paket gidince biter.

```
Gün 0 kesim
    → Gün 1 nakit
        → Gün 2 alt defter vs GL
            → Gün 3 tahakkuk / reclass
                → Gün 4 flux yorumu
                    → Gün 5 paket + kilit
```

Dört değişmez:

1. Sıra: nakit → alt defter → tahmin → analiz → kilit.
2. Her bilanço hesabı ya dış kaynağa bağlanır ya roll-forward çizelgesiyle açıklanır.
3. Her material P&L satırının yazılı nedeni vardır.
4. Close, geri alınamayan bir işle bitir: dönem kilidi + dağıtılmış paket.

---

## 2. Sektörler: ne değişiyor?

Ortak omurga üstüne her sektör **bir zor iş** ekler. Otomasyon sorusu: o iş Excel-vs-GL ile çözülüyor mu, yoksa ayrı motor mu istiyor?

### Saha hizmeti — kurulum + izleme (başlangıç)

**Zor kısım.** İki gelir, iki mekanik. Tek seferlik kurulum: müşteri depozitosu (sık %50 peşin / %50 teslim), “bu ay hangi iş bitti?” kesimi. Aylık izleme/bakım: elle tutulan müşteri listesi. Teknisyen bordrosu: mesai, on-call, iş başı prim. Kamyondaki parça çoğu SMB’de sayılmaz, alımda gider yazılır.

**Inbox.** QuickBooks GL/TB. Field-service export (ServiceTitan, Jobber, Housecall Pro). Sözleşme Excel’i (müşteri, plan, aylık ücret, aktif?). Gusto/ADP bordro. Tedarikçi faturaları (PDF’den elle Excel). Yakıt kartı. Banka/kart.

**Controller ne yapar.** İş kaydını GL gelirle toplar; faturalanmamış tamamlanmış işi kovalar. Aktif sözleşmeleri toplayıp GL izleme geliriyle karşılaştırır — fark genelde iptal müşteri hâlâ “aktif.” Bordroyu GL maaşla karşılaştırır; on-call primi Contractor’a gitmiş çıkar. Tedarikçi toplamını COGS ile karşılaştırır. Açık kurulumlarda depozitoyu gelirden ayırır.

**Dosya-vs-GL.** Neredeyse tamamı. Sözleşme vs GL = `stale_reference`. Tedarikçi vs COGS = `missing_je` / tahakkuk. İş kaydı vs kurulum geliri = `timing_cutoff`. Bordro vs maaş = `categorical_misclassification` (eksik tutar başka hesapta durur).

**Motor / yargı.** İş bazlı WIP, kamyon stoğu, eyalet satış vergisi, depozito-vs-gelir kararı (araç deseni gösterir; insan karar verir).

### Profesyonel hizmet / IT danışmanlık (ikinci)

**Zor kısım.** Faturalanmamış iş: Mart çalışıldı, Nisan fatura — tahakkuk + tahsil edilebilirlik yargısı. Timesheet × tarife ≠ fatura (write-down normal). Retainer peşindir, yükümlülüktür; teslim edilince gelire döner. Taşeron faturaları geç gelir. Yıllık SaaS faturası peşin gider yazılmış olabilir.

**Inbox.** GL. Harvest/Toggl/PSA timesheet. Fatura kaydı + AR aging. Gusto. Taşeron Excel’i (Paid Y/N). Retainer listesi. SaaS abonelik listesi. T&E. Banka/kart.

**Dosya-vs-GL.** Timesheet vs GL gelir (deltayı araç sınıflar; unbilled/write-off ayrımını insan yapar). Retainer vs GL = `stale_reference`. Bordro vs GL = misclassification. Taşeron vs GL = `missing_je`. SaaS listesi vs GL yazılım = `accrual_mismatch` (`delta × 12` ipucu kodda var).

**Motor / yargı.** Unbilled vs write-off. Sabit ücrette yüzde tamamlanma. Çok unsurlu işte ASC 606.

### E-ticaret / çok kanallı perakende

**Zor kısım.** Her payout net’tir: brüt − iade − komisyon − reklam tek satır. Amazon 14 günlük settlement ayla denk gelmez; her ay timing vardır. Asıl close: SKU maliyeti, landed cost, FBA yoldaki stok, fire, fiziki sayım. Bu ölçekte COGS sık ay sonu “plug.”

**Inbox.** Shopify/Amazon settlement, Stripe/PayPal, 3PL, Meta/Google reklam, tedarikçi/navlun, stok raporu, satış vergisi, GL, banka.

**Dosya-vs-GL.** Kanal settlement vs GL gelir/ücret. Reklam vs GL. Settlement’ın ayı aşması = timing.

**Neden sonra.** Stok/COGS close’un en büyük kalemi ve ayrı motor. A2X / Bookkeep / Link My Books payout’u API ile QuickBooks’a basıyor; kirli departman Excel avantajı burada zayıf.

### SaaS / abonelik

**Zor kısım.** Close = ertelenmiş gelir şelalesi (ASC 606). Yıllık peşin nakit P&L’ye o ay yazılmaz. Stripe deposit ≠ gelir (ücret, iade, dönem kayması). Rollforward: açılış + faturalama − tanınan = kapanış, şelale ve GL ile kilitlenir.

**Neden şimdi değil.** Şelale, SSP tahsisi, komisyon kapitalizasyonu (ASC 340-40) ürün kapsamında yok. Dosya-vs-GL sadece gider tarafını (en az acıyan kısım) tutar.

### Üretim

**Zor kısım.** Hammadde → WIP → mamul → COGS. Standart maliyet sapmaları, overhead yansıtma, üç stok kovası, fire. P&L üretim hacmine de bağlıdır, sadece satışa değil. Finance, operasyon kapanmadan kapatamaz.

**Neden şimdi değil.** Acıyan kısım ERP. Kirli Excel varsayımını kırar. Vendor/bordro vs GL close’un belki beşte biri.

### İnşaat

**Zor kısım.** Close = WIP çizelgesi. Harcanan / tahmini toplam × sözleşme = hak edilen gelir. Fazla/eksik fatura bilançoya gider. PM her ay “bitirme maliyeti” günceller — bu bir toplantı. Retainage, change order, surety/banka paketi. Süre 10–20 gün.

**Neden şimdi değil.** Messy Excel gerçek; teslimat yüzde-tamamlanma çizelgesi. Mutabakat yapılır, close bitmez.

### Klinik (hafif)

**Zor kısım.** Gelir = brüt − sözleşmesel sigorta indirimi (yargı). Bir EFT onlarca claim. Dosya-vs-GL teknik olarak uyar.

**Neden şimdi değil.** HIPAA. İlk satış konuşmasında BAA (Anthropic alt işlemci dahil) istenir. Pre-revenue üründe kapı, özellik değil.

### STK (hafif)

**Zor kısım.** Fon/kısıt boyutu, 990 için fonksiyonel gider dağılımı, bağış koşulluluğu. CRM bağış toplamı vs GL iyi bir mutabakat.

**Neden şimdi değil.** Kısıt/fon şemada yok. Teslimat board paketi + functional expense, flux anlatısı değil. Alıcı yavaş ve fiyata duyarlı; çoğu aylık değil çeyreklik kapatır.

---

## 3. Bu ürüne göre sıralama

Kriterler genel pazar değil, Month Proof’a özel:

- (a) Departmandan kirli Excel geliyor mu
- (b) Asıl acı GL vs kaynak dosya mı
- (c) Ağır stok / WIP / ASC 606 motoru gerekmiyor mu
- (d) ABD SMB 5–40 kişi, QuickBooks
- (e) Tek kişi 4–5 günde müdüre paket

(c) eleme kriteri: close’un kalbi inşa etmediğimiz motorsa, mutabakat ne kadar iyi olursa olsun kapanış bitmez.

| Sıra | Sektör | a | b | c | d | e | Toplam |
|------|--------|---|---|---|---|---|--------|
| 1 | Saha hizmeti | 5 | 5 | 4 | 5 | 5 | 24 |
| 2 | Profesyonel hizmet | 5 | 5 | 3 | 5 | 5 | 23 |
| 3 | Klinik | 4 | 4 | 4 | 4 | 3 | 19 |
| 4 | STK | 4 | 4 | 4 | 3 | 3 | 18 |
| 5 | E-ticaret | 3 | 4 | 2 | 4 | 4 | 17 |
| 6 | İnşaat | 5 | 3 | 1 | 4 | 2 | 15 |
| 7 | SaaS | 2 | 3 | 1 | 4 | 3 | 13 |
| 8 | Üretim | 3 | 2 | 1 | 3 | 2 | 11 |

E-ticaret (a)=3: dosyalar makine CSV’si, insan Excel’i değil. İnşaat (a)=5 ama 6. sıra: acı WIP’te, close 10–15 gün. SaaS 7. sıra: “modern finance” pazarı gibi durur; şelale close’un kendisi. Klinik (e)=3: HIPAA kapısı.

---

## 4. Neden saha hizmeti, neden profesyonel hizmet ikinci?

İkisi de yüksek skor. Saha hizmeti üç somut nedenle önde:

1. İki gelir de listeden toplanır; değerleme motoru yok. Profesyonel hizmette en büyük gelir satırında yargı var (unbilled vs write-off).
2. İki baskın hata tipi, sınıflandırıcının en iyi tuttuğu iki sınıf: `stale_reference` (iptal müşteri hâlâ aktif) ve `missing_je` (distributor faturası girilmemiş).
3. Sentinel senaryosu ve (varsa) demo baseline bu sektörde. Varyans için önceki dönem şart; başka sektörde önce Şubat baseline yazılır.

Demo şirketi: Sentinel Secure tipi — 8–30 kişi, QuickBooks, ServiceTitan/Jobber, kapatan kişi ofis müdürü, paket owner’a mail.

---

## 5. Saha hizmetinde 4–5 gün — ürünü buna tamamla

Aşağıdaki ekler yeni ürün değil. Banka matching, ASC 606, stok, inşaat WIP, ERP’ye JE basmak **yok.**

### Gün 0 — Kesim ve dosya manifesti

Beklenen dosyalar: GL export, bordro, tedarikçi çizelgesi, sözleşme listesi, iş/kurulum kaydı, yakıt kartı, (varsa) depozito logu. Hangisi geldi, hangisi yok. Dönem uyumu; geçen ayın dosyasının yeniden gönderilmediği (aynı satır sayısı + aynı toplam). Close checklist’in ilk kutusu. Discovery plan zaten var; yeni motor değil.

### Gün 1 — GL bütünlüğü (nakit yerine, sınır yazılı)

Ortodoks Gün 1 banka recon’dur; ürün yapmaz. Yapabileceği kapı: kaynak gerçeği mutabakattan önce tam mı — GL ayakları tutuyor, map %100, mükerrer hesap yok, dönem tek. Çıktı: “GL kaynak kabul edildi — N hesap, gelir X, gider Y.” Pakette açık cümle: *banka ve kart mutabakatı Month Proof dışında tamamlandı, controller teyit etti.*

### Gün 2 — Beş tie-out (çekirdek)

Her kontrol: bir dosya toplamı vs bir GL hesabı.

1. Bordro vs GL maaş / vergi / taşeron → `categorical_misclassification` (`similar_amount_in_other_account`).
2. Tedarikçi çizelgesi vs GL malzeme/COGS → `missing_je` veya dönem aşan faturada `accrual_mismatch`.
3. Aktif sözleşme × ücret vs GL izleme geliri → `stale_reference`.
4. İş/kurulum kaydı vs GL kurulum geliri → kayıtta kesim sonrası tarih varsa `timing_cutoff` (`crosses_period_boundary`).
5. Yakıt kartı vs GL araç → `missing_je` veya `timing_cutoff`.

Ekran “32 anomali” değil: **5 kontrolden 3 temiz, 2 istisna.** Close bir kontrol listesidir, bulgu yığını değil.

**Gerçek dosya boşluğu.** Consolidator `Account` kolonuna join eder; demo dosyaları elle bu kolonu taşır. Gerçek sözleşme listesinde müşteri adı + ücret vardır, GL adı yoktur. Tie-out 3 ve 4 için dosya-seviyesi map gerekir: “bu dosyanın Amount toplamı → GL hesabı X.” Mapping modu, yeni motor değil. Bu, akışı gerçek müşteri dosyasına oturtan en önemli mühendislik parçasıdır.

### Gün 3 — Açık madde yaşlandırma

Ajan tahakkuk yazmaz. Yapar: “Şubat $1.700 CableMax hâlâ açık, iki aydır.” Timing sonraki ay dönmeli. Veri önceki period `reports.reconciliations` içinde. `delta × 12` başka hesaba denk geliyorsa adlandırılmış accrual istisnası (yıllık fatura peşin gider).

### Gün 4 — Flux (mevcut, eşik düzeltilmeli)

Saha sahibinin baktığı beş sayı: kurulum vs izleme geliri, brüt marj, işçilik/gelir, malzeme/kurulum, araç maliyeti. Anlatı ve guardrail aynı.

`backend/agents/comparison.py` eşikleri DRONE ölçeği ($50k / $10k). ~$180k aylık HVAC P&L’de Tier 1 hiçbir satırı flag’lemez. Eşik ciroya göre ölçeklenmeli veya şirket ayarı olmalı — yeni sektör değil.

İlgili gürültü: `consolidator.py` içinde `_is_material`, dokümante edilen “$100 ve %5” kuralını uygulamıyor; fiilen `$100` tabanı. Delta `(canonical, category)` ile gruplanınca GL ile departman kategori anlaşmazlığında tek kaynaklı yetim düşüyor. Sentinel smoke test’te 41 hesaplı GL’den 32 recon (28 `missing_je`) bu yüzden. Hiçbir controller 41 satırda 32 istisna kabul etmez.

### Gün 5 — Paket, imza, kilit

`complete` yetmez. Kullanıcı “dönemi kapattım” der (`closed` durumu, kim/ne zaman). Kapalı dönem salt okunur; yeniden açmak yeni run ve log. QuickBooks closing date karşılığı.

Excel’e mevcut üç sayfaya ek: **Close Checklist** (tie-out durumu + banka/stok dışarıda teyit) ve **Open Items** (Gün 3 yaşlanmış liste). Mail: net kâr, üç flux satırı, sınıfa göre istisna, açık maddeler, teyit cümlesi. Ofis müdürünün owner’a ilettiği paket bu.

---

## 6. Ürün sapması (neden süreç garip)

| Close adımı | Gerçek hayatta | Month Proof bugün |
|-------------|----------------|-------------------|
| Gün 0 kesim | Dosya/iş kesimi | Yok (yükle ve çalıştır) |
| Gün 1 nakit | Banka = GL nakit | Yok; sınır da yazılmıyor |
| Gün 2 tie-out | Kontrol hesabı vs kaynak | Var, ama bulgu listesi; checklist değil. Join `Account` kolonu bekliyor |
| Gün 3 tahakkuk | Çizelge + ters kayıt | Sınıf var; yaşlandırma yok |
| Gün 4 flux | Mutabakat bitince | Pipeline’ın erken/orta kısmında; SMB eşiği yüksek |
| Gün 5 kilit | Closing date + paket | `complete` + e-posta; imza/kilit yok |

Omurga P&L varyansı; close değil. GL çoğu yerde hesap numaralı defter değil, P&L satır adı + 6–7 GAAP kovası. `monthly_entries` tek tutar `(şirket, hesap, dönem)` — debit/credit, JE detayı, bilanço rollforward yok. Prompt “jargon yok / non-technical” der; hedef kullanıcı GL ve JE konuşan analist/controller.

Bu bir bug listesi değil, **yanlış katman seçimi.** Mimari kural (pandas hesaplar, Claude yazar, guardrail doğrular) doğru ve korunur.

---

## 7. Bilerek dışarıda (pivot değil)

- Banka işlem eşleştirme
- ASC 606 / deferred revenue waterfall
- Stok ve COGS değerleme
- İnşaat WIP / yüzde tamamlanma
- ERP’ye JE post (SOX: ajan post etmez, taslak önerir)
- PDF/OCR
- Multi-entity / intercompany
- HIPAA-first klinik satışı

Bunların her biri başka sektörün düşük skorunun nedeni. Birini eklemek kapsamı yeniden açar.

---

## 8. Kaynaklar

- [HighRadius — Month-end close steps](https://www.highradius.com/resources/Blog/what-is-month-end-close-process/)
- [FloQast — What is the month-end close process](https://www.floqast.com/blog/what-is-the-month-end-close-process)
- [Catalyst CPA — SMB month-end close checklist 2026](https://catalyst-cpa.com/month-end-close-checklist-small-business-2026/)
- [CLA — 8 steps for a strong month-end close](https://www.claconnect.com/en/resources/articles/26/building-a-strong-month-end-close-process)
- [Northstar — 2,000+ monthly closings across industries](https://nstarfinance.com/resources/reviewing-2000-monthly-closings-across-industries-learnings)
- [Xorosoft — Manufacturing month-end close](https://xorosoft.com/manufacturing-month-end-close/)
- [Profitability Partners — Monthly close for contractors / field service](https://profitabilitypartners.io/monthly-close-checklist-contractors/)
- [Numetix — Professional services accounting](https://www.numetix.ai/resources/professional-services-accounting-guide)
- [The SaaS CFO — Deferred revenue](https://www.thesaascfo.com/deferred-revenue-saas/)
- [Premier CS — Construction WIP reports](https://premiercs.com/blog/the-complete-guide-to-wip-reports-in-construction-accounting)
- Repo içi: [docs/04-status/YAPILACAKLAR.md](../04-status/YAPILACAKLAR.md), [docs/archive/three_sector_demo_plan.md](../archive/three_sector_demo_plan.md), [backend/agents/consolidator.py](../../backend/agents/consolidator.py), [backend/agents/comparison.py](../../backend/agents/comparison.py)

---

## 9. Sonraki adım (kod değil, sıra)

1. Hedef kullanıcı kilit: controller/analist (GL, JE, mutabakat) — jargon bilmeyen owner değil.
2. Close dilimi kilit: GL-merkezli tie-out + açık maddeler + flux + paket. Yalnızca P&L anlatısını derinleştirmek değil.
3. İlk müşteri dosya listesi: GL TB, bordro, tedarikçi, sözleşme, iş kaydı. BvA ve tam banka recon ilk dilimde yok.
