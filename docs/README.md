# Month Proof — doküman haritası

*1 Ekim 2026. Eski Nisan listeleri ve bitmiş planlar `archive/` altında.*

## Önce burası

1. **Kalan iş** — [`04-status/REMAINING_WORK.md`](04-status/REMAINING_WORK.md) (tek canlı backlog)
2. **Nasıl çalışır (kod)** — kök `CLAUDE.md` / `AGENTS.md`, sonra `01-architecture/`
3. **Kilit sözleşme** — [`02-planning/close-flow-contract.md`](02-planning/close-flow-contract.md) (Dil 1, 2 ve 3 yapıldı)

## Canlı klasörler

| Klasör | Ne için |
|---|---|
| `01-architecture/` | `db-schema.md` ve `api.md` güncel (migrasyon `0012`, dönem kilidi uçları). `agent-flow.md`, `tech-stack.md`, `design.md` Nisan tarihli; üstlerinde kısa "güncel durum" notu var. Şüphede kod. |
| `02-planning/` | `close-flow-contract.md` (kilit sözleşme, Dil 3 kaydı en altta). Hafıza yol haritası arşivde: [`archive/planning/agentic-memory-roadmap.md`](archive/planning/agentic-memory-roadmap.md). |
| `04-status/` | Yalnız `REMAINING_WORK.md`. |
| `05-guides/` | `runbook.md` — çalıştırma / deploy notları. |
| `06-reports/` | `close-process-by-sector.md` — sektör araştırması. |
| `sprint/` | `pre-analysis-close-checklist.md` (Dil 2 + Dil 3 kararı ve kaydı), `kova2-implementation-plan.md` (Item 2 / 3 / 6 spec; backlog buna bakıyor). Close triage araştırması arşivde: [`archive/sprint-complete/field-service-close-triage.md`](archive/sprint-complete/field-service-close-triage.md). |
| `qa/` | Güncel kabul kanıtı: `slice2-acceptance-2026-10-01-payroll-retest/`. |
| `demo_data/` | Redhawk, Riverbend ve diğer fixture'lar. |
| `archive/` | Bitmiş, bayat veya yalan söyleyen dokümanlar. Silinmedi. |

## Arşiv özeti

- Hackathon Nisan durum/TODO: `archive/hackathon-april-2026/`
- Hackathon günlük sprint + risks: `archive/03-sprint/`
- Eski auditler: `archive/audits/`
- Tamamlanmış pre-analysis (guardrail kilidi ve ikinci kapı, geçersiz token, aynı dönemi yeniden üretme, kaynak eşlemeleri dahil): `archive/sprint-complete/`
- Eylül canlı kabul yürüyüşleri ve ilk başarısız Ekim turu: `archive/qa/`
- Strateji / Upwork taslakları: `archive/strategy/`

## Bakım

- Kalan iş yalnızca `REMAINING_WORK.md` içinde güncellenir.
- Bitmiş plan `archive/` altına `git mv` ile gider; silinmez.
- `01-architecture/` kodla çelişirse kod doğrudur; mimari dosyayı sonra düzelt.
- Arşivdeki dosyalar eski yollara (`docs/sprint/...`, `docs/qa/...`) atıf yapabilir; güncellenmez.
