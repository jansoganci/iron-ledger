# IronLedger Ürün ve Teknik Yol Haritası — Taslak

**Durum:** Taslak / tartışmaya açık. Kod değişikliği, migration veya özellik uygulaması içermez.
**Hazırlanma tarihi:** 2026-07-18
**Kapsam:** Bu belge, kod tabanının doğrudan okunmasıyla (dosya ve satır referanslarıyla) doğrulanmış bulgulara dayanır. Daha önceki raporlar (kod tabanı değerlendirme raporu ve `IronLedger_Strategy_Report_TR.md`) girdi olarak kullanılmış, ancak hiçbir iddia sorgusuz kabul edilmemiştir. Bir iddia kodda doğrulanamadıysa "**Doğrulanmadı**" etiketiyle işaretlenmiştir.

**Önemli not — kaynakların güvenilirliği:** `docs/IronLedger_Strategy_Report_TR.md` dosyasının kendisi, 26-28. satırlarda açıkça şunu belirtir: rapor yazılırken kod tabanına erişim yoktu, "mevcut durum" bölümü sohbetten çıkarılmıştır ve kod üzerinden doğrulanmış bir teknik denetim değildir. Bu nedenle o raporun "şu an var / yok" tespitleri bu belgede **doğrudan kaynak olarak kullanılmamış**, yalnızca kodda doğrulanan gerçek durumla karşılaştırılmıştır. Benzer şekilde, `CLAUDE.md` ve `docs/01-architecture/` klasöründeki mimari dokümanlar da kodun daha önceki, daha küçük bir haline aittir; kod bunların ötesine geçmiştir.

---

## 1. Yönetici Özeti

**Şu an ne çalışıyor?**
IronLedger (üründe "Month Proof" olarak da anılıyor), tek dosya veya birden fazla dosya (GL + bordro + tedarikçi faturaları vb.) yükleyip bunları tek bir aylık kâr-zarar tablosuna dönüştüren, sapmaları tespit eden, sebebini sınıflandıran ve Claude ile düz metin bir rapor yazan çalışan bir sistemdir. Sayısal hesaplamalar tamamen Python/pandas ile yapılıyor; Claude'un ürettiği hiçbir rakam, pandas'ın ürettiği referans rakamlarla eşleşmeden rapora geçmiyor (`backend/tools/guardrail.py`). Bu, projenin "Altın Kural"ının kodda gerçekten uygulandığı anlamına gelir — kontrol ettiğimiz hiçbir hesaplama dosyasında (`comparison.py`, `consolidator.py`, `hint_computer.py`) Claude'a hesap yaptırılmadığı doğrulandı.

**En büyük teknik risk nedir?**
Birden fazla dosya yüklendiğinde (ürünün asıl vaadi budur), bir hesap adı hem GL (muhasebe defteri) dosyasında hem de başka bir kaynak dosyada (örn. bordro, satış) geçiyorsa, sisteme kaydedilen tutar **iki kaynağın toplamı** oluyor — GL'nin tek başına yetkili kabul edilmesi gerekirken. Bu, kodun kendi yorum satırında da itiraf ediliyor (`backend/agents/interpreter.py:272-273`: *"the consolidated pandas_summary total ($10,920 = GL + dept)"*). Ayrıntı Bölüm 3.1'de.

**En güçlü ürün yeteneği nedir?**
Altı kategorili tutarsızlık sınıflandırması (`timing_cutoff`, `categorical_misclassification`, `missing_je`, `stale_reference`, `accrual_mismatch`, `structural_explained`) — pandas'ın hesapladığı somut sinyallere (`backend/tools/hint_computer.py`) dayanıyor, Claude'un tahminine değil. Stratejik raporun en çok önem verdiği fikirlerden biri gerçekten inşa edilmiş durumda.

**Sırada ne olmalı?**
Önce Bölüm 3.1'deki toplama hatası düzeltilmeli ve kiracı (müşteri) izolasyonu için otomatik bir test yazılmalı (Bölüm 3.2). Bunlar olmadan üzerine yeni özellik inşa etmek, yanlış sayılar üzerine bina kurmak demektir.

**Şimdilik ne inşa edilmemeli?**
Katmanlı (4 seviyeli) hesap eşleme sistemi, etkileşimli finansal akış tuvali (canvas) ve bütçe/gerçekleşen karşılaştırması. Bunların hiçbiri bugün var olan temel (kalıcı eşleme hafızası, onay/denetim izi) olmadan sağlam inşa edilemez.

**Önerilen geliştirme sırası:** Faz 0 (doğruluk ve temizlik) → Faz 1 (kalıcı eşleme + inceleme temeli) → Faz 2 (operasyonel kapanış ve istisna kutusu) → Faz 3 (finansal akış tuvali) → Faz 4 (bütçe karşılaştırma) → Faz 5 (planlama/senaryo, koşullu).

---

## 2. Mevcut Ürünün Gerçek Durumu

### 2.1 Kullanıcı akışı (Çalışıyor)

Kullanıcı 1 veya N dosya yükler (`POST /upload`, `backend/api/routes.py:186`). Dosya sayısına göre iki farklı yol izleniyor (`routes.py:263-278`):

- **Tek dosya:** Yapı keşfi (Discovery, Haiku modeliyle) → normalleştirme → doğrulama → hesap kategorisi eşleme (Haiku) → kullanıcı onayı bekleniyor.
- **Çok dosya:** Her dosya ayrı ayrı okunuyor, GL olmayan dosyalardaki ham değerler (örn. tedarikçi adı) bir GL hesabına eşleniyor (AccountMapper, Haiku) → kullanıcı eşlemeyi onaylıyor → dosyalar birleştiriliyor (consolidation) → kullanıcı son önizlemeyi onaylıyor.

Onaydan sonra karşılaştırma (pandas), anlatı üretimi (Claude Opus) ve sayısal doğrulama (guardrail) çalışıyor, rapor tamamlanıyor. **Durum: Çalışıyor.** Kanıt: `backend/domain/run_state_machine.py` 14 durumlu bir akış tanımlıyor (`pending → parsing → discovering/mapping → awaiting_confirmation → comparing → generating → complete`), ve bu geçişler `backend/agents/orchestrator.py` içinde uygulanıyor.

### 2.2 Ön yüz (Frontend) ekranları ve yetenekleri

Doğrulanan sayılar: **11 sayfa** (`frontend/src/pages/`), **24 üst düzey bileşen** (`frontend/src/components/`), **App.tsx içinde 11 rota** (`frontend/src/App.tsx:37-118`). (Not: önceki değerlendirme raporunda 10 ve 12 gibi farklı sayılar geçiyordu; doğrudan sayım 11 sayfa/24 bileşen çıkardı — küçük bir tutarsızlık, önemli değil ama burada düzeltiliyor.)

Sayfalar: LandingPage, LoginPage, RegisterPage, OnboardingPage, UploadPage, DataPage, ReportPage, ProfilePage, DashboardPage, ReportsPage, QuarterlyReportPage.

Öne çıkan bileşenler ve durumları:
- `FileUpload.tsx`, `MappingReview.tsx`, `DiscoveryReview.tsx`, `ParsePreviewPanel.tsx` — **Çalışıyor.** `MappingReview.tsx` doğrudan okundu: dosya başına toplu eşleme uygulama, "Bordro" ön ayarı, çakışma kontrolü içeriyor; `POST /runs/{id}/confirm-mappings` uç noktasını çağırıyor.
- `ReconciliationPanel.tsx`, `ReconciliationCard.tsx`, `ClassificationBadge.tsx` — **Çalışıyor.** Şiddete göre (yüksek/orta/düşük) gruplama yapıyor.
- `AnomalyCard.tsx`, `ReportSummary.tsx`, `GuardrailWarning.tsx`, `ProvenanceTooltip.tsx`, `QuarterlyProgress.tsx` — **Çalışıyor** (raporda kullanıldığı doğrulandı).
- `ErrorBoundary.tsx` — **Çalışıyor**, `App.tsx:31`'de en dış katmanı sarmalıyor.

Ön yüzün backend'e bağlanma şekli: tüm veri çağrıları `frontend/src/lib/api.ts` üzerinden, JWT (kimlik token'ı) ekleyerek yapılıyor. Supabase istemcisi (`frontend/src/lib/supabase.ts`) **sadece** oturum/token almak için kullanılıyor; hiçbir yerde doğrudan Supabase tablosu sorgulanmıyor — yani ön yüz backend'in iş mantığını atlamıyor. **Durum: Çalışıyor**, doğrudan `api.ts` ve `supabase.ts` okunarak doğrulandı.

Durum yönetimi: React Query (`@tanstack/react-query`) bazı GET isteklerinde (`useQuery`), geri kalanı düz `useState` ile yapılıyor (`UploadPage.tsx` içinde 10'dan fazla `useState` çağrısı doğrudan görüldü). Bütçe, onay/inceleyen rolü veya tuval (canvas) gibi kavramlara dair **hiçbir bileşen veya bağımlılık yok** — `frontend/package.json` doğrudan okundu, `reactflow`, `d3`, `recharts` gibi bir grafik/tuval kütüphanesi bulunmuyor. **Durum: Spec / henüz yok.**

`ProtectedRoute.tsx` sadece "giriş yapılmış mı" kontrolü yapıyor; inceleyen/onaylayan gibi bir rol ayrımı **yok**. **Durum: Spec / henüz yok.**

### 2.3 Backend servisleri, API'ler ve ajanlar

`backend/agents/` klasöründe **9 ajan modülü** var (CLAUDE.md kök dosyasının belirttiği 3 değil): `parser.py` (586 satır), `discovery.py` (131 satır), `account_mapper.py` (120 satır), `consolidator.py` (354 satır), `comparison.py` (221 satır), `interpreter.py` (346 satır), `opus_upgrade.py` (152 satır), `quarterly.py` (556 satır), `orchestrator.py` (901 satır). Hepsi doğrudan okundu ve gerçekten çalışan, birbirine bağlı kod olduğu doğrulandı.

`backend/api/routes.py` içinde **23 uç nokta** doğrudan sayıldı (`grep '^@router\.'`): `/health`, `/upload`, `/runs/{id}/status`, `/runs/{id}/raw`, `/report/{company_id}/{period}`, `/report/.../export.xlsx`, `/anomalies/{company_id}/{period}`, `/mail/send`, `/runs/{id}/retry`, `/runs/{id}/mapping/confirm`, `/runs/{id}/confirm`, `/runs/{id}/confirm-mappings`, `/runs/{id}/confirm-discovery`, `/runs/{id}/reject-discovery`, `/companies/me`, `/companies/me/has-history`, `POST /companies`, `/reports`, `/data`, çeyreklik rapor için 4 uç nokta (generate/status/get/delete). **Durum: Çalışıyor.**

Kullanılan yapay zekâ modelleri hâlâ sadece iki tane (kullanıcı tarafından değiştirilemiyor) ama **6 farklı çağrı noktasında**: Haiku — Discovery (`discovery.py:14`), kategori eşleme (`parser.py` içinde), AccountMapper (`account_mapper.py:25`); Opus — ana anlatı (`interpreter.py:17`), "Opus Upgrade" ikinci geçiş (`opus_upgrade.py:12`), çeyreklik rapor (`quarterly.py:14`).

### 2.4 Dosya alım ve ayrıştırma (Parsing)

`backend/tools/file_reader.py` — Excel/CSV formatlarını, NetSuite'in `.xls` uzantılı ama aslında XML olan dosyalarını (ilk 2 bayta bakarak) okuyor. **Durum: Kısmen çalışıyor / Doğrulanmadı gerçek dünya verisiyle.** Gerekçe: `docs/demo_data/` altındaki hiçbir gerçek örnek dosya `.xls` veya NetSuite-XML formatında değil (hepsi `.xlsx`); bu kod yolu yalnızca test içinde elle üretilmiş sentetik baytlarla sınanmış, gerçek bir NetSuite çıktısıyla değil.

`backend/agents/discovery.py` + `backend/tools/normalizer.py` — Claude önce dosyanın yapısını (başlık satırı, atlanacak satırlar, sütun eşlemesi) tahmin ediyor, güven skoru %80'in altındaysa kullanıcıya soruluyor (`discovery.py:16` `CONFIDENCE_THRESHOLD = 0.80`), üstündeyse otomatik devam ediyor. Normalizer tamamen pandas/Python, LLM çağrısı yok — doğrudan okundu. **Durum: Çalışıyor.**

Önemli ayrıntı: çoklu dosya yüklemesinde, dosya bazında düşük güvenli Discovery planları **sessizce otomatik onaylanıyor** (`backend/agents/parser.py` içindeki ilgili akış, orkestratör tarafında `run_multi_file_parser_with_mapping` çağrılıyor) — yalnızca birleştirilmiş eşleme taslağı kullanıcıya soruluyor, her dosyanın yapısal okunuşu tek tek sorulmuyor. **Durum: Kısmen çalışıyor** (güvenlik ağı tek dosyada var, çok dosyada zayıflatılmış).

### 2.5 Hesap eşleme (Account mapping)

İki ayrı, birbirinden bağımsız mekanizma var:
1. Parser'ın kendi "sütun → ABD GAAP kategorisi" eşlemesi (Haiku, güven skoruyla, `accounts` tablosuna yazılıyor, sürüm geçmişi yok).
2. `AccountMapper` (`backend/agents/account_mapper.py`) — ham kaynak değerini (örn. "AlarmTech Industries") bir GL hesap adına eşliyor. Halüsinasyon koruması var: Claude'un önerdiği hesap adı, önceden GL dosyasından çıkarılan geçerli hesap havuzunda yoksa reddediliyor (`account_mapper.py:83-94`, doğrudan okundu).

**Kritik eksik:** Hiçbir migration'da (`0001`–`0009`, hepsi tek tek okundu) `account_mappings` gibi bir kalıcı eşleme tablosu yok. Eşleme kararları yalnızca o anki `runs.parse_preview` (JSONB) alanında yaşıyor ve çalışma bitince kayboluyor. Her yeni yükleme, aynı tedarikçi adı için Claude'u sıfırdan tekrar çağırıyor. **Durum: Kısmen çalışıyor** (eşleme işi yapılıyor, ama hiçbir şey kalıcı/sürümlü değil).

### 2.6 Birleştirme (Consolidation)

`backend/agents/consolidator.py` — çok dosyalı yüklemede tüm kaynakları birleştirip tek bir hesap listesi üretiyor. Adımlar: birleştirme (union) → bulanık eşleştirme (fuzzy match, %90 eşik, `rapidfuzz` kütüphanesi) → toplama (roll-up) → fark tespiti (delta detection). **Durum: Çalışıyor ama Bölüm 3.1'de açıklanan ciddi bir doğruluk sorunu var.**

### 2.7 Tutarsızlık sınıflandırması

`backend/tools/hint_computer.py` — 6 farklı sinyali (dönem sınırını aşma, yuvarlak kesir/50% örüntüsü, başka hesapta eşleşen tutar, yalnızca-GL/yalnızca-kaynak, yıllık fatura örüntüsü) tamamen pandas ile hesaplıyor, bu sinyaller Claude'un sınıflandırma yapmasına yardımcı oluyor (`interpreter.py:58-76`'da Claude sınıflandırma yapmazsa kural tabanlı bir yedek de var). **Durum: Çalışıyor**, doğrudan okundu.

### 2.8 Anlatı üretimi ve güvenlik ağı (guardrail)

`backend/tools/guardrail.py` — CLAUDE.md dosyasının belirttiği sabit %2 tolerans değil, `max(değerin %1'i, 1.000 $)` kuralı uygulanıyor (`guardrail.py:15-24`, doğrudan okundu). Yani projenin "DO NOT CHANGE" (değiştirme) diye işaretlediği tek dosya, dokümantasyonu güncellenmeden zaten değiştirilmiş. **Durum: Çalışıyor**, ama dokümantasyon güncel değil.

Guardrail'e ayrıca `reconciliation_values` adında ek bir referans değer listesi besleniyor (`interpreter.py:270-283`) — bu, Claude'un "GL'de 5.420$ görünüyor" gibi kaynak bazlı tekil rakamlar söylediğinde, bu rakamların birleşik toplamla (`consolidated total`) eşleşmemesi yüzünden yanlışlıkla reddedilmesini önlemek için eklenmiş. Bu kodun kendisi, geliştiricinin birleşik toplamın "GL + departman" olduğunu bildiğinin kanıtı (bkz. Bölüm 3.1).

### 2.9 Excel/rapor teslimi

`backend/tools/excel_export.py` — 3 sayfalı bir Excel dosyası üretiyor: Konsolide Gelir Tablosu, Mutabakatlar (Reconciliations), Kaynak Dağılımı. Statik değerler, formül yok. Anlatı metni (Claude'un yazdığı) **hiç dahil edilmiyor** — yalnızca sayılar. Ayrıca `suggested_action` (önerilen düzeltme) alanı da Excel'e yazılmıyor. **Durum: Çalışıyor** ama kapsamı sınırlı, doğrudan okundu.

### 2.10 Kimlik doğrulama ve şirket izolasyonu

Bkz. Bölüm 3.2 — burada ayrıntılı ele alınıyor. Özet: kimlik doğrulama gerçek ve çalışıyor, ama veritabanı düzeyindeki izolasyon (RLS) uygulamada devre dışı kalıyor çünkü backend "servis rolü anahtarı" kullanıyor.

### 2.11 Veritabanı tabloları ve migration'lar

9 migration dosyası (`0001`–`0009`), hepsi tek tek okundu. 7 tablo hâlâ aynı (companies, account_categories, accounts, monthly_entries, anomalies, reports, runs) ama çok sayıda sütun eklenmiş: `pandas_summary`, `source_column`, `storage_key`, `parse_preview`, `discovery_plan`/`discovery_approval_mode`, `source_breakdown`/`reconciliations`/`file_count`, `opus_status`/`opus_upgraded`, `report_type`/`quarter`/`year`/`is_stale`/`quarterly_data`, `anomalies.is_recurring`. Migration numaralandırması düzenli, çakışma yok. **Durum: Çalışıyor.**

### 2.12 Testler

`tests/` altında **17 test dosyası** var (doğrudan listelendi): agents, tools, domain, api, adapters, integration alt klasörlerinde. Ama:
- `tests/integration/conftest.py:17` ve kök dizindeki `probe_excel.py:5`, artık var olmayan bir dosyaya (`docs/demo_data/Drone Inc - Mar 26.xlsx`) işaret ediyor — bu dosyanın gerçekten olmadığı doğrudan kontrol edildi (`ls` "No such file or directory" döndürdü). Bu, en az 5 entegrasyon testini (`test_parser_end_to_end.py` içinde) kurulum aşamasında `FileNotFoundError` ile çökertir.
- Kiracı izolasyonu (RLS) için **hiçbir test dosyası yok** — `tests/` içinde `test_rls.py` benzeri bir dosya bulunmuyor.
- **Durum: Kısmen çalışıyor** (testler var ama bir kısmı bozuk, kritik bir alan hiç test edilmiyor).

### 2.13 Dokümantasyon

`CLAUDE.md`, `docs/01-architecture/*`, `docs/04-status/CURRENT_STATUS.md` gibi dosyalar, kodun daha önceki, daha küçük bir hâlini anlatıyor (3 ajan, 6 migration, ~16 uç nokta, 2 demo sektörü). Gerçek kod: 9 ajan, 9 migration, 23 uç nokta, 6 demo sektörü (clearview, corebuilt, harvest, helix, sentinel, vandelay). **Durum: Eski / güncel değil.** CLAUDE.md'nin "Demo Data" bölümünde bahsedilen `drone_feb_2026.xlsx` / `drone_mar_2026.xlsx` dosyaları da artık repoda yok.

### 2.14 Özet sınıflandırma tablosu

| Yetenek | Durum | Kanıt |
|---|---|---|
| Tek/çoklu dosya yükleme akışı | Çalışıyor | `routes.py:263-278`, `orchestrator.py` |
| PII (kişisel veri) temizleme | Çalışıyor | `pii_sanitizer.py` (iki katmanlı: sütun + değer bazlı) |
| Yapı keşfi (Discovery) | Çalışıyor | `discovery.py`, `normalizer.py` |
| Hesap eşleme (AccountMapper) | Kısmen çalışıyor | `account_mapper.py` — kalıcılık yok |
| Birleştirme (Consolidation) | Çalışıyor ama hatalı | `consolidator.py` — bkz. 3.1 |
| Tutarsızlık sınıflandırması | Çalışıyor | `hint_computer.py`, `interpreter.py` |
| Sayısal güvenlik ağı (guardrail) | Çalışıyor | `guardrail.py` |
| Excel dışa aktarma | Çalışıyor (sınırlı kapsam) | `excel_export.py` |
| Çeyreklik rapor | Çalışıyor | `quarterly.py` |
| Kiracı izolasyonu (gerçek) | Kısmen çalışıyor / riskli | Bkz. 3.2 |
| Kalıcı eşleme hafızası / sürüm geçmişi | Spec, henüz yok | Hiçbir migration'da `account_mappings` yok |
| İnceleme/onay iş akışı | Spec, henüz yok | `discovery_approval_mode` dışında onay alanı yok |
| Taslak yevmiye kaydı (draft JE) | Spec, henüz yok | Hiçbir yerde JE veri modeli yok |
| Finansal akış tuvali | Spec, henüz yok | Bağımlılık/bileşen yok |
| Bütçe / gerçekleşen karşılaştırma | Spec, henüz yok | Şema yok |
| Çok şirketli (multi-entity) yapı | Spec, henüz yok | `companies.owner_id` 1:1 |
| NetSuite XML gerçek veriyle test | Doğrulanmadı | Gerçek örnek dosya yok |

---

## 3. Kritik Doğruluk ve Güvenlik Riskleri

### 3.1 GL ve destekleyici kaynakların birleştirilmesi

**Mevcut davranış (doğrudan kodda doğrulandı):**

`backend/agents/consolidator.py` içindeki `_roll_up` fonksiyonu (satır 157-210), her bir kanonik hesap için tek bir satır üretir. Kategori alanında GL'ye öncelik veriyor:

```python
# satır 190-192
if _is_gl_label(source_file):
    entry["category"] = category
```

Ama **tutar (amount) alanında böyle bir öncelik yok**:

```python
# satır 194 — koşulsuz, her kaynak dosya için çalışıyor
entry["amount"] = round(entry["amount"] + amount, 2)
```

Yani "Bordro" hesabı hem GL dosyasında 44.900 $ hem de bordro kayıt dosyasında 44.200 $ olarak geçiyorsa, `monthly_entries.actual_amount` alanına yazılan rakam **89.100 $** oluyor — 44.900 $ (doğru GL rakamı) değil. Bu akış `backend/api/routes.py:930-947` üzerinden doğrudan takip edildi: `row["amount"]` değeri, konsolide DataFrame'den geldiği için bu toplanmış rakamı taşıyor.

Bunun ayrıca kodun içinde **itiraf edildiğini** de gördük — `backend/agents/interpreter.py:270-273`:

> "Claude may mention individual source-level figures (e.g. 'GL shows $5,420') which differ from the consolidated pandas_summary total ($10,920 = GL + dept)."

Yani geliştirici ekip, birleşik toplamın "GL + departman" olduğunu zaten biliyor ve bunu guardrail'i şaşırtmamak için bir yan kanal (`reconciliation_values`) ekleyerek "çözmüş" — ama asıl kayıt edilen rakamı (`monthly_entries.actual_amount`) düzeltmemiş.

**Beklenen muhasebe davranışı:** GL, yetkili (authoritative) kayıt olmalı. Diğer kaynaklar (bordro, satış, fatura) GL'yi *doğrulamak* için kullanılmalı, GL'nin üzerine eklenerek ikinci bir gelir tablosu oluşturmamalı. Bir hesap için GL kaynağı varsa, kayıtlı tutar GL'nin tutarı olmalı; diğer kaynaklardaki fark, ayrı bir "mutabakat farkı" (reconciliation delta) olarak gösterilmeli — toplama dahil edilmemeli.

**Çift sayımın nasıl oluştuğuna somut örnek:**
- GL dosyası: "Bordro" = 44.900 $
- Bordro kayıt dosyası: "Bordro" = 44.200 $ (aynı ay, küçük bir fark — belki bir ödeme henüz GL'ye işlenmemiş)
- Bugünkü davranış: sisteme kaydedilen "Bordro" tutarı = 89.100 $
- Doğru davranış: sisteme kaydedilen tutar = 44.900 $ (GL), ayrıca "700 $ fark tespit edildi, sebebi muhtemelen zamanlama" notu

**Hangi çıktılar etkileniyor:**
- `monthly_entries.actual_amount` — doğrudan yanlış.
- Karşılaştırma ajanı (`comparison.py`) — bu yanlış rakamı geçmişle kıyaslıyor, yanlış sapma (%varyans) üretiyor.
- Anomali tespiti — yanlış rakama dayalı yanlış alarm veya kaçırılmış gerçek sapma.
- Opus anlatısı ve çeyreklik rapor — yanlış rakamı "doğru" kabul edip yorumluyor.
- Guardrail bunu **yakalayamıyor** çünkü guardrail sadece Claude'un yazdığı rakamın pandas çıktısıyla eşleşip eşleşmediğine bakıyor; pandas çıktısının kendisi zaten yanlışsa guardrail bunu göremez.

**Nasıl düzeltilmeli (öneri, uygulama değil):** `_roll_up` fonksiyonu, bir hesap için GL kaynağı varsa tutarı GL'nin tutarına eşitlemeli, diğer kaynaklardaki tutarları toplama dahil etmemeli — bunun yerine mevcut mutabakat mekanizmasına (zaten var olan `_detect_deltas`, `gl_amount`, `non_gl_total`, `delta` alanları) bırakmalı. Yalnızca GL kaynağı hiç yoksa (hiçbir dosyada GL etiketi yoksa), departman kaynaklarının toplamı kullanılmaya devam edilebilir — bu durum zaten `hint_computer.py`'deki `_is_source_only` mantığıyla ayrıca işaretleniyor.

**Gerekli regresyon testleri:**
- Bir hesabın hem GL hem departman dosyasında farklı tutarlarla geçtiği bir senaryoda, konsolide tutarın GL tutarına eşit olduğunu doğrulayan yeni bir test (`tests/agents/test_consolidator.py` içine).
- Yalnızca departman kaynaklarının olduğu (GL'siz) senaryoda toplamanın hâlâ doğru çalıştığını doğrulayan test.
- Mevcut mutabakat-farkı testlerinin (delta hesaplama) bu değişiklikten sonra da geçtiğinin doğrulanması.

**Kabul kriterleri:** GL + departman çakışması olan hesaplarda konsolide tutar = GL tutarı; mevcut mutabakat farkı hesaplaması değişmeden çalışmaya devam ediyor; entegrasyon testleri (düzeltildikten sonra, bkz. 2.12) yeşil.

**Not:** Bu bulgu, bu belgeyi hazırlarken kodun doğrudan okunmasıyla iki farklı bağımsız incelemenin çelişkili sonuçlarının çözülmesiyle netleştirildi (bir önceki inceleme kategori önceliğini tutar önceliğiyle karıştırmıştı). `consolidator.py` satır satır okunarak kesinleştirildi — bu **Doğrulanmadı değil, Doğrulandı** bir bulgudur.

### 3.2 Kiracı/şirket izolasyonu (tenant/company isolation)

**company_id nasıl uygulanıyor (doğrudan doğrulandı):**

`backend/api/auth.py` — kullanıcının JWT'si (giriş token'ı), Supabase'in `/auth/v1/user` uç noktasına gönderilerek doğrulanıyor (satır 27-55), dönen `user_id` ile `companies` tablosunda `owner_id` araması yapılıyor (`get_company_id`, satır 72-90). Yorum satırında açıkça yazıyor: *"Never accepts company_id from the client"* — yani `company_id` hiçbir zaman istemciden (frontend'den) doğrudan alınmıyor, her zaman sunucu tarafında JWT'den çözülüyor. Bu doğru ve güvenli bir tasarım.

**Supabase servis rolü nerede kullanılıyor:**

`backend/api/deps.py:22-24`:
```python
def _supabase_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)
```

Backend'in veritabanına yaptığı **her** sorgu bu tek istemci üzerinden gidiyor, ve bu istemci "servis rolü anahtarı" (`supabase_service_key`) ile oluşturuluyor.

**RLS gerçekten devre dışı mı kalıyor:**

Evet. `supabase/migrations/0001_initial_schema.sql` satır 138-202'de RLS politikaları gerçekten tanımlı ve `ENABLE ROW LEVEL SECURITY` komutu her şirket-sahipli tabloda çalıştırılmış — bu politikalar teknik olarak var. Ama Supabase/Postgres'in kendi kuralı gereği, **servis rolü anahtarı RLS'i by-pass eder** (atlar) — bu Supabase'in resmi davranışıdır, IronLedger'a özgü bir hata değil. Yani bu politikalar SQL dosyasında yazılı duruyor ama backend trafiğinde **hiç devreye girmiyor**.

Basit bir benzetme: RLS politikaları, her dairenin kendi anahtarıyla açılan bir apartman gibi düşünülebilir. Ama backend, "bina yöneticisi" anahtarıyla (servis rolü) giriyor — bu anahtar tüm daireleri açar, RLS'in "sadece kendi dairen" kuralını devre dışı bırakır. Bugün izolasyonu sağlayan şey RLS değil, her sorgu fonksiyonunun kodda elle `company_id` filtresi eklemesi (`backend/adapters/supabase_repos.py` içindeki repo sınıfları).

**Bu, kötü bir mimari mi?** Hayır — pek çok üründe bilinçli olarak tercih edilen, çalışabilir bir yaklaşımdır ("uygulama katmanında izolasyon"). Ama iki koşulu sağlaması gerekir: (1) hiçbir sorgu fonksiyonunun `company_id` filtresini unutmaması, (2) bunu kanıtlayan otomatik bir test olması. Bugün ikinci koşul **sağlanmıyor**.

**Hangi uç noktalar risk taşıyor:** Teorik olarak, `backend/adapters/supabase_repos.py` içindeki herhangi bir repo metodunun `company_id` filtresini unutması durumunda, o metodu çağıran **her** uç nokta (23 uç noktanın tamamı) başka bir şirketin verisini sızdırabilir. Bunu şu an hiçbir otomatik test kontrol etmiyor; kod incelemesi (code review) tek güvenceniz.

**Gerekli otomatik izolasyon testleri:**
- İki farklı gerçek (veya taklit) JWT ile, A şirketinin kullanıcısının B şirketinin verisine (raporlar, çalışmalar, hesaplar) hiçbir uç noktadan erişemediğini doğrulayan bir test paketi (`tests/test_rls.py` veya benzeri, henüz yok).
- Özellikle `run_id`, `report_id` gibi doğrudan ID ile erişilen uç noktalarda (`/runs/{run_id}/status`, `/runs/{run_id}/raw` gibi) çapraz-şirket erişim denemesi.

**Önerilen uzun vadeli güvenlik mimarisi (tartışmaya açık, Bölüm 11'de karar maddesi olarak da var):**
- **Seçenek A (düşük efor):** Servis rolü mimarisini koru, ama her repo metodunun `company_id` filtresi içerdiğini garanti eden bir test paketi ekle ve bunu CI'a (otomatik kontrol sürecine) bağla.
- **Seçenek B (orta efor, daha güçlü):** Kullanıcı JWT'sini backend üzerinden Supabase'e ileterek gerçek RLS'i devreye sokan bir istemci kullan (servis rolü yalnızca arka plan/yönetim işlemleri için). `backend/settings.py` içinde zaten bir `supabase_jwt_secret` alanı var ve bu, `backend/api/rate_limit.py:16-23` içinde JWT'yi yerel olarak çözmek için zaten kullanılıyor — yani bu ikinci mimariye geçiş için altyapı parçaları zaten mevcut, sıfırdan kurulmuyor.
- Bu belgenin önerisi: pilot müşteriler öncesinde en azından Seçenek A (test paketi) zorunlu; Seçenek B, üretim ölçeğine geçmeden önce değerlendirilmeli.

### 3.3 Diğer teknik riskler

| # | Bulgu | Kanıt | Öncelik |
|---|---|---|---|
| 1 | GL + departman toplamı çift sayım | `consolidator.py:190-194`, `interpreter.py:270-273` | **P0** |
| 2 | Kiracı izolasyonu testsiz, RLS fiilen devre dışı | `deps.py:22-24`, `0001_initial_schema.sql:138-202` | **P0** |
| 3 | Bozuk test fixture'ı — 5 entegrasyon testi kurulumda çöküyor | `tests/integration/conftest.py:17`, dosya yok | **P1** |
| 4 | Ölü kod: `run_multi_file_parser_until_preview` hiç çağrılmıyor | `orchestrator.py:68-251`, `routes.py:29` (yalnızca import, çağrı yok) | P2 |
| 5 | Tekrarlı kod: `file_keys` sözlüğü iki kez hesaplanıyor (biri atılıyor) | `orchestrator.py:630-638` (yorum satırı: "Rebuild file_keys correctly") | P3 |
| 6 | `messages.MAPPING_FAILED` iki kez tanımlanmış, ikincisi birinciyi sessizce eziyor — kullanıcıya hangi sütunların eşlenemediği bilgisi kayboluyor | `messages.py:17-20` ve `messages.py:65`, kullanım `main.py:101` | P1 |
| 7 | Dokümantasyon kodun gerisinde (ajan sayısı, migration sayısı, uç nokta sayısı, demo veri seti) | `CLAUDE.md`, `docs/01-architecture/*`, `docs/04-status/CURRENT_STATUS.md` | P2 |
| 8 | `opus_upgrade.py` adı yanıltıcı — ana yol zaten Opus kullanıyor, bu "yükseltme" değil "ikinci Opus geçişi"; her çalışma için Opus'a iki kez ödeme yapılıyor | `interpreter.py:17`, `opus_upgrade.py:12` | P2 (maliyet) |
| 9 | `suggested_action` alanı var ama hiç yapılandırılmış veri olarak doldurulmuyor, yalnızca serbest metin | `contracts.py:188`, `interpreter.py` içinde ayrı bir atama yok | P1 |
| 10 | `account_mappings` gibi kalıcı bir eşleme tablosu yok — her yükleme sıfırdan Haiku çağırıyor | 9 migration'ın tamamı tarandı, böyle bir tablo yok | P1 |
| 11 | NetSuite XML okuma kodu gerçek örnek veriyle hiç test edilmemiş | `docs/demo_data/` içinde `.xls`/XML dosyası yok | P2 |
| 12 | Gözlemlenebilirlik (observability) — loglama var (`backend/logger.py`, `trace_id` ile) ama merkezi hata/metrik panosu yok | Doğrulanmadı — böyle bir panonun var olup olmadığı bu incelemenin kapsamı dışında kaldı | Doğrulanmadı |
| 13 | Idempotency (aynı işlemi iki kez tetiklemenin güvenli olması): `apply_mapping_and_consolidate` çift tetiklenmeye karşı durum kontrolü yapıyor (`orchestrator.py:734-745`) — bu iyi bir örnek, ama tüm uç noktalarda sistematik olarak uygulandığı doğrulanmadı | `orchestrator.py:738-745` | Doğrulanmadı (genel kapsamda) |
| 14 | Denetim izi (audit trail) — hiçbir işlemin "kim, ne zaman, ne yaptı" bilgisi kalıcı olarak tutulmuyor; `discovery_approval_mode` (`auto`/`manual`) dışında onay/inceleme kaydı yok | 9 migration tarandı | P1 |

**Öncelik tanımları:** P0 — finansal doğruluğu veya veri güvenliğini tehdit ediyor. P1 — ürünün güvenilir kullanımını engelliyor. P2 — ölçeklenme veya bakım sorunu. P3 — iyileştirme.

---

## 4. Hedef Ürün Mimarisi

Hedeflenen ürün, tek seferlik bir "rapor oluşturucu" değil, tekrar eden bir **ay sonu kapanış operasyonu** aracı olmalı. Aşağıdaki yetenekler dört gruba ayrılıyor:

**Çekirdek ay sonu kapanış ürünü (bugünün üzerine, doğruluk düzeltmesiyle):**
- Güvenilir finansal veri temeli (Bölüm 3.1'in düzeltilmiş hâli — GL yetkili kaynak)
- Kalıcı hesap eşleme hafızası (bu ay yapılan eşleme, gelecek ay tekrar sorulmuyor)
- İstisna ve mutabakat yönetimi (tek seferlik değil, ay ay takip edilen bir kuyruk)
- Kaynak düzeyinde izlenebilirlik (provenance) — zaten dosya/sütun/hesap düzeyinde var, satır düzeyine kadar götürülmesi tartışmalı (Bölüm 11)
- İnceleme ve onay iş akışı (kim hazırladı, kim onayladı)
- Yapılandırılmış düzeltme önerileri (serbest metin değil, üzerine buton konulabilen veri)

**Yakın vadeli genişletmeler:**
- Taslak yevmiye kaydı (draft journal entry) — muhasebecinin manuel olarak deftere işleyeceği hazır bir öneri
- Denetim izi (audit trail) — her onay/değişiklik kalıcı kayıt

**Uzun vadeli planlama özellikleri (koşullu, müşteri kanıtı gerektirir):**
- Finansal akış tuvali (canvas) — kaynak → eşleme → GL hesabı → tablo satırı → istisna zincirini görselleştiren, tıklanabilir bir arayüz
- Bütçe içe aktarma ve gerçekleşen-bütçe karşılaştırması (salt okunur)
- Senaryo/tahmin planlama

**Şimdilik inşa edilmemesi gerekenler:**
- Tam bir bütçeleme/FP&A (finansal planlama ve analiz) motoru
- Serbest biçimli, sürükle-bırak finansal model tuvali
- GL'den bağımsız "ikinci bir gerçek gelir tablosu"
- Gün 1'den itibaren otomatik yevmiye kaydı gönderimi (ERP'ye yazma)
- Çok şirketli (multi-entity) konsolidasyon — mevcut kimlik modeli buna hazır değil

Bu ayrım, hem `IronLedger_Strategy_Report_TR.md`'nin kendi önerisiyle (agresif olmayan, "Close Investigation Workspace" odaklı büyüme) hem de kod tabanının bugünkü olgunluk seviyesiyle tutarlı.

---

## 5. Aşamalı Geliştirme Planı

### Faz 0 — Finansal Doğruluk ve Teknik Temizlik

**Kapsam:**
1. `consolidator.py`'deki GL/departman toplama hatasının düzeltilmesi (Bölüm 3.1).
2. Kiracı izolasyonu için otomatik test yazımı (Bölüm 3.2).
3. Bozuk test fixture'ının onarılması (`conftest.py`'nin var olmayan Drone dosyasına referansı).
4. Ölü kodun (`run_multi_file_parser_until_preview`) silinmesi veya neden tutulduğunun belgelenmesi.
5. `messages.MAPPING_FAILED` çakışmasının giderilmesi.
6. CLAUDE.md ve `docs/01-architecture/` dosyalarının gerçek kod durumuna güncellenmesi.

**Neden önemli:** Bu düzeltmeler yapılmadan üzerine yeni özellik eklemek, yanlış bir sayı üzerine yeni katmanlar inşa etmek anlamına gelir. Ayrıca kiracı izolasyonu testsiz kaldığı sürece, gerçek müşteri verisiyle çalışmak veri sızıntısı riski taşır.

| Görev | Backend değişikliği | Frontend etkisi | Veritabanı değişikliği | Güvenlik etkisi | Gerekli testler | Kabul kriteri | Bağımlılık | Risk |
|---|---|---|---|---|---|---|---|---|
| Konsolidasyon düzeltmesi | `consolidator.py` `_roll_up` fonksiyonu | Yok (kullanıcı arayüzü değişmiyor, sadece rakamlar doğrulanıyor) | Yok | Yok | Yeni regresyon testi (Bölüm 3.1) | GL+departman çakışmasında tutar = GL tutarı | Yok | Düşük — izole, saf mantık değişikliği |
| İzolasyon testi | Yeni test dosyası, kod değişikliği yok | Yok | Yok | Yüksek — açık riski kapatıyor | İki-JWT testi | Farklı şirketlerin verisi karışmıyor | Yok | Düşük |
| Fixture onarımı | `tests/integration/conftest.py` | Yok | Yok | Yok | Mevcut 5 test tekrar çalışır hâle geliyor | Test paketi kırmızı değil | Güncel demo veri dosyası | Düşük |
| Ölü kod temizliği | `orchestrator.py`, `routes.py` import satırı | Yok | Yok | Yok | Yok (silme işlemi) | Kod tabanında kullanılmayan fonksiyon kalmıyor | Yok | Çok düşük |
| Mesaj çakışması düzeltmesi | `messages.py` | Kullanıcı artık hangi sütunun eşlenemediğini görebilir | Yok | Yok | Küçük birim testi | 422 hata mesajı sütun adlarını içeriyor | Yok | Çok düşük |
| Dokümantasyon güncelleme | Yok (sadece .md dosyaları) | Yok | Yok | Yok | Yok | CLAUDE.md gerçek ajan/migration sayısını yansıtıyor | Yok | Yok |

### Faz 1 — Kalıcı Mapping ve İnceleme Temeli

**Kapsam:** `account_mappings` benzeri bir veri modeli eklemek — bir kaynak değerinin ("AlarmTech Industries") hangi GL hesabına eşlendiğini, kim tarafından, hangi tarihten itibaren geçerli olduğunu ve hangi güvenle onaylandığını kalıcı olarak saklamak. `MappingReview.tsx` arayüzü bu tabloya yazacak/okuyacak şekilde genişletilir. Rapor üzerine `reviewed_by`/`reviewed_at` gibi minimal bir onay alanı eklenir.

**Katmanlı (4 seviyeli) AccountMapper şimdi mi, sonra mı?** Bu belgenin önerisi: **şimdi değil.** Stratejik rapor 4 katmanlı bir yapı öneriyor (kaynak → normalize edilmiş kavram → GL hesabı → raporlama taksonomisi → yönetim hiyerarşisi). Bugün yalnızca ilk katman (kaynak değeri → GL hesabı) var ve kalıcı değil. Önerilen sıra: önce mevcut tek katmanı kalıcı ve sürümlü hâle getirmek (bu, "hiçbir şey bir çalışmadan uzun yaşamıyor" sorununun kendisini çözer), sonra gerçek kullanıcı düzeltme örüntülerine bakıp 2-4. katmanların gerekip gerekmediğine karar vermek. Bugün hiçbir kullanıcı bir eşlemeyi düzeltmemişken (çünkü düzeltmeler kalıcı olmuyor) 4 katmanlı bir sürümleme şeması tasarlamak, kanıtsız / körlemesine bir mühendislik kararı olur.

### Faz 2 — Operasyonel Close ve Exception Inbox

**Kapsam:** Bugün her tutarsızlık (`reconciliations`) yalnızca o ayın raporunda görünüyor ve kayboluyor. Bu fazda, tutarsızlıkların ay ay takip edilebildiği, durumu olan (açık/ertelendi/kapatıldı), atanabilen, yorum eklenebilen bir "istisna kutusu" (exception inbox) kurulur. Kök sebep sınıflandırması (zaten var olan 6 kategori) ve önerilen düzeltme (`suggested_action`) yapılandırılmış veri hâline getirilir — serbest metin cümlesi değil, üzerinde işlem yapılabilen bir alan olur. Taslak yevmiye kaydı (draft JE) modeli eklenir: kullanıcı bir öneriyi kabul ettiğinde, muhasebe yazılımına elle girilebilecek yapılandırılmış bir kayıt üretilir (otomatik gönderim değil — kullanıcı hâlâ kendi sistemine kendisi giriyor). İnceleyen/onaylayan rol ayrımı ve değişmez (immutable) bir denetim izi eklenir.

**Bunun IronLedger'ı bir "rapor üretici"den bir "kapanış operasyonu ürünü"ne dönüştürmesi nasıl olur:** Bugünkü ürün, her ay "burada bir rapor var" diyor ve biter — geçen ayki bulgu bu ayki çalışmayı etkilemiyor, kimin ne onayladığı kaydedilmiyor. Faz 2 sonrasında ürün "geçen ay ertelediğiniz 3 istisna hâlâ açık, bu ay 2 yeni istisna var, ikisi de sizin onayınızı bekliyor" diyebilir hâle gelir — yani tek seferlik bir çıktı değil, süregelen bir iş akışı olur. Bu, stratejik raporun "Close Investigation Workspace" (Kapanış İnceleme Çalışma Alanı) dediği şeyin temelidir.

### Faz 3 — Financial Flow Canvas (Finansal Akış Tuvali)

Tuval, süs amaçlı bir görselleştirme olarak ele alınmamalı.

**Hangi problemi çözüyor:** Bugün bir rakamın nereden geldiğini anlamak için (hangi dosya, hangi sütun, hangi eşleme kararı) kullanıcı birden fazla ekranı/tabloyu birbirine bağlamak zorunda. Tuval, bunu tek bir tıklanabilir görsel zincire dönüştürür.

**Ana kullanıcı yolculukları:** (1) Bir tablo satırına tıkla → hangi kaynak dosyalardan geldiğini gör. (2) Bir eşleme kuralına tıkla → hangi hesapları etkilediğini ve ne zamandan beri geçerli olduğunu gör. (3) Bir istisnaya tıkla → kaynak satırları, kuralı, güven skorunu gör.

**Düğümler (nodes):** Kaynak dosya → normalize edilmiş kayıt → eşleme kuralı → GL hesabı → tablo satırı (gelir tablosu kalemi) → istisna/varyans.
**Bağlantılar:** Her düğüm arasındaki oku tıklandığında, o dönüşümü yapan kural/hesaplama gösterilir.
**Detaya inme (drill-down):** Herhangi bir düğümden kaynak satırlara kadar inilebilmeli.
**Kaynak izlenebilirliği:** Bugünkü `source_breakdown` verisi (dosya + tutar + satır sayısı) bu görselleştirmenin temelini oluşturabilir, ama satır düzeyine inmiyor (Bölüm 2.5, 2.11'de not edildi) — bu sınırlama tuval için de geçerli olacak, satır düzeyi izlenebilirlik eklenmedikçe "şu satıra tıkla" deneyimi eksik kalır.
**Eşleme düzenleme:** Tuval üzerinden bir eşleme değiştirilebilmeli, ama önce "bu değişikliğin etkisi ne olur" önizlemesi gösterilmeli ve kayıt, sürümlü bir kural oluşturmalı (Faz 1'in mapping veri modeline dayanır).
**İstisna göstergeleri, gerçek tutarlar, onay durumu, dönem/şirket seçimi, yetkiler, sürüm geçmişi:** Bunların hepsi Faz 1 ve Faz 2'nin kalıcı verisine dayanır — bugünkü geçici (`parse_preview` JSONB) veri üzerine kurulursa, tıklanan düğümün arkasında kalıcı bir şey olmaz.

**Ön yüz gereksinimleri:** Yeni bir grafik/tuval kütüphanesi seçimi (bugün `frontend/package.json`'da hiçbiri yok — Bölüm 11'de karar maddesi). Performans riski: yüzlerce hesap ve binlerce kaynak satırı olan büyük şirketlerde tuval yavaşlayabilir; sanal kaydırma (virtualization) veya kademeli yükleme gerekebilir.
**Backend gereksinimleri:** Yeni bir "lineage" (soy ağacı) sorgu uç noktası — bugünkü `source_breakdown` verisini düğüm/bağlantı formatına dönüştüren bir servis.
**Veritabanı bağımlılığı:** Faz 1 (kalıcı eşleme) ve Faz 2 (denetim izi) tamamlanmadan tuval üzerinde anlamlı, kalıcı bir gezinme deneyimi kurulamaz.

**Tuvalden önce hangi veri temeli var olmalı:** Kalıcı, sürümlü eşleme kayıtları (Faz 1) ve onay/denetim izi (Faz 2). Bunlar olmadan tuval, her çalışmadan sonra sıfırlanan geçici veriye bakan "güzel ama boş" bir ekran olur.

### Faz 4 — Actual vs. Budget (Gerçekleşen vs. Bütçe)

**Başlangıç kapsamı:** Bütçe dosyası içe aktarma (mevcut dosya okuma araçları — `file_reader.py` — yeniden kullanılabilir), bütçe satırlarının hesaplara eşlenmesi (mevcut eşleme altyapısına benzer bir mantıkla), salt okunur gerçekleşen-bütçe karşılaştırması, fark tespiti (mevcut `comparison.py` mantığına benzer, pandas ile), farkın kaynağa kadar izlenebilmesi.

**Tam bütçeleme, tahminleme ve senaryo modellemesi neden ertelenmeli:** Bunlar çok daha büyük bir ürün yüzeyi (işbirlikli düzenleme, sürüm karşılaştırma, onay iş akışı, sürükle-bırak planlama arayüzü) gerektirir ve bugünkü ürünün henüz kanıtlamadığı bir müşteri talebine dayanır. Stratejik rapor da bunu 10-12. aya kadar ertelemeyi öneriyor; bu belge bu önerinin kod tabanının bugünkü olgunluğuyla tutarlı olduğunu doğruluyor — bugün bırakın bütçe tablosunu, gerçekleşen tarafın kendisi bile (Bölüm 3.1) hâlâ düzeltilmeyi bekliyor.

### Faz 5 — Planlama ve Senaryo Modellemesi (Koşullu)

Bu faz, aşağıdaki kanıtlar olmadan **başlatılmamalı**:
- En az birkaç pilot müşterinin Faz 4'ün salt-okunur bütçe karşılaştırmasını **düzenli olarak** (ay ay) kullandığının gösterilmesi.
- Müşterilerin açıkça "işbirlikli bütçe düzenleme" veya "senaryo karşılaştırma" talep ettiğinin somut kanıtı (görüşme notu, destek talebi, iptal sebebi vb.).
- Bu talebin, ürünün mevcut çekirdek değerini (kapanış/mutabakat) zayıflatmadan eklenebileceğinin değerlendirilmesi.

Kapsanacak alanlar (yalnızca yukarıdaki kanıt toplandıktan sonra tasarlanmalı): işbirlikli bütçeleme, tahmin sürümleri, sürücü bazlı (driver-based) planlama, senaryo modelleme, onay iş akışı, çok şirketli planlama.

---

## 6. Frontend Yol Haritası

| Faz | Değiştirilecek mevcut ekranlar | Yeni ekranlar | Ana bileşenler | API bağımlılığı | Yükleme/hata/boş durumlar | Yetkiler | Denetim görünürlüğü | UX riski | Sıra |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Yok (yalnızca arka uç düzeltmesi, görünür değişiklik yok) | — | — | — | — | — | — | Düşük | 1 |
| 1 | `MappingReview.tsx` — artık geçmiş eşlemeleri gösterebilmeli | — | `MappingHistoryPanel` (yeni, küçük) | `GET /account-mappings` (yeni) | Boş durum: "henüz eşleme geçmişi yok" | Yok (henüz rol ayrımı yok) | Kim onayladı bilgisi gösterilmeli | Kullanıcı "neden tekrar soruyor" diye şaşırabilir — geçmiş eşlemenin neden değiştiğini açıklamak gerekir | 2 |
| 2 | `ReconciliationPanel.tsx`, `ReportPage.tsx` | `ExceptionInboxPage.tsx` (yeni) | `ExceptionCard`, durum rozetleri (açık/ertelendi/kapatıldı), yorum alanı | `GET/PATCH /exceptions` (yeni) | Yükleniyor/hata/boş üç durumu da tanımlanmalı; boş durum "bu ay istisna yok, harika" gibi olumlu bir mesaj olmalı | İnceleyen/onaylayan ayrımı burada ilk kez gerekiyor — basit bir rol alanı yeterli, karmaşık RBAC gerekmez | Her durum değişikliğinin kim/ne zaman yaptığı görünmeli | Kullanıcılar "istisna kuyruğu" kavramına alışkın olmayabilir — ilk kullanımda kısa bir açıklama gerekebilir | 3 |
| 3 | — | `LineageCanvasPage.tsx` (yeni) | Seçilecek grafik kütüphanesine bağlı yeni bileşenler | Yeni "lineage" sorgu uç noktası | Büyük veri setlerinde performans/yükleme durumu kritik | Düzenleme yetkisi olmayan kullanıcı salt-okunur görmeli | Sürüm geçmişi düğümde görünmeli | En yüksek UX riski — kötü tasarlanırsa "şık ama kullanışsız" bir ekrana dönüşebilir; bu belge kasıtlı olarak görsel tasarım önermiyor, önce iş akışı doğrulanmalı | 4 |
| 4 | `ReportPage.tsx` — bütçe sütunu eklenmeli | `BudgetImportPage.tsx` (yeni) | Bütçe yükleme formu (mevcut `FileUpload.tsx` yeniden kullanılabilir) | Yeni bütçe uç noktaları | Bütçe eksikse "bütçe yüklenmedi" boş durumu | Yok (salt okunur, tek kullanıcı) | Gerekli değil (henüz onay akışı yok) | Kullanıcı bütçe ile gerçekleşeni karıştırabilir — görsel ayrım (renk/etiket) net olmalı | 5 |

**Erişilebilirlik (accessibility):** Bu incelemede mevcut bileşenlerin erişilebilirlik uyumluluğu (klavye navigasyonu, ekran okuyucu etiketleri) sistematik olarak test edilmedi — **Doğrulanmadı**. Radix UI bileşenleri (`@radix-ui/react-dialog` vb.) kullanılıyor olması iyi bir başlangıç noktası (bu kütüphaneler erişilebilirlik standartlarına göre tasarlanmış), ama özel bileşenlerin (örn. `MappingReview.tsx` içindeki tablo/seçim kutuları) erişilebilirliği doğrulanmadı.

Bu belge kasıtlı olarak görsel tasarım (renk, tipografi, animasyon) önermiyor — Bölüm 6'nın amacı iş akışı ve bilgi mimarisidir.

---

## 7. Backend Yol Haritası

| Faz | Değiştirilecek mevcut servisler | Yeni domain servisleri | API uç noktaları | Ajan sorumlulukları | Deterministik/LLM sınırı | Test gereksinimi |
|---|---|---|---|---|---|---|
| 0 | `consolidator.py` | — | — | Değişmiyor | Değişmiyor — düzeltme yalnızca pandas tarafında | Yeni regresyon + izolasyon testleri |
| 1 | `account_mapper.py`, `parser.py`, `supabase_repos.py` | `MappingRepo` (yeni repo arayüzü) | `GET/POST /account-mappings` | `AccountMapper` artık önce kaydı kontrol edip varsa Haiku'yu tekrar çağırmamalı (önbellek) | Eşleme kararı hâlâ LLM'den geliyor, ama saklama/sürümleme tamamen deterministik Python | Eşleme kalıcılığı ve önbellek isabet/ıskalama testleri |
| 2 | `interpreter.py` (suggested_action doldurma), `reports.py` deposu | `ExceptionRepo`, `JournalEntryDraftRepo`, `AuditRepo` | `GET/PATCH /exceptions`, `POST /exceptions/{id}/draft-je`, `GET /audit-events` | Interpreter, sınıflandırmaya göre yapılandırılmış öneri şablonunu seçiyor (LLM serbest metin yazmıyor, önceden tanımlı şablonlardan seçim yapıyor — Altın Kural'a uygun) | Öneri şablonu seçimi deterministik olmalı; LLM yalnızca hangi şablonun uygun olduğuna dair sınıflandırma yapmaya devam ediyor (zaten var olan sınırlama) | Şablon-seçim testleri, denetim izi bütünlük testleri |
| 3 | — | `LineageService` (yeni) | `GET /lineage/{company_id}/{period}` | Yok (LLM içermiyor, salt sorgu/dönüştürme) | Tamamen deterministik | Performans testi (büyük veri seti), doğruluk testi (görselleştirilen düğümlerin gerçek veriyle eşleştiği) |
| 4 | `file_reader.py` (bütçe formatları için yeniden kullanım), `comparison.py`'ye benzer yeni bir `BudgetComparisonAgent` | `BudgetRepo` | `POST /budgets/import`, `GET /budgets/{company_id}/{period}/variance` | Yeni ajan, gerçekleşen-bütçe farkını pandas ile hesaplıyor; Claude yalnızca yorumluyor | Değişmiyor — hesap yine pandas'ta | Bütçe içe aktarma + fark hesaplama testleri |

**Deterministik hesaplama sınırı korunmalı:** Her fazda, yeni bir "fark", "toplam" veya "yüzde" hesaplandığında bu hesaplama pandas/Python tarafında yapılmalı; Claude yalnızca zaten hesaplanmış rakamları yorumlamalı ve mevcut guardrail mekanizmasından geçmeli. Bu kural, mevcut kod tabanında tutarlı şekilde uygulandığı doğrulanan tek mimari ilke olduğu için (Bölüm 2), her yeni fazda da aynı disiplinle sürdürülmelidir.

**Idempotency (tekrar tetiklenmeye dayanıklılık):** `apply_mapping_and_consolidate` fonksiyonunun durum kontrolü yaptığı doğrulandı (`orchestrator.py:738-745`) — yeni eklenecek her arka plan görevi (background task) için aynı deseni (mevcut durumu kontrol et, beklenmeyen durumda sessizce çık) sistematik olarak uygulamak önerilir.

**Maliyet kontrolü:** `opus_upgrade.py`'nin her çalışma için ikinci bir Opus çağrısı yaptığı doğrulandı (Bölüm 3.3, madde 8). Yeni fazlarda LLM çağrı sayısı arttıkça, hangi çağrıların gerçekten ek değer kattığı (örn. iki Opus geçişinin kullanıcıya görünür bir farkı var mı) gözden geçirilmeli — bu belge kapsamında bu sorunun cevabı **Doğrulanmadı**, çünkü iki narrative'in kullanıcıya nasıl farklı yansıdığı incelenmedi.

---

## 8. Database Yol Haritası

Aşağıdaki tablolar bir **taslak veri modeli önerisidir — SQL migration dosyası oluşturulmamıştır**, yalnızca kavramsal tasarım.

### `account_mappings`
**Amaç:** Bir kaynak değerinin (örn. "AlarmTech Industries") hangi GL hesabına eşlendiğini kalıcı olarak saklamak.
**Önemli alanlar:** `id`, `company_id`, `source_pattern` (ham değer), `gl_account_id`, `confidence`, `created_by` (ajan mı kullanıcı mı), `effective_from` (hangi dönemden itibaren geçerli), `superseded_by` (bu kayıt başka bir kayıtla değiştirildiyse).
**İlişkiler:** `company_id → companies`, `gl_account_id → accounts`.
**Şirket izolasyonu:** `company_id` zorunlu, RLS politikası diğer tablolarla aynı desende (`owner_id = auth.uid()` üzerinden).
**Değişmezlik/sürümleme:** Bir eşleme değiştirildiğinde eski kayıt silinmemeli, `superseded_by` ile yeni kayda bağlanmalı — böylece "geçen ay neden farklı eşlenmişti" sorusu cevaplanabilir.
**Şimdi mi sonra mı:** **Şimdi (Faz 1).**

### `account_mapping_versions`
**Amaç:** `account_mappings` üzerindeki her değişikliğin ayrı bir sürüm kaydı olarak tutulması — eğer `account_mappings` tablosunun kendisi "geçerli olan" kaydı tutuyorsa, bu tablo "tüm geçmiş" kaydını tutar.
**Not:** Basit senaryoda `account_mappings` içindeki `superseded_by` alanı yeterli olabilir; ayrı bir sürüm tablosu yalnızca sürüm sayısı çoğaldıkça ve sorgu performansı önem kazandıkça gerekebilir.
**Şimdi mi sonra mı:** **Sonra** — Faz 1'de `superseded_by` yaklaşımıyla başlanabilir, ihtiyaç netleşince ayrılabilir.

### `mapping_reviews`
**Amaç:** Bir eşleme taslağının kullanıcı tarafından ne zaman, kim tarafından incelendiğini/onaylandığını kaydetmek.
**Önemli alanlar:** `id`, `company_id`, `run_id`, `reviewed_by`, `reviewed_at`, `decision` (onaylandı/reddedildi/değiştirildi).
**Şimdi mi sonra mı:** **Şimdi (Faz 1)** — bugünkü `discovery_approval_mode` alanının kapsamını genişleten bir yapı.

### `reconciliation_exceptions`
**Amaç:** Bugün her çalışmanın raporunda geçici olarak yaşayan `reconciliations` (JSONB) verisini, ay ay takip edilebilen, durumu olan kalıcı kayıtlara dönüştürmek.
**Önemli alanlar:** `id`, `company_id`, `period`, `account`, `classification`, `severity`, `status` (açık/ertelendi/kapatıldı), `assigned_to`, `gl_amount`, `non_gl_total`, `delta`.
**İlişkiler:** `company_id → companies`, dönem bazlı gruplama.
**Şimdi mi sonra mı:** **Faz 2.**

### `exception_actions`
**Amaç:** Bir istisna üzerinde yapılan her işlemin (yorum, durum değişikliği, atama) geçmişini tutmak.
**Önemli alanlar:** `id`, `exception_id`, `actor`, `action_type`, `note`, `created_at`.
**Değişmezlik:** Bu tablo yalnızca ekleme (append-only) olmalı — geçmiş işlem kaydı silinmemeli/güncellenmemeli.
**Şimdi mi sonra mı:** **Faz 2.**

### `journal_entry_drafts`
**Amaç:** Bir istisna için önerilen düzeltmenin, muhasebeciye "kopyala-yapıştır" yapılabilecek yapılandırılmış bir kayda dönüşmesi (borç/alacak satırları, hesap referansları).
**Önemli alanlar:** `id`, `exception_id`, `company_id`, `debit_account`, `credit_account`, `amount`, `memo`, `status` (taslak/kabul edildi/reddedildi).
**Not:** Bu, ERP'ye otomatik yazma **değildir** — kullanıcı hâlâ kendi muhasebe sistemine kendisi giriyor. Otomatik gönderim bu belgenin "şimdilik inşa edilmemeli" listesinde.
**Şimdi mi sonra mı:** **Faz 2.**

### `approvals`
**Amaç:** Genel amaçlı bir onay kaydı — hangi kaynak varlığın (rapor, eşleme, JE taslağı) kim tarafından onaylandığı.
**Önemli alanlar:** `id`, `company_id`, `entity_type`, `entity_id`, `approved_by`, `approved_at`.
**Şimdi mi sonra mı:** **Faz 2** — `mapping_reviews` ile birleştirilebilir veya ayrı tutulabilir, bu bir tasarım kararı (Bölüm 11).

### `audit_events`
**Amaç:** Değişmez (immutable), sistemdeki her önemli durum değişikliğinin (rapor tamamlandı, eşleme onaylandı, istisna kapatıldı) tek bir kronolojik kaydı.
**Önemli alanlar:** `id`, `company_id`, `event_type`, `actor`, `payload` (JSONB), `created_at`.
**Değişmezlik:** Kesinlikle yalnızca ekleme; hiçbir satır güncellenmemeli/silinmemeli.
**Şimdi mi sonra mı:** **Faz 2.**

### `source_records` / lineage kayıtları
**Amaç:** Bugünkü `source_breakdown` (dosya + tutar + satır sayısı, JSONB) verisinin satır düzeyine indirgenmiş hâli — tuval (Faz 3) için gerekli olan asıl izlenebilirlik.
**Not:** Bu, `discovery-layer-plan.md`'de bilinçli olarak "post-MVP" diye ertelenen `source_row_index` kavramının yeniden ele alınması anlamına gelir — bilinçli bir geri dönüş, hata değil.
**Şimdi mi sonra mı:** **Faz 3 öncesi gerekli**, Faz 2'de değil.

### `budgets`, `budget_versions`, `budget_lines`
**Amaç:** İçe aktarılan bütçe dosyalarının hesap bazlı satırlarını, hangi sürüme (örn. "2026 Q1 revize") ait olduklarını saklamak.
**Şimdi mi sonra mı:** **Faz 4.**

### `variance_investigations`
**Amaç:** Bir gerçekleşen-bütçe farkının kullanıcı tarafından araştırılıp not düşülmesi — `reconciliation_exceptions`'a benzer bir desen, ama bütçe tarafı için.
**Şimdi mi sonra mı:** **Faz 4, muhtemelen `reconciliation_exceptions` ile ortak bir taban şema paylaşabilir** (Bölüm 11'de karar maddesi).

**Genel not:** Yukarıdaki tüm tablolar için RLS beklentisi, mevcut `0001_initial_schema.sql`'deki desenle aynı olmalı (`company_id` üzerinden `companies.owner_id = auth.uid()` kontrolü) — ama Bölüm 3.2'de belirtildiği gibi, bu politikaların backend trafiğinde fiilen devreye girmesi için servis-rolü mimarisinin de gözden geçirilmesi gerekiyor.

---

## 9. Güvenlik ve Finansal Kontroller

**Kimlik doğrulama:** Çalışıyor, Supabase Auth + JWT üzerinden (Bölüm 3.2). Doğrulandı.
**Yetkilendirme (authorization):** `company_id` sunucu tarafında JWT'den çözülüyor, istemciden alınmıyor. Doğrulandı. Ama rol bazlı yetkilendirme (kim ne yapabilir) henüz yok.
**Kiracı izolasyonu / RLS / servis-rolü kullanımı:** Bölüm 3.2'de ayrıntılı. Politikalar var ama fiilen devrede değil; izolasyon uygulama koduna dayanıyor ve test edilmiyor.
**En az yetki (least privilege):** Servis rolü anahtarı tüm veritabanına tam erişim veriyor — "en az yetki" ilkesinin tam tersi bir durum. Uzun vadede gözden geçirilmeli (Bölüm 3.2, Seçenek B).
**PII (kişisel veri) temizleme:** İki katmanlı, gerçek örnek verilerle (bordro dosyalarındaki isim/çalışan no sütunları) test edilmiş durumda doğrulandı (`pii_sanitizer.py`). Güçlü bir alan.
**Dosya güvenliği / imzalı URL'ler (signed URLs):** Bu incelemede `backend/adapters/supabase_storage.py`'nin imzalı URL kullanıp kullanmadığı ayrıntılı olarak doğrulanmadı — **Doğrulanmadı**.
**Veri saklama (retention):** Tamamlanan çalışmalar sonrası dosyanın depodan silindiği doğrulandı (`orchestrator.py:414-433`, `run_comparison_and_report` içinde `get_file_storage().delete(storage_key)`). Ama genel bir veri saklama/silme politikası (örn. "X ay sonra rapor verisi silinir") **Doğrulanmadı**.
**Denetim logları:** Yapısal loglama var (`trace_id` ile, `backend/logger.py`) ama kalıcı, sorgulanabilir bir denetim izi tablosu yok (Bölüm 3.3, madde 14).
**Onay kontrolleri / görev ayrılığı (separation of duties):** Yok — bugün tek kullanıcı bir şirketin sahibi ve tüm işlemleri tek başına yapıyor (`companies.owner_id` 1:1). İnceleyen/onaylayan ayrımı Faz 2'de planlanıyor.
**LLM veri maruziyeti:** PII, Claude'a gönderilmeden önce iki katmanlı temizlemeden geçiyor (doğrulandı). Ama yüklenen dosyaların içeriğinin tamamı (PII olmayan kısmı) yine de Anthropic API'sine gönderiliyor — bu, herhangi bir üçüncü taraf LLM kullanımının doğal sonucu ve ayrı bir müşteri sözleşmesi/veri işleme anlaşması (DPA) konusu, bu belgenin teknik kapsamı dışında.
**Yüklenen dosyalar üzerinden prompt injection riski:** Kullanıcının yüklediği bir Excel dosyasındaki bir hücrenin, Claude'a "sen artık farklı bir talimat izle" gibi bir metin içermesi teorik bir risktir. Bu incelemede bu senaryoya karşı özel bir savunma (örn. talimat/veri ayrımı, sistem promptunun dosya içeriğinden izole edilmesi) kodda **doğrulanmadı** — prompt dosyaları (`backend/prompts/*.txt`) okunmadı bu inceleme kapsamında, bu nedenle **Doğrulanmadı**.
**Sayısal güvenlik ağı (guardrail):** Çalışıyor ve doğrulandı (Bölüm 2.8), ama Bölüm 3.1'in gösterdiği gibi, guardrail yalnızca "Claude'un yazdığı rakam pandas çıktısında var mı" diye bakıyor — pandas çıktısının kendisinin doğru olup olmadığını garanti etmiyor. Bu önemli bir kavramsal sınır: guardrail bir "tutarlılık kontrolü", bir "doğruluk kontrolü" değil.
**Yedekleme ve kurtarma (backup/recovery):** Supabase'in kendi otomatik yedekleme mekanizmaları dışında, projeye özgü bir yedekleme/kurtarma stratejisi bu incelemede **doğrulanmadı**.
**Olay görünürlüğü (incident visibility):** Guardrail hatası, rate-limit aşımı gibi durumlar kullanıcıya düz metinle gösteriliyor (`messages.py`) — doğrulandı. Ama operasyon ekibine (siz) bir olay gerçekleştiğinde otomatik bildirim gönderen bir mekanizma (örn. Slack/e-posta uyarısı) **doğrulanmadı**.

**Öncelik gruplaması:**

*Pilot müşteriler öncesi mutlaka olmalı:*
- Kiracı izolasyonu testi (Bölüm 3.2)
- Konsolidasyon düzeltmesi (Bölüm 3.1)
- `MAPPING_FAILED` mesaj hatası düzeltmesi

*Üretim (daha geniş müşteri kitlesi) öncesi mutlaka olmalı:*
- Denetim izi (audit_events)
- İnceleyen/onaylayan rol ayrımı
- Servis-rolü mimarisinin gözden geçirilmesi (en azından test kapsamının genişletilmesi)
- Veri saklama politikasının netleştirilmesi

*Daha sonraki kurumsal (enterprise) gereksinimler:*
- SOC 2 benzeri uyumluluk hazırlığı
- Görev ayrılığının tam RBAC ile desteklenmesi
- Çok şirketli (multi-entity) izolasyon modeli

---

## 10. Test Stratejisi

| Test türü | Bugünkü durum | Gerekli eklemeler |
|---|---|---|
| Birim testleri (unit) | Var — `tests/agents/`, `tests/tools/` altında | Faz 0 sonrası: yeni GL-öncelik regresyon testi |
| Konsolidasyon regresyon testleri | Var (`test_consolidator.py`) ama çift-sayım senaryosunu test etmiyor | GL+departman çakışma senaryosu testi (Bölüm 3.1) |
| Parser testleri | Var (`test_parser_end_to_end.py`) ama **bozuk** (Bölüm 2.12) | Fixture onarımı öncelikli |
| Mapping testleri | Var (`test_account_mapper.py`) | Faz 1 sonrası: kalıcılık/önbellek testleri |
| API entegrasyon testleri | Var (`test_confirm_mappings.py`) | Yeni uç noktalar için genişletme |
| Kiracı izolasyonu testleri | **Yok** | Bölüm 3.2 — en yüksek öncelik |
| RLS testleri | **Yok** | Servis-rolü mimarisi netleşince eklenmeli |
| Uçtan uca kapanış akışı testi | Doğrulanmadı — böyle bir test dosyası bu incelemede görülmedi | Yükleme → onay → rapor tamamlanana kadar tam akışı doğrulayan bir test |
| Sayısal guardrail testleri | Var (`test_guardrail.py`) | Yeterli görünüyor, ek gereksinim yok şimdilik |
| Migration testleri | Doğrulanmadı — migration'ların otomatik olarak sınandığı bir mekanizma bu incelemede görülmedi | En azından "migration'lar sırayla, hatasız uygulanıyor mu" kontrolü |
| Tuval lineage testleri | Henüz uygulanabilir değil (özellik yok) | Faz 3 ile birlikte tasarlanmalı |
| Bütçe-gerçekleşen testleri | Henüz uygulanabilir değil | Faz 4 ile birlikte tasarlanmalı |

**Gerçekçi finansal test verisi:** `docs/demo_data/` altındaki 6 sektör senaryosu (clearview, corebuilt, harvest, helix, sentinel, vandelay), her biri GL + 3-4 ek kaynak dosyasıyla, gerçekçi test verisi için iyi bir temel oluşturuyor — ama bugün hiçbir otomatik test bu klasördeki dosyaları başarıyla okuyamıyor (Bölüm 2.12). Önerilen: Faz 0'da fixture onarımı yapılırken, bu 6 senaryodan en az birinin (örn. sentinel — tek çok-aylı veri seti) otomatik testlere kalıcı olarak bağlanması, böylece gerçek dosya biçimleriyle sürekli sınama sağlanır.

---

## 11. Karar Verilmesi Gereken Konular

| # | Karar | Seçenekler | Önerilen | Gerekçe | Risk | Ne zaman karar verilmeli | Uygulama bloke mi |
|---|---|---|---|---|---|---|---|
| 1 | GL yetkili kayıt mı olacak? | (a) Evet, GL varsa her zaman GL tutarı esas alınır (b) Hayır, tüm kaynaklar eşit ağırlıklı | (a) | Hem CLAUDE.md hem stratejik rapor hem muhasebe pratiği bunu destekliyor | (b) seçilirse bugünkü mutabakat mantığının tamamı yeniden tasarlanmalı | Faz 0 başlamadan önce | **Evet — Faz 0'ı bloke ediyor** |
| 2 | GL yoksa destekleyici kaynaklar nasıl ele alınacak? | (a) Toplanır (bugünkü davranış) (b) En güvenilir tek kaynak seçilir (c) Kullanıcıya sorulur | (a), yalnızca GL hiç yoksa | Bugünkü `is_source_only` mantığı zaten bunu ayrıca işaretliyor | Yanlış seçilirse GL'siz şirketlerde de çift sayım riski sürer | Faz 0 | Evet |
| 3 | Eşleme granülerliği (mapping granularity) — tek katman mı, 4 katman mı? | (a) Tek katman + kalıcılık (b) Doğrudan 4 katmana geç | (a) | Kanıtsız 4 katmanlı tasarım riskli; tek katmanı kalıcı yapmak daha hızlı değer üretir | (b) seçilirse Faz 1 süresi katlanarak uzar | Faz 1 başlamadan önce | Evet — Faz 1'i bloke ediyor |
| 4 | İstisna taksonomisi (6 kategori) genişletilecek mi? | (a) Bugünkü 6 kategori korunur (b) Yeni kategoriler eklenir | (a), en azından Faz 2 sonuna kadar | Bugünkü 6 kategori zaten kod ve testlerle iyi entegre; erken genişletme karmaşıklık katar | Gerçek kullanım "kategori yetersiz" derse revize gerekir | Faz 2 ortası, kullanım verisiyle | Hayır |
| 5 | Taslak yevmiye kaydı kapsamı | (a) Yalnızca öneri/kopyala-yapıştır (b) ERP'ye otomatik yazma | (a) | Otomatik yazma, hem stratejik raporun hem bu belgenin "şimdilik yapma" listesinde | (b) erken yapılırsa geri alınamaz muhasebe hataları riski | Faz 2 tasarımı sırasında | Evet — Faz 2'yi bloke ediyor |
| 6 | Tuval teknolojisi | (a) React tabanlı graf kütüphanesi (örn. reactflow) (b) Özel SVG/Canvas çizimi (c) Üçüncü taraf gömülü araç | Doğrulanmadı — bu belge bir teknoloji önermiyor, çünkü bugünkü kod tabanında hiçbir seçim yapılmamış | — | Yanlış seçim, Faz 3'ün büyük bir kısmının yeniden yazılmasına yol açabilir | Faz 3 başlamadan önce, ayrı bir teknik değerlendirmeyle | Evet — Faz 3'ü bloke ediyor |
| 7 | İnceleme/onay modeli | (a) Basit tek-rol (herkes onaylayabilir) (b) İnceleyen/onaylayan ayrımı (iki kişi kuralı) | (b), en azından opsiyonel olarak | Muhasebe/denetim bağlamında "aynı kişi hazırlayıp onaylamasın" beklentisi yaygın | (a) seçilirse kurumsal müşteriler için sonradan zor bir geçiş | Faz 2 tasarımı sırasında | Evet — Faz 2'yi bloke ediyor |
| 8 | Bütçe dosya formatı | (a) Serbest Excel/CSV, mevcut parser yeniden kullanılır (b) Sabit şablon zorunlu | (a) | Mevcut altyapı (Discovery, Normalizer) zaten esnek formatları ele alıyor | (b) kullanıcı sürtünmesini azaltır ama esnekliği kaybeder | Faz 4 tasarımı sırasında | Hayır |
| 9 | Çok şirketli (multi-entity) desteğin zamanlaması | (a) Faz 3 sonrası (b) Daha erken | (a) | Bugünkü kimlik modeli (`companies.owner_id` 1:1) buna hazır değil; erken girişim büyük bir mimari yeniden yapılanma gerektirir | Erken talep gelirse fırsat kaybı riski | Sürekli izlenmeli, resmi karar Faz 2 sonunda | Hayır (ama gecikirse müşteri kaybı riski olabilir) |
| 10 | Servis-rolü mimarisi | (a) Bugünkü yapı + kapsamlı test (b) Kullanıcı JWT'si ile gerçek RLS'e geçiş | (a), pilot için; (b) üretim ölçeği için değerlendirilmeli | (b) daha güvenli ama daha büyük bir mühendislik işi; altyapı parçaları (`supabase_jwt_secret`) zaten mevcut | (a) yeterince test edilmezse veri sızıntısı riski sürer | Faz 0'da (a), üretim öncesi (b) yeniden değerlendirilmeli | Faz 0 — (a) uygulanmadan pilot müşteri alınmamalı |

---

## 12. Önceliklendirilmiş Backlog

| ID | Görev | Faz | Öncelik | Katman | Bağımlılık | Karmaşıklık | Risk | Kabul kriteri | Kurucu onayı gerekli mi |
|---|---|---|---|---|---|---|---|---|---|
| B-01 | GL/departman toplama hatasını düzelt | 0 | P0 | Backend | Karar #1, #2 | S | Düşük (izole değişiklik) | GL+departman çakışan hesapta tutar=GL tutarı | Evet |
| B-02 | Kiracı izolasyonu testi yaz | 0 | P0 | Testing/Security | Karar #10 | M | Düşük | İki-JWT testi, çapraz şirket erişimi engelleniyor | Evet |
| B-03 | Bozuk fixture'ı onar | 0 | P1 | Testing | — | S | Düşük | 5 entegrasyon testi tekrar yeşil | Hayır |
| B-04 | Ölü kodu temizle (`run_multi_file_parser_until_preview`) | 0 | P2 | Backend | — | S | Çok düşük | Kullanılmayan fonksiyon silinmiş veya belgelenmiş | Hayır |
| B-05 | `MAPPING_FAILED` çakışmasını düzelt | 0 | P1 | Backend | — | S | Çok düşük | Hata mesajı sütun adlarını içeriyor | Hayır |
| B-06 | Dokümantasyonu güncelle (CLAUDE.md, mimari dosyaları) | 0 | P2 | Docs | — | M | Yok | Belgeler gerçek ajan/migration/uç nokta sayısını yansıtıyor | Hayır |
| B-07 | `account_mappings` veri modelini tasarla ve uygula | 1 | P1 | Database/Backend | Karar #3 | L | Orta | Eşleme kararları kalıcı, sürümlü | Evet |
| B-08 | `MappingReview.tsx`'i geçmiş eşlemeleri gösterecek şekilde genişlet | 1 | P1 | Frontend | B-07 | M | Düşük | Kullanıcı geçmiş eşlemeyi görebiliyor | Hayır |
| B-09 | `reviewed_by`/`reviewed_at` alanlarını ekle | 1 | P2 | Database/Backend | — | S | Düşük | Rapor kim tarafından incelendiği kaydediliyor | Hayır |
| B-10 | `suggested_action`'ı yapılandırılmış veri hâline getir | 1 | P1 | Backend | — | M | Düşük | Her mutabakat kaleminde dolu, yapılandırılmış öneri var | Hayır |
| B-11 | `reconciliation_exceptions` + istisna kutusu (exception inbox) | 2 | P1 | Backend/Frontend/Database | B-07, Karar #4 | XL | Orta | Kullanıcı ay ay istisna takip edebiliyor | Evet |
| B-12 | Taslak yevmiye kaydı (draft JE) modeli | 2 | P2 | Backend/Database | B-11, Karar #5 | L | Orta (muhasebe hatası riski) | Kullanıcı öneriyi yapılandırılmış JE olarak indirebiliyor | Evet |
| B-13 | İnceleyen/onaylayan rol ayrımı | 2 | P1 | Backend/Frontend/Database | Karar #7 | L | Orta | İki farklı kullanıcı hazırlama/onaylama yapabiliyor | Evet |
| B-14 | Değişmez denetim izi (`audit_events`) | 2 | P1 | Database/Backend | — | M | Düşük | Her önemli işlem kalıcı, silinemez şekilde kayıtlı | Hayır |
| B-15 | Satır düzeyinde kaynak izlenebilirliği | 3 (ön koşul) | P2 | Backend/Database | — | L | Düşük | Her tablo satırı kaynak dosyanın hangi satırından geldiğini gösterebiliyor | Hayır |
| B-16 | Tuval teknolojisi seçimi ve prototip | 3 | P2 | Frontend | Karar #6 | L | Yüksek (yanlış seçim maliyetli) | Teknik değerlendirme raporu + küçük prototip | Evet |
| B-17 | Lineage sorgu servisi | 3 | P2 | Backend | B-15 | L | Orta | Tuval için düğüm/bağlantı verisi API'den geliyor | Hayır |
| B-18 | Bütçe içe aktarma | 4 | P3 | Backend/Frontend | Karar #8 | M | Düşük | Bütçe dosyası yüklenip hesaplara eşlenebiliyor | Evet |
| B-19 | Gerçekleşen-bütçe fark hesaplama | 4 | P3 | Backend | B-18 | M | Düşük | Fark pandas ile hesaplanıyor, Claude yalnızca yorumluyor | Hayır |
| B-20 | Servis-rolü mimarisinin üretim öncesi gözden geçirilmesi | — (sürekli) | P1 | Security | Karar #10 | L | Orta-Yüksek | Karar #10 (b) seçeneği değerlendirilmiş ve belgelenmiş | Evet |

---

## 13. Phase Gates (Aşama Onay Kapıları)

Hiçbir aşama, kendi onay kapısı geçilmeden uygulamaya başlamamalı:

- **Gate 0:** Bu belgedeki doğruluk bulguları (Bölüm 3) kurucu tarafından onaylandı — özellikle Bölüm 3.1'deki GL/departman toplama hatasının gerçek olduğu ve önceliklendirildiği kabul edildi.
- **Gate 1:** Faz 0 uygulama planı (Bölüm 5, Faz 0 tablosu) onaylandı — hangi görevlerin hangi sırayla yapılacağı netleşti.
- **Gate 2:** Faz 1'in eşleme veri modeli (Bölüm 8'deki `account_mappings` tasarımı) onaylandı — özellikle Karar #3 (tek katman mı 4 katman mı) netleşti.
- **Gate 3:** Faz 2'nin istisna iş akışı (Bölüm 5, Faz 2 + Karar #5, #7) onaylandı — özellikle taslak JE kapsamı ve inceleyen/onaylayan modeli netleşti.
- **Gate 4:** Faz 3'ün tuval UX ve mimarisi (Bölüm 5, Faz 3 + Karar #6) onaylandı — teknoloji seçimi ve veri temeli hazırlığı netleşti.
- **Gate 5:** Faz 4'ün bütçe-gerçekleşen kapsamı (Bölüm 5, Faz 4 + Karar #8) onaylandı.

---

## 14. Recommended Immediate Next Step (Önerilen İlk Adım)

**İlk araştırılması gereken konu:** `consolidator.py`'deki GL/departman toplama davranışının, gerçek bir demo senaryosuyla (örn. `docs/demo_data/harvest` — GL + POS satışları + teslimat + bordro + tedarikçi faturaları, 5 kaynaklı bir senaryo) uçtan uca çalıştırılıp, bugün gerçekten kaç hesapta çift sayım oluştuğunun somut olarak gösterilmesi. Bu, Bölüm 3.1'in kod okumasıyla doğrulanan bulgusunu, çalışan bir örnekle daha da somutlaştırır ve düzeltmenin önceliğini kurucuya net şekilde gösterir.

**Doğrulamadan sonraki ilk uygulama görevi:** B-01 — `consolidator.py`'nin `_roll_up` fonksiyonunda GL önceliğinin tutar alanına da uygulanması (Bölüm 3.1'deki öneri).

**Etkilenmesi muhtemel dosyalar:** `backend/agents/consolidator.py`, `tests/agents/test_consolidator.py`, dolaylı olarak `backend/agents/orchestrator.py` (tutar kaynağını değiştirmez ama davranış değişikliğini miras alır).

**Önce yazılması gereken testler:** GL+departman çakışması senaryosu için yeni bir regresyon testi (Bölüm 3.1) ve kiracı izolasyonu testi (Bölüm 3.2) — ikisi de kod değişikliğinden **önce** yazılmalı ki düzeltmenin doğruluğu ve mevcut davranışın hiçbir yerde bozulmadığı kanıtlanabilsin.

**Kurucu ile görüşülmesi gereken kararlar:** Karar #1 ve #2 (Bölüm 11) — GL'nin ne zaman ve nasıl yetkili kabul edileceği, GL olmayan senaryolarda toplamanın nasıl davranacağı. Bu iki karar netleşmeden B-01 uygulamaya başlanmamalı, çünkü düzeltmenin "doğru" davranışı bu kararlara bağlı.

---

## Bu Doküman Nasıl Kullanılmalı?

Bu belge **yaşayan bir taslaktır**, tek seferlik bir teslimat değildir. Her faz, uygulamaya başlanmadan önce ayrı ayrı tartışılmalı, gerekirse revize edilmeli ve kurucu tarafından açıkça onaylanmalıdır (Bölüm 13'teki onay kapıları). Bir fazın planı onaylandıktan sonra bile, uygulama sırasında ortaya çıkan yeni bulgular bu belgeye geri yansıtılmalı — belge kodun gerisinde kalmamalı.

Bu belgenin kendisi de kod tabanı değiştikçe güncelliğini yitirebilir (tıpkı CLAUDE.md ve `docs/01-architecture/` dosyalarının bugün güncelliğini yitirmiş olması gibi — Bölüm 2.13). Bu nedenle her büyük fazın sonunda, bu belgenin ilgili bölümlerinin gerçek kod durumuyla hâlâ örtüştüğü yeniden kontrol edilmelidir.

**Bu belgenin hazırlanması sırasında hiçbir uygulama kodu, migration dosyası veya özellik değiştirilmedi/oluşturulmadı — yalnızca bu planlama belgesi yazıldı.**
