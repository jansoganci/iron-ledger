# Kalan işler

*16 Eylül 2026. Kaynak: `main` kodu + kilitli ürün kararları. Eski durum listeleri arşivde.*

Tek canlı backlog burasıdır. Bitmiş planları buraya geri kopyalama. Yeni iş ancak kilit + onay sonrası.

**Sıra (değişmez):** kalan ürün işi → canlı Supabase SQL en son (uygulayan insan; `supabase db push` yok) → GitHub / Cloudflare en son.

---

## Şimdi açık — ürün

### Close checklist Dil 2 — şimdilik açık

İsimli beş kontrol (install / fuel dahil), yeni `SourceFileType` iğneleri, dosya-toplamı → GL eşleme **başlamadı ve iptal değil**.

Dil 1 (Payroll / Vendors / Contracts / Other olarak mevcut kartları gruplamak) ayrı ailede kodlandı; bu `main` ağacında henüz yok. Dil 2, Dil 1’in üstüne gelir.

Neden açık: Redhawk’ta üç destek dosyası var; install/fuel fixture yok. Dosyası olmayan kontrolü “passed” saymak yalan olur. Yanlış GL hedefi sahte temiz veya sahte açık üretir.

Yeniden açmak: gerçek demo dosyası + file-total kilidi, sonra etiket. `closed` yok.

Kayıt: `docs/02-planning/close-flow-contract.md`, `docs/sprint/field-service-close-triage.md`.

### Close checklist Dil 3 — dönem kilidi

`closed` / sign-off / `RunStateMachine` + migrasyon. Dil 2’den ayrı. SQL’siz başlamaz.

### Aynı dönemi yeniden yükleme / takılı run

Ayrı aile. `report_failed` sonrası taze run vs sessiz replace. Checklist ekranı değil. Kilit yok; uydurma.

---

## Başka ailede kodlandı — `main`’de yok, yeniden yazma

Bunları sıfırdan açma. `main`’e alma sırası: SQL ve deploy’dan **önce değil, onlarla birlikte en sonda**.

| Konu | Bu `main` ağacında görünen |
|---|---|
| Kalıcı kaynak eşlemeleri | Yok |
| Uydurma classification token (`exception_three_way_matches`) | Hâlâ şema dışı token run’ı öldürebilir |
| Guardrail Stage 1 enforce + quarterly/Opus `strict=True` | `ENFORCE_NARRATIVE_CONSISTENCY = False`; `strict=True` yalnız aylık interpreter |
| Close checklist Dil 1 | `tie_out_summary` yok |

---

## Yarım — kodda var, kenarı açık

Kod 16 Eylül 2026 `main`’inde doğrulandı. Claude matematik yapmaz; bunları “rapor düzeltmesi” sanma.

| Konu | Ne var | Ne eksik |
|---|---|---|
| Migrasyon `0010` | `monthly_revenue_band` kolonu `IF NOT EXISTS` | `ADD CONSTRAINT` ikinci çalışmada kırılır |
| `500k_plus` bandı | Dört bant var | Üst sınır yok; $500k ile $5M aynı kapı |
| Flux yüzde kapıları | Dolar kapıları banda göre | `_TIER1_PCT` / `_TIER2_PCT` sabit |
| Processor fee bandı | `_is_processor_fee_gap` %3–8 | Dosya / hesap / yön yok; herhangi iki taraflı fark `structural_explained` olabilir |
| `compute_hints` hata yutma | Run düşmez | Her exception boş hint — yanlış sınıf riski |
| Storage TTL | Complete sonrası cleanup var | `guardrail_failed` dosyaları süpürülmüyor (production öncesi) |

**Yapıldı, listeye alma:** quarterly kalıcı rapor (`0009`, `mark_quarterly_stale`); Redhawk seed `under_100k`; coverage kartları; `_is_material` AND-gate; roster tarihlerini cutoff’tan çıkarma; onboarding `onboarding_done`.

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
