# Riverbend HVAC LLC — Item 1 three-way cash demo

A small HVAC shop that takes cards through Stripe inside its field-service
app. Period **2026-03-01**. Upload all three files together.

This set exists because `tests/tools/fixtures/kova_cash_*.csv` cannot survive
a real `POST /upload`: those CSVs have no `account` column, so pandera fails
with "We couldn't read the 'unknown column' column." These workbooks carry
`Account` on every file so Discovery can map the Golden Schema, while the
sidecar columns (`Payout ID`, `Gross`, `Bank Ref`, `Memo`, …) still feed the
three-way matcher.

Company UF account name (exact): **Undeposited Funds**.

## Files

| File | Detected type | Role |
|---|---|---|
| `riverbend_gl_mar_2026.xlsx` | `general_ledger` | P&L totals plus UF / AR clearing detail |
| `riverbend_stripe_payouts_mar_2026.xlsx` | `processor_settlement` | FSM / Stripe payout export |
| `riverbend_bank_statement_mar_2026.xlsx` | `bank_statement` | Checking deposit lines |

## Expected nested matches

Six cards under Undeposited Funds. The clean tie-out produces **no** card.

| Payout / bank ref | What happened | Class | Card? |
|---|---|---|---|
| `po_1Qx8Km2eZvRB` | Lakeshore Orthodontics rooftop repair. Gross 1,847.50, Stripe kept 83.14 (4.5%), bank received 1,764.36. | `structural_explained` | yes |
| `po_1Qy2Nt4eZvRB` | Harborview Senior Living chiller PM collected 31 Mar, landed 2 Apr. | `timing_cutoff` | yes |
| `po_1Qz9Pw7eZvRB` | Maple & Main Cafe walk-in cooler. In Stripe and the bank; bookkeeper never posted the JE. | `missing_je` | yes |
| `ACH-44192` | Westfield Auto Group wired 918.40 for an old invoice. Not in Stripe, not in the GL. | `missing_je` | yes |
| `po_1Ra3Ls1eZvRB` | Pinecrest Dental mini-split. Same dollars everywhere, but the GL put it on Accounts Receivable. | `categorical_misclassification` | yes |
| `po_1Rb7Vc9eZvRB` | Brookfield Montessori boiler service. Check in, check out, UF, zero fee. | — | **no** |
| two blank 186.40 rows on 2026-03-25 | Two Eastgate Townhomes diagnostic calls, same fee, export dropped the batch ids. | `stale_reference` (`ambiguous`, `candidate_count` = 2) | yes |

Account-level class on the Undeposited Funds card is **`missing_je`** (the
most action-requiring nested class).
