# Close Checklist Slice 2 — Live acceptance, 2026-10-01

**Verdict: NOT READY**
**Blocker:** Payroll rol satırları ücret hesaplarına (Technician Wages / Admin Wages / Owner Salary) eşlenmiyor; bordro "Not compared" çıkıyor ve yanlışlıkla "Missing JE" uyarısı üretiyor (L3, L19).

## Environment
- Frontend `localhost:5173`, backend `localhost:8000` (`npm run dev`). Tarayıcı: Chrome (Claude in Chrome). Workbook: openpyxl ile yapısal inceleme.
- Supabase projesi `lxvxqpgixwwpeileggds` (backend ve frontend aynı), Redhawk demo şirketi, yeni şirket yok. Kullanıcı `demo@redhawkdemo.com`.
- LLM canlı: Haiku (keşif ×4 + hesap eşleme) ve Opus (anlatı + arka plan yükseltmesi) çağrıları; tur başına yaklaşık 9–10 çağrı, toplam 3 tam tur denendi (biri migration eksikliğinden, biri rapor-yazma hatasından yarıda kaldı).
- Çalışma ağacı: commit edilmemiş Dil 2 değişiklikleri üzerinde test edildi; commit/push/reset yapılmadı; demo dosyaları değişmedi.

## Bulunan ve düzeltilen blokajlar
1. **Eksik tablo.** `source_account_mappings` yoktu (PGRST205); kullanıcı migration 0011'i ekledi, mapping adımı çalıştı. 20 Eylül "Something went wrong" hatasının nedeni büyük olasılıkla buydu.
2. **Rapor değiştirilemiyordu.** Aynı dönem raporu yeniden üretilirken `reports` silinemiyordu (`runs_report_id_fkey`). Düzeltme: `backend/adapters/supabase_repos.py` `delete_monthly` önce eski rapora bağlı `runs.report_id` değerlerini boşaltıyor; test `tests/adapters/test_delete_monthly.py`. Tam test seti: 614 geçti, 5 atlandı.
3. **Tarayıcıdaki "404 (Not Found)".** Yürüyüş boyunca uygulamanın hiçbir API isteği 404 vermedi (hepsi 200); backend'deki tek 404, eksik tabloya giden Supabase isteğiydi. Tarayıcıdaki kaynak 404'ün (büyük olasılıkla favicon veya benzeri statik dosya) hangi URL olduğu yakalanamadı; akışı etkilemedi.

## Scenario results
| ID | Result | Evidence / notes | File |
|---|---|---|---|
| L1 | PASS | Açık oturumla Upload, Report ve Reports ekranlarına ulaşıldı; API çağrıları 200. | screenshots/04_mapping_review.jpg |
| L2 | PASS | İkinci denemede (migration 0011 sonrası) 4 dosya parse oldu; mapping ekranı hedefi açıkça gösterdi (Contracts → Service Revenue $3,825.00; 5 tedarikçi adı). Kaydedilen eşlemeler tekrar yüklemede "Saved" geldi. Ham PII yok (sanitizer 0 sütun düşürdü, log temiz). Mapping canlı Haiku. | screenshots/04_mapping_review.jpg |
| L3 | FAIL | Payroll "Not compared": rol satırları (Install Technician 2.100, Lead Install 2.400, Service Technician 1.700, Office Admin 1.400, Owner/Operations 5.500) GL hesabı gibi ele alındı. GL'de Technician Wages 6.200 (=2.100+2.400+1.700), Admin Wages 1.400, Owner Salary 5.500 var; rol→ücret hesabı eşlemesi mapping ekranında hiç sunulmadı. Beklenen: Tied out. | screenshots/05_report_close_controls.jpg; monthproof_2026-03-01_close_package.xlsx |
| L4 | PASS | Contracts: Service Revenue, kaynak $3,825.00, GL $3,540.00, fark $285.00, Has exceptions; roster 85 aktif / 82 faturalanan. | screenshots/05_report_close_controls.jpg |
| L5 | BLOCKED | Ek fixture (kaynak eksik yükleme) çalıştırılmadı. | — |
| L6 | BLOCKED | Ek fixture çalıştırılmadı. | — |
| L7 | BLOCKED | Ek fixture çalıştırılmadı. | — |
| L8 | BLOCKED | Ek fixture çalıştırılmadı. | — |
| L9 | BLOCKED | Ek fixture çalıştırılmadı (Redhawk contracts dosyası account-less roster; mapping ekranı file-total hedefini onaya sundu, bu L9'a kısmi destek ama senaryo ayrı fixture ister). | screenshots/04_mapping_review.jpg |
| L10 | BLOCKED | Ek fixture çalıştırılmadı. | — |
| L11 | BLOCKED | Ek fixture çalıştırılmadı. | — |
| L12 | BLOCKED | Geçersiz mapping onayı API'si JWT gerektirir; tarayıcı oturum anahtarı çıkarılmadı. | — |
| L13 | PASS | Rapordaki "Download Excel" butonu GET /report/{company}/2026-03-01/export.xlsx (200) çağırdı; dosya adı monthproof_2026-03-01_close_package.xlsx; openpyxl ile açıldı (3 sayfa). | monthproof_2026-03-01_close_package.xlsx |
| L14 | PASS | Reconciliations sayfasındaki kontrol özeti, dosya adları, hedefler, tutarlar, nedenler ve sonraki adımlar web raporuyla birebir aynı (2 compared · 1 exceptions · 1 not evaluated · 10 GL hesabı). Payroll kusuru Excel'de de aynen taşınıyor. | monthproof_2026-03-01_close_package.xlsx |
| L15 | BLOCKED | Excel/Numbers'ta görsel kontrol yapılamadı (yerel uygulama ekranını yakalayan araç yok). Yalnız yapısal kontrol: sütun genişlikleri tanımlı. | — |
| L16 | BLOCKED | Stale-export senaryosu ikinci bir dönem verisi değişikliği ve yetkili API çağrısı gerektirir; yapılmadı. | — |
| L17 | PASS | Güncel rapor aynı oturumda sorunsuz export edildi, içerik web raporuyla tutarlı. | monthproof_2026-03-01_close_package.xlsx |
| L18 | PASS | "Bank and card reconciliation is done outside Month Proof", "Installation and fuel were not evaluated in this delivery", "does not mean the month is closed" ifadeleri var; kapandı iddiası yok. | screenshots/05_report_close_controls.jpg |
| L19 | FAIL | Kontroller, açık işler, eksik kanıt, kaynak ve sonraki adım okunabiliyor; ama bordro için "journal entry may be missing, enter the missing JE" (HIGH/MEDIUM) yanlış yönlendiriyor: GL'de bu tutarlar Technician Wages / Admin Wages / Owner Salary altında mevcut. | screenshots/05_report_close_controls.jpg |

## Yan etkiler
- Mart 2026 raporu son (üçüncü) turda başarıyla yeniden üretildi; önceki iki tur rapor yazmadan durdu. Başarısız ilk run'lar (`a33ee010…`, `c5df53fb…`) terminal durumda kaldı.
- Beş tedarikçi adı eşlemesi `source_account_mappings` tablosuna kaydedildi (demo şirket).
- Kod değişikliği: yukarıdaki `delete_monthly` düzeltmesi ve testi.
