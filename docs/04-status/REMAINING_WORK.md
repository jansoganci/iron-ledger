# Kalan işler

*17 Eylül 2026 ürün kararı. Kaynak: güncel `main` kodu + kilitli ürün kararları.
Kabul: 1 Ekim 2026 canlı Redhawk Mart yürüyüşü — üç kontrol geçti.
Kâr tablosu tutarı, GL varsa GL'dir; destek dosyası üstüne eklenmez.*

Tek canlı backlog burasıdır. Bitmiş planları buraya geri kopyalama. Yeni iş ancak kilit + onay sonrası.

**Sıra (değişmez):** kalan ürün işi → canlı Supabase SQL en son (uygulayan insan; `supabase db push` yok) → Cloudflare en son.

---

## Şimdi açık — ürün

### Close checklist Dil 2 — ana yol geçti (2026-10-01)

Redhawk Mart 2026 canlı yürüyüş: bordro Tied out (6.200 / 1.400 / 5.500),
tedarikçi Tied out, sözleşme 3.825 vs 3.540, fark 285. Kanıt:
`docs/qa/slice2-acceptance-2026-10-01-payroll-retest/`.

Kâr tablosu artık aynı hesabı iki kez toplamaz. GL satırı varsa tutar GL'dir.
Destek dosyası kırılımda ve kontrol kartında kalır. Kayıtlı eski rapor eski
toplamı gösterir; yeni bir analiz güncel tutarı yazar.

Açık kenar: eksik dosya senaryoları, stale-export, Excel'in görsel kontrolü.
Install/fuel ayrı durur. `0011` demo projede uygulandı. Dönem kilidi (`closed`) aşağıda: yapıldı.

Güncel karar, UX ve uygulama kaydı:
[Close checklist pre-analysis §11](../sprint/pre-analysis-close-checklist.md#11-17-eylül-2026--dil-2-ürün-kararı-ve-rapor-ux-tasarımı).

### Close checklist Dil 3 — dönem kilidi: yapıldı (`96cf24e`, 1 Ekim 2026)

Migrasyon `0012_add_period_closes.sql` demo projede uygulandı. Canlıda denendi: kapat,
yeniden aç (log: closed → reopened), düzeltilmiş raporla tekrar kapat.

- `RunStatus` değişmedi; kapanış bir run durumu değil, `period_closes` satırı
  (aktif kilit: `reopened_at IS NULL`, `(şirket, ay)` başına tek). Yeniden açma
  satırı silmez, `reopened_*` damgalar; `period_close_log` yalnız ekleme.
- `POST /periods/{ay}/close` ve `/reopen` ayrı açık onay ister (`{"confirm": true}`);
  kapatmak için bitmiş aylık rapor şart. `GET /periods/{ay}/close` durum + log.
- Kapalı ayda `/upload`, `/runs/{id}/confirm` (Replace) ve `/runs/{id}/retry` 409
  (`PERIOD_CLOSED`); uçuştaki run ve Opus yükseltmesi de dokunmadan durur.
- Çeyrek rapor kilidin parçası değil. Banka, kurulum/yakıt, yaşlandırma, e-posta yok.

**Kalan canlı iş:** kapalı ayda sunucunun 409 vermesini canlıda denemek (yalnız testlerde var).
Açık kenar: Opus yükseltmesi ve karşılaştırma kontrolü iki ayrı okuma; kapatma tam o
aralıkta olursa küçük bir yarış penceresi kalır.

### Anlatı–kart tutarlılığı: yapıldı (1 Ekim 2026)

Destek dosyası olmayan (coverage / `is_gl_only`) bir GL hesabına "missing journal entry" veya
yüksek/orta önem diyen anlatı bir kez yeniden denenir; ikinci denemede rapor yazılmaz
(`NarrativeContradictionError`, `narrative_check.py`). Opus yükseltmesi çelişkiliyse yayınlanmaz.
Sınır: kural kelime tabanlıdır; hesap adı anmayan genel cümleler yakalanmaz.

---

## Yapıldı — listeye alma

- Aynı dönemi yeniden üretme (açık onay, sessiz UPSERT yok)
- Kalıcı kaynak eşlemeleri (`0011` demo projede uygulandı)
- Uydurma classification token düşer, run ölmez
- Guardrail Stage 1 enforce + quarterly/Opus `strict=True`
- Close checklist Dil 1 (`tie_out_summary`)
- Quarterly kalıcı rapor (`0009`, `mark_quarterly_stale`)
- Redhawk seed `under_100k`; coverage kartları; `_is_material` AND-gate; roster tarihlerini cutoff’tan çıkarma; onboarding `onboarding_done`

---

## Yarım — kodda var, kenarı açık

Claude matematik yapmaz; bunları “rapor düzeltmesi” sanma.

| Konu | Ne var | Ne eksik |
|---|---|---|
| Migrasyon `0010` | `monthly_revenue_band` kolonu `IF NOT EXISTS` | `ADD CONSTRAINT` ikinci çalışmada kırılır |
| `500k_plus` bandı | Dört bant var | Üst sınır yok; $500k ile $5M aynı kapı |
| Flux yüzde kapıları | Dolar kapıları banda göre | `_TIER1_PCT` / `_TIER2_PCT` sabit |
| Processor fee bandı | `_is_processor_fee_gap` %3–8 | Dosya / hesap / yön yok; herhangi iki taraflı fark `structural_explained` olabilir |
| `compute_hints` hata yutma | Run düşmez | Her exception boş hint — yanlış sınıf riski |
| Storage TTL | Complete sonrası cleanup var | `guardrail_failed` dosyaları süpürülmüyor (production öncesi) |

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

---

## Bu dosyayı nasıl kullan

1. Yeni iş buraya bir satır olarak girer, ayrı bir “master brief” açılmaz.
2. Bitince satır düşer veya “yapıldı” olur; plan dosyası arşive gider.
3. Çelişince kod kazanır.
