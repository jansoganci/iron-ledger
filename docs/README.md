# Month Proof — doküman haritası

*16 Eylül 2026. Eski Nisan listeleri arşivde.*

## Önce burası

1. **Kalan iş** — [`04-status/REMAINING_WORK.md`](04-status/REMAINING_WORK.md)
2. **Nasıl çalışır (kod)** — `01-architecture/` ve kök `AGENTS.md` / `CLAUDE.md`
3. **Kilit sözleşme** — [`02-planning/close-flow-contract.md`](02-planning/close-flow-contract.md) (Dil 2 şimdilik açık)

## Canlı klasörler

| Klasör | Ne için |
|---|---|
| `01-architecture/` | Ajan akışı, API, şema, tasarım, stack. Şüphede kod. |
| `02-planning/` | `close-flow-contract.md`, `agentic-memory-roadmap.md` (Phase 1–3 kodda; dosya tarihsel). |
| `04-status/` | Yalnız `REMAINING_WORK.md`. |
| `05-guides/` | `runbook.md` — çalıştırma / deploy notları. |
| `06-reports/` | `close-process-by-sector.md` — sektör araştırması. |
| `sprint/` | Hâlâ referans: close triage, Kova 2 item planı, guardrail kilidi. Bitmiş pre-analysis arşivde. |
| `demo_data/` | Redhawk, Riverbend ve diğer fixture’lar. |
| `archive/` | Bitmiş, bayat veya yalan söyleyen dokümanlar. Silinmedi. |

## Arşiv özeti

- Hackathon Nisan durum/TODO: `archive/hackathon-april-2026/`
- Hackathon günlük sprint + risks: `archive/03-sprint/`
- Eski auditler: `archive/audits/`
- Tamamlanmış pre-analysis: `archive/sprint-complete/`
- Strateji / Upwork taslakları: `archive/strategy/`

## Bakım

- Kalan iş yalnızca `REMAINING_WORK.md` içinde güncellenir.
- Bitmiş plan `archive/` altına `git mv` ile gider; silinmez.
- `01-architecture/` kodla çelişirse kod doğrudur; mimari dosyayı sonra düzelt.
