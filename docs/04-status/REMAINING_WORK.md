# Kalan işler

*17 Eylül 2026. Kaynak: güncel `main` kodu + kilitli ürün kararları.*

Tek canlı backlog burasıdır. Bitmiş planları buraya geri kopyalama. Yeni iş ancak kilit + onay sonrası.

**Sıra (değişmez):** kalan ürün işi → canlı Supabase SQL en son (uygulayan insan; `supabase db push` yok) → Cloudflare en son.

---

## Şimdi açık — ürün

### Close checklist Dil 2 — dört kabul düzeltmesi uygulandı (2026-09-17)

Bordro, tedarikçi ve sözleşme kontrolleri, run-scoped file-total eşleme ve
rapor/Excel kanıtı working tree'de. §11.12'de onaylanan dört düzeltme uygulandı:
kontrol başına tek destek dosyası; doğrulanmış roster için file-total; sunucuda
eksiksiz mapping onayı; Excel'de eksiklik nedeni ve sonraki adım. 588 yerel
backend testi, frontend typecheck ve build geçti. Commit veya canlıya çıkış yok.

Açık kalan: install/fuel named kontrolleri; bordro Bonus/Benefits dağıtımı;
hedef kullanıcıyla 60 saniyelik okuma yürüyüşü ve Excel görsel kontrolü.
Genel repo lint sorunları ayrıca sürüyor; `closed` yok.

Güncel karar, UX ve uygulama kaydı:
[Close checklist pre-analysis §11](../sprint/pre-analysis-close-checklist.md#11-17-eylül-2026--dil-2-ürün-kararı-ve-rapor-ux-tasarımı).

### Close checklist Dil 3 — dönem kilidi

`closed` / sign-off / `RunStateMachine` + migrasyon. Dil 2’den ayrı. SQL’siz başlamaz.

---

## Yapıldı — listeye alma

- Aynı dönemi yeniden üretme (açık onay, sessiz UPSERT yok)
- Kalıcı kaynak eşlemeleri (`0011_add_source_account_mappings.sql` — dosya repoda; canlı DB’ye insan uygular)
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
| Migrasyon `0011` | Kaynak eşleme tablosu dosyada | Canlı Supabase’e henüz uygulanmadı |
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
