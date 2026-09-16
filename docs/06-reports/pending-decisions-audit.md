# Karar verilmiş ama üretilmemiş işler — çapraz doküman taraması

*7 Eylül 2026. `main` + `claude/iron-ledger-review-cs3x9p` HEAD'i (`e41c2f2`) üzerinden.*
*Amaç: `docs/` altındaki ~30 dosyayı tek tek okuyup üç soruyu ayırmak — (1) karar verilmiş ama hâlâ kod olmayan iş, (2) bilinçli olarak beklemeye alınmış iş, (3) doküman zaten kodu anlatmıyor / yalan söylüyor. Konsolidasyon öncesi envanter niyetiyle yazıldı — hangi dosyanın arşive gideceğine, hangisinin güncelleneceğine, hangisinin backlog'a gireceğine buradan karar verilebilir.*

**Yöntem:** Her iddia için ilgili kodu (`backend/`, `frontend/`) grep'leyip doğruladım; sadece dokümanın kendi ifadesine güvenmedim. Test suite bu HEAD'de `501 passed, 5 skipped` (taze venv'de yeniden çalıştırıldı).

---

## 1. Gerçek boşluklar — karar verilmiş, henüz kodlanmamış

Önem sırasına göre.

### 1.1 Close-flow — Dil 1 bitti, Dil 2 şimdilik açık
**Kaynak:** `docs/02-planning/close-flow-contract.md`; uygulama kaydı `docs/sprint/pre-analysis-close-checklist.md`
**Durum (16 Eylül 2026):** Sözleşmenin *ilk iskelet* dilimi (raporu checklist gibi okutmak) **Dil 1 olarak kodlandı**: Python `tie_out_summary`, GET `/report` `tie_out_group`, sayfa sırası tie-out → istisna (Payroll / Vendors / Contracts / Other) → coverage → anlatı → oturumluk banka kutusu. `closed` hâlâ yok.

**Şimdilik açık bırakıldı (Dil 2, 16 Eylül 2026):** isimli beş kontrol (install/fuel dahil), `SourceFileType` iğneleri, dosya-toplamı→GL eşleme modu. Redhawk’ta üç destek dosyası var; install/fuel fixture yok. Dosyası olmayan kontrolü “passed” saymak ve etiket uydurmak yasak. Yanlış GL hedefi sahte temiz/sahte açık üretir. Yeniden açmak yeni bir kilit ister (gerçek demo dosyası + file-total modu, sonra etiket). Dil 3 (`closed` / SQL) ayrı ve daha sonra.

Bu madde artık “hiç başlamamış ilk dilim” değil. Okuyan kişi Dil 2’yi unutulmuş iş sanmasın: **bilinçli açık**.

### 1.2 Agentic-memory roadmap Phase 3 — Persisted Quarterly Artifacts
**Kaynak:** `docs/02-planning/agentic-memory-roadmap.md` §2 Phase 3
**Durum:** Phase 1 (recurring anomaly detection) VE Phase 2 (on-demand quarterly report) canlıda — doğrulandı: `backend/agents/comparison.py:131` `list_account_flag_counts_before` çağırıyor, `backend/agents/quarterly.py` mevcut ve recurrence gruplama (`recurrence_count` 3/2/1) kodda var. **Phase 3 açıkça "post-demo, production'dan önce" olarak zamanlanmış** (migrasyon `0009_add_report_type_and_quarterly.sql` — bu numara zaten `discovery-layer-plan.md`'de farklı bir amaç için de anılıyor, çakışma riski var, bkz. §4.2) ve hiç yazılmamış: `report_type`, `quarter`, `year` kolonları `reports` tablosunda yok, `is_recurring` boolean `anomalies`'te yok, stale-quarterly-on-monthly-rerun mantığı yok.

**Not:** Bu bilinçli bir erteleme (dokümanın kendisi "post-demo, before production" diyor) — ama "production" tarihi belirsiz ve iş hâlâ backlog'da hiçbir yerde görünmüyor. `risks.md`'ye R-numarası ile girmemiş.

### 1.3 Guardrail Stage 2 — narrative/numbers_used tutarlılığı hâlâ warn-only
**Kaynak:** `backend/tools/guardrail.py:22` `ENFORCE_NARRATIVE_CONSISTENCY = False`
**Doğrulandı:** `docs/sprint/test-plan-full-product.md` §E "Note on E2" ve `docs/audit_results.md` (c) tablosu satır 1 — ikisi de aynı bayrağı, aynı nedenle ("bir ölçüm turu bitmeden enforce etme") açık olarak işaretliyor. Şu anki canlı ölçüm: Redhawk raporunda **0 ihlal** (`test-plan-full-product.md` §E2). Bir ölçüm turu geçti, bayrak hâlâ kapalı — flip etme kararı kimseye ait değil, dokümante edilmiş ama tetiklenmemiş.

### 1.4 Quarterly ve Opus-upgrade path'leri hâlâ eski (non-strict) guardrail toleransında
**Kaynak:** `docs/audit_results.md` (c) tablosu satır 2-3
**Doğrulandı:** `grep -n "strict=True" backend/agents/*.py` → yalnızca `interpreter.py:526`. `quarterly.py` ve `opus_upgrade.py` `strict` parametresi geçmiyor → `verify_guardrail`'in eski `max(1%, $1,000)` toleransını kullanıyorlar, `CLAUDE.md`'nin "aylık interpreter strict, quarterly/opus-upgrade legacy tolerance kullanıyor (belgelenmiş)" notuyla tutarlı — yani bu **CLAUDE.md'de zaten kabul edilmiş bir borç**, ama audit'in belirttiği asıl sorun şu: quarterly ve opus prompt'ları hâlâ Claude'dan türetilmiş değer istiyor (`{N} of {M}`, `year-1`, "net position if derivable") — bu ikisi düzeltilmeden strict'e geçiş mümkün değil. Migrasyon planı yok.

### 1.5 "exception_three_way_matches" — invalid classification token bug
**Kaynak:** `docs/sprint/test-plan-full-product.md` gap #7b, bu oturumda kullanıcı tarafından da doğrulandı.
**Durum:** Bu depoda (`e41c2f2` HEAD) **hâlâ açık** — commit geçmişinde bir düzeltme yok. Kullanıcı bunu **kendi makinesinde** çözdüğünü ama commit/push etmediğini belirtti; bu uzak oturumun çalışma kopyasında değişiklik yok (`git status` temiz, `git log` içinde ilgili bir commit yok). Yani: iki farklı yerde iki farklı durum var — local'de çözüm var, bu repo'da (ve GitHub'da) yok. Push edilene kadar "çözüldü" sayılmamalı.

---

## 2. Bilinçli olarak beklemeye alınmış işler (gap değil, karar)

Bunlar backlog değil — tetikleyici koşulu net, "unutulmuş" değil. Yine de tek yerde toplanmaları gerekiyor çünkü şu an dört farklı dosyaya dağılmış.

| İş | Kaynak | Tetikleyici (döndüğünde tekrar açılır) |
|---|---|---|
| **Item 2** — Truck stock / van inventory | `docs/sprint/kova2-implementation-plan.md` "Item 2" | Bir bayiden gerçek count-vs-GL workbook gelirse (SKU, qty, location, opening) |
| **Item 3** — Central-station wholesale accrual | aynı dosya, "Item 3" | Item 4 canlıya çıktıktan **sonra** (çıktı — bkz. §3) VE bir bayiden central-station faturası gelirse |
| **Item 6** — WIP / professional services | aynı dosya, "Item 6" | Açık bir ürün kararı: profesyonel hizmetler dikeyine satış yapılacaksa |
| pgvector, ERP API entegrasyonu, multi-user/role, budget vs actuals, draft JE | `docs/02-planning/scope.md` "Future Roadmap", `docs/03-sprint/risks.md` R-100–R-104 | Post-MVP, tarih yok |
| Number-level prose provenance, TrendChart/MetricCard/HistoryList, Redis rate-limit, mypy strict, CI/CD, multi-recipient mail | `risks.md` R-105–R-120 | Post-MVP, tarih yok |
| **Storage TTL sweep** (guardrail_failed run'ların dosyaları) | `CLAUDE.md` Storage cleanup bölümü + `risks.md` R-115 | Production öncesi |

**Item 3 artık gerçekten Item 4'e bağımlı ve Item 4 çoktan bitti** (`backend/tools/roster_counts.py` var, `e41c2f2` öncesi commit'lerde canlı doğrulandı — bkz. sohbetin önceki turu). Yani Item 3'ün tetikleyicisinin yarısı **artık gerçek**: sadece "bir bayiden central-station faturası" bekleniyor, "Item 4 bitmesi" koşulu zaten sağlandı. Bunu `kova2-implementation-plan.md`'ye not düşmek gerek — şu an dosya hâlâ "Item 4 sonrası" diyor, sanki hâlâ gelecek zamanmış gibi okunuyor.

---

## 3. Yarım kalanlar — bir yolda var, ötekinde yok

Bunlar ne "yapıldı" ne "yapılmadı" — kısmi implementasyon, dokümante edilmiş açık uçlar.

| # | Konu | Ne var | Ne eksik | Kaynak |
|---|---|---|---|---|
| 3.1 | Migrasyon `0010` | Kolon ekleme `IF NOT EXISTS` ile korunuyor | `ADD CONSTRAINT` korunmuyor — ikinci çalıştırma hata verir | `audit_results.md` Tour 2 E.1 |
| 3.2 | Item 5 testleri | Tier 2 routing gerçekten çalışıyor (`test_tier2_payroll_fires_at_lower_gates` ayırt ediyor) | `test_icp_100k_250k_salaries_flags` ve `test_payroll_name_uses_tier2_of_band` **ayırt etmiyor** — payroll adı silinse de aynı sonucu verirler | `audit_results.md` Tour 2 E.2 |
| 3.3 | `seed.sql` | Redhawk demo şirketi var | `monthly_revenue_band` set edilmemiş → Item 5 fail-safe `$50k/$10k` gate'inde kalıyor, hiç kendi bandını kullanmıyor | `audit_results.md` Tour 2 E.3 |
| 3.4 | `500k_plus` bandı | Diğer üç bant revenue-scaled | Üstte sınırsız, `$500k/ay` ile `$5M/ay` şirket aynı gate'i alıyor | `audit_results.md` Tour 2 E.4 |
| 3.5 | Yüzde gate'leri | Dolar gate'leri banda göre ölçekleniyor | Yüzde gate'leri (`_TIER1_PCT`, `_TIER2_PCT`) sabit — küçük şirket için yüzde gate bağlayıcı kalıyor | `audit_results.md` Tour 2 E.5 |
| 3.6 | `_crosses_period_boundary` / `_deposit_column_signal` | Roster/renewal hariç tutma çalışıyor | Hesap bazında değil, **tüm dosya** taranıyor — bir gelecek tarihli satır dosyadaki her recon item'ı etkileyebilir | `audit_results.md` Tour 1 E.2 |
| 3.7 | `_is_processor_fee_gap` | Deposit vs fee ayrımı var | Herhangi iki taraflı %3–8 fark, dosya/hesap kimliği veya yön kontrolü olmadan `structural_explained`'a zorlanıyor | `audit_results.md` Tour 1 E.3 |
| 3.8 | `compute_hints` fallback | Hata durumunda run çökmüyor | Her exception'ı yutup boş hint objesi dönüyor — hint motorundaki bir hata sessizce yanlış sınıflandırmaya yol açabilir | `audit_results.md` Tour 1 E.4 |

Bunların hiçbiri "unutulmuş" değil — hepsi audit'te "still open" olarak işaretli ve bu HEAD'de tekrar doğrulandı (kod hâlâ aynı satırlarda). Ama hiçbiri `risks.md`'de R-numarası almamış, yani tek bakışta görünmüyorlar.

---

## 4. Doküman hijyeni sorunları — bu tarama sırasında bulundu

Kullanıcının "dağınık dokümanları toplayacağız" hedefiyle doğrudan ilgili. Bunlar kod boşluğu değil, **doküman kodu yanlış anlatıyor** durumları.

### 4.1 `docs/04-status/CURRENT_STATUS.md` ve `YAPILACAKLAR.md` tamamen bayat
İkisi de **24 Nisan 2026** tarihli, orijinal 6 günlük hackathon planını anlatıyor (Day 1-6, Cerebral Valley submission, DRONE Inc. demo, Railway/Vercel deploy). O plandaki her şey (multi-file consolidation, Excel export, ConsolidatorAgent) **çoktan yapıldı** — `backend/agents/consolidator.py` var, export endpoint'i var ve test ediliyor. Ürün o tarihten beri tamamen başka bir evreye geçti (Kova reconciliation stack, Item 1/4/5, Redhawk/Riverbend demo verisi, close-flow-contract). Bu iki dosya bugün okunursa yanlış zihniyet verir — "deploy edilmemiş, demo hazır değil" gibi maddeler hâlâ orada dururken ürün aylardır canlı test ediliyor.
**Öneri:** `docs/archive/`'e taşı, yerine güncel bir `CURRENT_STATUS.md` yaz (ya da bu dokümanı o amaçla güncelle).

### 4.2 İki ayrı "sprint" klasörü
`docs/03-sprint/` (hackathon günlük planları + `discovery-layer-plan.md`) ve `docs/sprint/` (post-hackathon triage + pre-analysis + test-plan) — isim çakışması kafa karıştırıcı. `docs/README.md` ikisini de listeliyor ama aralarındaki ilişkiyi açıklamıyor (biri bitmiş dönem, diğeri aktif). Ayrıca `docs/03-sprint/discovery-layer-plan.md`'nin migrasyon numaralandırması (`0009` bahsi) `agentic-memory-roadmap.md`'nin önerdiği `0009_add_report_type_and_quarterly.sql` ile aynı numarayı hedefliyor olabilir — gerçek sıradaki migrasyon dosyası hangisiyse, diğeri numarasını kaydırmalı. Şu an gerçek sıradaki en yüksek migrasyon `0010` (`supabase/migrations/`), yani her iki plan da numarasını `0011` olarak güncellemeli.

### 4.3 Pre-analysis dosyaları tutarsız "tamamlandı" işaretlemesi
`docs/sprint/pre-analysis-is-material.md` ve `pre-analysis-orphan-policy.md` başlıklarında **"SONUÇ: implementation tamamlandı"** notu var. `pre-analysis-deposit-vs-fee.md`, `pre-analysis-annual-prepayment.md`, `pre-analysis-renewal-vs-timing.md`, `pre-analysis-coverage-ui.md` dosyalarında bu not **yok** — hâlâ "Planning only. No implementation until this document is approved" diyorlar. Ama `docs/audit_results.md` (b) tablosu bunların **hepsinin** `main`'de canlı ve test edilmiş olduğunu doğruluyor (deposit/fee, cutoff allowlist, annual prepayment hepsi "COMPLETE — verified merged"). Yani dört dosya, tamamlanmış işi hâlâ "onay bekliyor" gibi gösteriyor.
**Öneri:** Dört dosyaya da is-material/orphan-policy'deki gibi bir "SONUÇ" bandı eklenmeli.

### 4.4 `docs/05-guides/onboarding-revision.md` da bayat
Başlıkta **"Status: Planning only — no code has been written"** yazıyor. Ama `onboarding_done` metadata deseni (`frontend/src/components/CompanySetupForm.tsx:65`, `frontend/src/pages/LoginPage.tsx:35`, `backend/api/routes.py:1277` yorumu) tam olarak dokümanın tarif ettiği şekilde kodda mevcut ve çalışıyor. Plan uygulanmış, başlık güncellenmemiş.

### 4.5 `docs/audit_results.md` kendi içinde iki katman — okuyan kişi hangi kısmın güncel olduğunu ilk bakışta ayırt edemeyebilir
Dosyanın kendisi bunu en üstte açıkça söylüyor ("Tours 1-3 tarihsel, düzeltilmiyor") ve bir "Stale in the historical record" tablosu tutuyor — bu iyi bir örnek, ama dosya 944 satır ve "Current Status" bölümü de artık **bu depodaki en güncel commitlere göre bir miktar bayat**: Item 1 ve Item 4 o zaman "spec only" / "not started" idi, şimdi ikisi de canlı doğrulanmış durumda (bu oturumun önceki turunda teyit edildi: Riverbend/Redhawk live run'ları). Yani bu dosyanın "Current Status" bölümü bile artık bir "Tour 4" güncellemesi istiyor.

### 4.6 `scope.md` hâlâ DRONE Inc. odaklı, ürün artık Redhawk/Riverbend/Sentinel/vb. çok-sektörlü demo setine geçti
`docs/02-planning/scope.md` "Demo Scenario" bölümü sadece DRONE'u anlatıyor; `CLAUDE.md`'deki güncel sekiz şirketlik demo seti (`clearview, corebuilt, harvest, helix, redhawk, riverbend, sentinel, vandelay`) hiç geçmiyor. Ürün artık field-service/close-flow pivotunda; `scope.md` hâlâ orijinal hackathon MVP tanımını taşıyor.

---

## 5. Önerilen sıradaki adımlar

Öncelik sırasına göre, "ne yapılmalı" değil "ne kilitli, ne değil" ayrımını netleştirmek için:

1. **`exception_three_way_matches` düzeltmesini push'la.** Zaten local'de çözülmüş — GitHub'a gitmediği sürece bu repo'da yok sayılır. En düşük efor, en yüksek risk kapatma.
2. **Doküman hijyenini önce yap, sonra konsolide et.** §4'teki altı madde düzeltilmeden (özellikle CURRENT_STATUS/YAPILACAKLAR arşivleme + pre-analysis "SONUÇ" bantları) konsolidasyon yanlış girdilerle başlar — bayat dosyalar "aktif" dosyalarla aynı ağırlıkta okunur.
3. **Close-flow Dil 2 şimdilik açık (§1.1).** Dil 1 (iskelet) kodlandı. İsimli beş kontrol + file-total→GL yeni kilit olmadan başlamaz. Dil 3 (`closed`) ayrı.
4. **`ENFORCE_NARRATIVE_CONSISTENCY` flip kararı.** Bir ölçüm turu geçti, 0 ihlal ölçüldü — flip etmenin maliyeti düşük görünüyor, karar sahibi belirlenmeli.
5. **§3'teki sekiz "yarım kalan" maddeyi `risks.md`'ye R-numarasıyla işle.** Şu an hiçbiri oradan görünmüyor; audit dosyasına gömülü kalmışlar.
