# Pre-analysis — Close checklist (raporu kapanış listesine çevir)

Status: Slice 1 implemented. Slice 2 **first delivery implemented**
(2026-09-17) for payroll, vendor, and contract controls. Installation/fuel
remain outside this delivery. Slice 3 (`closed` / period lock) is still later.
Update 2026-09-17: product direction and report UX recorded in
[§11](#11-17-eylül-2026--dil-2-ürün-kararı-ve-rapor-ux-tasarımı); implementation
result is in [§11.11](#1111-17-eylül-2026--ilk-teslim-uygulandı).
Three supported controls first; install/fuel remain outside the first delivery.
Earlier sections retain historical context. §11 is the design; §11.11 is what
the code actually does.
Date: 2026-09-16.
Parent: `docs/02-planning/close-flow-contract.md`;
`docs/06-reports/close-process-by-sector.md` §5;
`docs/06-reports/pending-decisions-audit.md` §1.1;
`docs/sprint/field-service-close-triage.md` Bucket 1 item 6–7.
Checkout: `main`.

Process: (1) this pre-analysis → approval, (2) implementation as **two
slices**, (3) verification vs this file. Do not start coding until §10 is
locked.

---

## One-sentence diagnosis

The engine already compares department files to the GL. The report still
*reads* like a story plus a pile of cards, so the office manager cannot
answer “how many controls are left, what do I do next.” First action is
**regroup the existing payload**. It is not a new agent, not `closed`,
and not bank matching.

---

## Scope lock

| In this family | Out |
|---|---|
| Reorder the report: tie-out summary → exceptions by file type → flux/narrative → bank attestation line | `closed` / sign-off / period lock (contract slice 3) |
| Group recon by supporting-file type, not by dollar-severity pile | Day 0 expected-file manifest |
| One bank sentence + optional session checkbox (display-only) | Bank CSV / line matching |
| Soften “Verified” so it does not mean “close is done” | Open-item aging from last month |
| Excel: one attestation sentence on the existing recon sheet **or** a thin checklist sheet of the same groups | New agent, new table, 7th class, ERP |

Two slices. Not one PR that also invents five named controls, install/fuel
file types, and a file-total→GL map.

---

## 1. What this item actually is

A US field-service close is a **control list**, not a narrative:

1. Cash (bank = GL cash) — Month Proof does **not** do this.
2. Five subledger vs GL tie-outs — the engine already computes these.
3. Accruals / open items that must reverse.
4. Flux (variance story) — already written, currently shown **first**.
5. Package + lock the period.

Today the product does step 4 early and dumps step 2 as “Reconciliation
findings” sorted by `|delta|`. Coverage cards (GL line, no supporting
file) already sit in a grey “Not compared” block. That is progress. It is
still a **finding pile**, not “3 of 4 controls clean.”

Contract one-liner, still correct:

> Raporu close checklist’e çevir; motoru değiştirme.

---

## 2. What the code does today (evidence)

| Surface | Today |
|---|---|
| Report order | KPI strip → **narrative** → recon → Account Variance below (`ReportPage.tsx`, `ReportSummary.tsx`) |
| Recon grouping | Exception cards by `$5k / $500` severity; coverage separately (`ReconciliationPanel.tsx`) |
| Run machine | Terminal = `complete` / `*_failed`. **No `closed`.** |
| Excel | Three sheets: P&L, Reconciliations, Source Breakdown. No checklist sheet. |
| File types | `payroll`, `contracts`, `supplier_invoices`, `general_ledger`, plus Item 1 `bank_statement` / `processor_settlement`. **No install. No fuel.** |
| Item shape | `sources[].source_file` exists; frontend grouping does not use it |
| Materiality | `$100` AND `5%`, or `$500` hard — **already in** `consolidator.py`. Do not reopen. |
| Orphans | `card_kind=coverage` for GL-only — **already in**. Do not reopen. |
| Badge | “Verified · Guardrail Passed” on a `complete` report |

Sentinel five-file pack is **gone**. On disk:

- `docs/demo_data/sentinel/` — GL March + GL February only
- Living analog: **Redhawk** (GL + payroll + vendor + contracts)
- Riverbend is cash three-way, not the five P&L tie-outs

The August paper walk cannot be re-run as written until those four
department files exist again. That restore is **not** required to ship
slice 1 if Redhawk is the acceptance fixture.

---

## 3. Why this is two debts, not one button

### Debt A — the page lies about what is done

The user sees a story, then a severity grid, then a green Verified chip.
Nothing says “payroll tied out, contracts did not, bank was outside the
tool.” Grouping by `$5,000` answers the wrong question.

This debt is **frontend + copy**. Payload already has `sources`,
`card_kind`, `classification`.

### Debt B — “5/N” is not a real number yet

The contract’s five named controls are:

1. Payroll vs GL wages
2. Supplier vs GL COGS
3. Contracts × fee vs GL monitoring revenue
4. Install jobs vs GL install revenue
5. Fuel card vs GL vehicle

The engine emits **account cards**, not named controls. Install and fuel
are not `SourceFileType` values, so a filename like
`sentinel_installation_payments_*.xlsx` today falls through the detector
(likely `supplier_invoices` via “invoice”/nothing useful). Fuel has no
needle at all.

Real contract workbooks often have customer + fee, **not** a GL account
column. AccountMapper maps **row values** → GL account. It does not map
**this file’s total** → GL account X. The contract called that map
mandatory before first code. Putting it in the same PR as the UI regroup
hides a mapping outage inside a layout change.

### Same family, different blast radius

| | Debt A (page skeleton) | Debt B (named 5 + file-total map) |
|---|---|---|
| Touches | `ReportSummary`, `ReconciliationPanel`, maybe Excel sentence | `SourceFileType` / detector, mapping mode, possibly consolidator join |
| Failure mode | Ugly / wrong order | Wrong GL target → fake pass or fake fail |
| Demo | Redhawk 4 files | Needs install/fuel types + a file without `Account` |
| Migration | None if bank box is session-only | Maybe none; still a product contract, not a flag flip |

---

## 4. What is *not* the problem

- The six-class taxonomy. Do not add a 7th.
- Guardrail / Claude arithmetic. Numbers stay pandas.
- `_is_material` ($100 and 5%). Already shipped.
- Coverage vs `missing_je`. Already shipped.
- Duplicate-period re-run (`REPORT_FAILED` / silent replace). Separate
  family; more urgent for stuck runs, but not this screen.
- Email stub. Out.

---

## 5. Recommended slices (after approval)

### Slice 1 — regroup the report (no new engine)

1. Page order: (1) tie-out summary “N compared / M with a gap / K not
   compared”, (2) exceptions **grouped by supporting file type** derived
   from `sources[].source_file` + existing `_detect_file_type` labels,
   (3) coverage block unchanged in meaning, (4) narrative/flux, (5) one
   bank line: cash rec is outside Month Proof. Optional checkbox stored
   **only in the browser session** (no `0011`, no `closed`).
2. “Verified” copy: numbers passed the guardrail. Not “period closed.”
3. Groups we can name from types we already detect: Payroll, Vendors,
   Contracts, plus a leftover “Other supporting files” (Item 1 cash,
   unknown names). Do **not** invent Install / Fuel labels until slice 2.
4. Clean two-sided match (delta under the existing gate) already does
   not emit a card — that *is* a passed control. Count it in the summary
   from files present vs files that still have exception cards.
5. Tests: Redhawk-shaped fixture — payroll group exists; coverage stays
   out of “to review”; bank sentence renders; narrative is not above the
   summary. Intentional: a vendor gap still appears under Vendors.

Exit: an office manager can say in one glance which **file-typed**
control still has work. They do not count 16 grey cards as 16 failures.

### Slice 2 — make “5 of 5” true (pandas + types, then UI labels)

Do **not** start slice 2 by painting Install/Fuel on the page.

1. Decide the five names against **Redhawk + what we still lack**
   (install, fuel). Add detector needles only for files we will actually
   demo. Do not add truck-stock.
2. File-total → GL account map for supporting files that have no Account
   column. This is a mapping **mode**, not a new consolidator engine.
   Persistent source mappings (other branch, unmerged) are adjacent, not
   a substitute: they remember row values, not “this whole file is
   Service Revenue.”
3. Then rename the UI groups to the five controls. A passed control with
   no card still counts as passed.

Exit: “3 of 5 clean” is a pandas fact, not a CSS heading.

### Sequencing

Slice 1 then 2. Combining them hides a mapping miss inside a layout PR.
Slice 2 without 1 leaves the right math on a page that still leads with
prose.

`closed` / sign-off / lock stays **slice 3**, later, with a migration and
run-state work. Do not sneak it into 1.

---

## 6. Options considered and rejected

| Option | Why not |
|---|---|
| One PR: new `closed` status + checklist UI + five types | Contract forbade this. Period lock is a different machine. |
| Restore Sentinel four department xlsx as the first code | Useful fixture later; Redhawk already has four living files. Do not block UI on binary restore. |
| Drop coverage cards so the count looks like 4 | Already rejected in orphan policy: forgetting Rent looks like a clean close. |
| Persist bank checkbox in `0011` in slice 1 | Display-only is enough to stop lying. Persist when slice 3 locks the period. |
| Ask Claude to write “3 of 5” | Golden rule. Count in Python from cards + file types. |

---

## 7. Tests each slice must add

### Slice 1

1. Report order: summary heading before narrative in the tree.
2. Two exception cards from `*payroll*` and `*vendor*` filenames land in
   two groups, not one severity list.
3. Coverage item is not in “to review.”
4. Bank attestation sentence is in the page (and Excel if we touch the
   recon sheet).
5. Guardrail / classification tests unchanged.

### Slice 2

1. File with no Account column, mapped as a whole to one GL account,
   produces one two-sided item (not 16 coverage cards).
2. Install/fuel (or whatever names we lock) only appear if detector +
   fixture exist.
3. Invented 5th control with no file does not count as “passed.”

No live LLM. No `supabase db push`.

---

## 8. Files (implementation, not now)

### Slice 1

| File | Change |
|---|---|
| `frontend/src/components/ReportSummary.tsx` | Order; bank line; Verified copy |
| `frontend/src/components/ReconciliationPanel.tsx` | Group by file type |
| `frontend/src/pages/ReportPage.tsx` | Variance block stays **after** checklist+narrative |
| `backend/tools/excel_export.py` | Attestation sentence only if we touch the sheet |
| Tests colocated with those components / export |

### Slice 2

| File | Change |
|---|---|
| `backend/domain/contracts.py` `SourceFileType` | Only if we add install/fuel |
| `backend/agents/orchestrator.py` detector | Needles |
| Account mapping path | File-total mode |
| Same UI files | Rename groups to the five controls |

No `guardrail.py` tolerance change. No new classification.

---

## 9. Infra

Slice 1: no migration. Slice 2: no migration unless we persist a
file-total map table — prefer run-scoped mapping draft first.
Slice 3 (`closed`) is the first one that needs SQL + `RunStateMachine`.
Not this family.

---

## 10. Approval checklist

Reply with yes/no per row. Implementation of a slice starts only when that
slice is locked.

- [x] This is **two slices**, not “add closed + checklist in one job.”
- [x] Slice 1: regroup existing cards + bank sentence + Verified copy.
      No new file types. No `closed`. No SQL.
- [x] Slice 2 first delivery (2026-09-17): three named controls +
      file-total→GL map for a single-target supporting source. Install/Fuel
      still not painted. An invented 5th control with no file does not count
      as passed.
- [x] Demo fixture for slice 1 is **Redhawk**, not restoring Sentinel binaries.
- [x] Do not reopen materiality, coverage/`missing_je`, or a 7th class.
- [x] Do not ask Claude to calculate N of M.
- [x] No live SQL / deploy in these slices.

If slice 1 is “no,” say whether we skip this family and take duplicate-period
re-run instead (stuck runs vs. wrong screen).
If slice 2 is “no,” slice 1 still ships a honest page for the types we have.

---

## SONUÇ — Slice 1

Counts live in `backend/tools/tie_out_summary.py` (uploaded filenames vs
exception cards). GET `/report` adds `tie_out_summary` and `tie_out_group`.
The report page leads with that summary, then exceptions by Payroll /
Vendors / Contracts / Other, then coverage, then narrative, then a
session-only bank checkbox. “Numbers verified” is not “period closed.”
Excel recon sheet carries the same bank sentence. No `closed` state, no
SQL, no install/fuel types.

## SONUÇ — Slice 2 left open (2026-09-16)

We are **not** starting named five controls, install/fuel `SourceFileType`
needles, or a file-total→GL mapping mode. Slice 1 already gives an honest
page for the types we have (Payroll / Vendors / Contracts / Other).

Why it stays open, not “done” and not “never”:

- Redhawk has three supporting files + GL. Install and fuel fixtures are
  not in the tree. Painting those labels would lie.
- A control with no uploaded file must not count as passed.
- File-total→GL is a mapping mode. Wrong GL target is a fake pass or a
  fake fail. That lock is a separate approval.

`closed` / sign-off / period lock remains slice 3, later, with SQL.
Do not sneak it in while slice 2 is open.

To reopen slice 2: lock names against real demo files, then file-total
mode, then UI labels — in that order. Until then this family stops at
slice 1.

**Superseded 2026-09-17:** first delivery of the three named controls is
implemented. See [§11.11](#1111-17-eylül-2026--ilk-teslim-uygulandı).
Install/fuel remain out. This historical lock is kept for the audit trail.

---

## 11. 17 Eylül 2026 — Dil 2 ürün kararı ve rapor UX tasarımı

**Karar tarihi:** 17 Eylül 2026.

**Durum:** İlk teslim uygulandı (2026-09-17). Üç desteklenen kontrol
(bordro, tedarikçi, sözleşme), run-scoped file-total eşleme ve rapor/Excel
kanıtı kodda. Kurulum/yakıt hâlâ çalışan kontrol değildir. Bu kayıt SQL,
deploy veya yeni fixture üretmez.

**Kullanıcı:** Saha hizmeti ofis müdürü ve fractional controller.

**Amaç:** Kullanıcının hangi kaynağın muhasebeyle tutarlı olduğunu, hangi
konuyu incelemesi gerektiğini ve hangi alanın kontrol edilemediğini anlayıp
kanıtlarıyla birlikte bir kapanış çalışma paketi paylaşabilmesi.

### 11.1. Alınan ürün yönü kararı

İlk teslim hedefi bordro, tedarikçi ve sözleşme kontrolleridir. Öncelik bu üç
kontrolden güvenilir ve aksiyon alınabilir sonuç çıkarmaktır. Kurulum ve yakıt
kontrolleri iptal edilmez; gerçek fixture, detector ve karşılaştırma kapsamı
doğrulanana kadar çalışan kontrol olarak sunulmaz.

Raporun önceliği açık işler ve kontrol kapsamıdır; aylık performans anlatısı
bunların ardından gelir. Belirsiz kaynak → GL eşlemesi kullanıcı onayına
sunulur. Kaynak eksikliği veya onaysız eşleme başarı sayılmaz.

Bu teslim, sözleşmedeki beş kontrolün tamamının bitmesi değildir. Üç kontrolün
temiz çıkması da bütün ay sonu kapanışının tamamlandığı anlamına gelmez.
Ürün vaadi: “Yüklediğiniz kaynakların GL ile tutarlılığını kontrol edin;
açıkları ve kanıtlarıyla kapanış çalışma paketinizi hazırlayın.”

### 11.2. Kullanıcının alacağı somut sonuç

Ofis müdürü raporu açtıktan sonra 60 saniyede şu soruları cevaplayabilmelidir:

1. Hangi kontroller yapıldı, hangilerinde inceleme gerekiyor?
2. Şimdi hangi dosyayı, hesabı veya kaydı kontrol etmeliyim?
3. Hangi alan kaynak ya da eşleme eksikliği nedeniyle değerlendirilemedi?
4. Hangi sonuç hangi dosyaya ve GL hesabına dayanıyor?
5. Excel paketini paylaşırken hangi açıkları ve kapsam sınırlarını belirtmeliyim?

Controller aynı raporda kaynak tutarı, GL tutarı, fark, dönem ve eşleme
kapsamına ulaşabilmelidir. Kanıtlanmış bulgu ile olası neden birbirinden
ayrılır. Dosyanın doğrulamadığı bir eksik fatura, JE veya neden kesinmiş gibi
yazılmaz. Sonraki adım bir inceleme önerisidir; otomatik JE veya ERP işlemi değildir.

### 11.3. Rapor ekranı: bilgi sırası

Dil 1'in mevcut iskeleti korunur. Aşağıdaki sıra gelecekteki UX hedefidir;
bugünkü uygulamanın bu davranışı zaten sağladığı iddia edilmez.

```text
Şirket · Dönem · Raporun veri güncelliği
Numbers verified — dönem kapanışı veya insan onayı değildir
Mevcut finansal KPI şeridi

KONTROL ÖZETİ
Karşılaştırılan kontroller · Fark bulunanlar · Değerlendirilemeyenler
Bordro       [durum]   [kanıtı incele / eksik bilgiyi gör]
Tedarikçiler [durum]   [kanıtı incele / eksik bilgiyi gör]
Sözleşmeler  [durum]   [kanıtı incele / eksik bilgiyi gör]
Kapsam notu: Kurulum ve yakıt bu sürümde değerlendirilmedi.

İNCELEMENİZ GEREKENLER
Kontrole göre gruplu bulgular · mevcut önem sırası
Bulgu → kaynak/GL karşılaştırması → inceleme için sonraki adım

KARŞILAŞTIRILMAYAN GL HESAPLARI
Mevcut coverage kartları; eksik JE veya başarısız kontrol sayılmaz

BU AY NE DEĞİŞTİ?
Mevcut flux / anlatı; kaynakta kanıtlanmayan neden kesinleştirilmez

BANKA VE KAPSAM
Banka mutabakatı Month Proof dışında · mevcut oturumluk teyit

EXCEL PAKETİNİ İNDİR
Kontrol özeti + açıklar + kanıtlar + mevcut finansal tablolar
```

Ekrandaki açıklamalar ürün diline uyarlanır; bu taslaktaki Türkçe ifadeler
ayrıca bir yerelleştirme projesi başlatmaz. Durumlar yalnız renkle anlatılmaz;
metin, klavye erişimi, odak ve yüklenme/hata durumları korunur.

### 11.4. Kontrol durumları ve sayım sözleşmesi

| Durum | Ne zaman gösterilir? | Kullanıcının sonraki adımı |
|---|---|---|
| Tied out | Kapsam/hedef doğrulanmış; iki taraflı karşılaştırma tamamlanmış; mevcut eşiklere göre istisna yok | İsterse kanıtı incele |
| Has exceptions | Karşılaştırma yapılmış; inceleme gereken mevcut recon bulgusu var | İlgili kaydı ve kanıtı incele |
| Mapping required | Kaynak var; hedef veya tutar kapsamı henüz doğrulanmamış | Karşılaştırma taslağını onayla/düzelt |
| Source missing | Desteklenen kontrol için gereken kaynak yok | Sonraki analizde ilgili kaynağı ekle |
| Not compared | GL tarafı eksik, kaynak boş/geçersiz veya kapsamın bir bölümü karşılaştırılamıyor | Gösterilen eksikliği gider |

Bu durumlar kontrol özeti içindir; yeni recon sınıfı veya run durumu değildir.
Kurulum/yakıt ilk teslimde ayrı bir kapsam notudur; bu tabloya sahte bir
çalışan kontrol veya “dosya yükleyince çalışır” çağrısı olarak eklenmez.
Bu not Gün 0 beklenen-dosya manifesti değildir.

Bir kontrol kısmen karşılaştırıldıysa bütünü Tied out olamaz. Karşılaştırılan
hesaplardaki bulgular görünür kalır; eksik kapsam ayrıca belirtilir. Kontrolün
tamamlanmış karşılaştırma sayısına girmesi için bütün tanımlı kapsamı işlenmelidir.

Özetin birimi **kontrol**dür. Karşılaştırılanlar tamamı değerlendirilmiş
kontrolleri; fark bulunanlar bunların istisnalı alt kümesini;
değerlendirilemeyenler eksik/onaysız/kısmi kontrolleri ifade eder. Kısmi bir
kontrolde bulunan farklar ayrıca gösterilir; özet eksik kapsamı gizlemez.
Coverage hesaplarının sayısı kontrol sayısına karıştırılmaz. Bütün sayıları
Python üretir; frontend ve Claude yeni N/M hesabı yapmaz.

İlk teslimde “3/5 tamamlandı” veya kapanış yüzdesi kullanılmaz. “Karşılaştırıldı”
ile “fark bulunmadı” ayrı anlamlardır. Kart çıkmaması tek başına Tied out kanıtı
değildir. Tied out, kuruşuna eşitlik veya bütün finansal tabloların doğruluğu
iddiası değildir; mevcut materiality kuralları altındaki sonucu ifade eder.
Timing ya da açıklanmış fark da insan onayı olmadan “çözüldü” yapılmaz.

### 11.5. Karşılaştırma ve kanıt UX'i

Her kontrolün detayında dönem, kaynak dosya, tutar kolonu/kapsamı, hedef GL
hesabı veya hesapları, kaynak tutarı, GL tutarı, fark ve mevcut bulgu sınıfı
görülür. Kullanıcı bir farkın hangi karşılaştırmadan geldiğini izleyebilir.
Kişisel veriler ve ham müşteri/çalışan satırları rapor kanıtı diye açılmaz;
mevcut sanitizasyon ve erişim sınırları korunur.

Belirsiz eşlemede karşılaştırmadan önce bir taslak gösterilir: “Bu dosyanın
şu dönem ve tutar kapsamı, şu GL hesabıyla karşılaştırılacak.” Kullanıcı
onaylar veya hedefi düzeltir. Otomatik öneri, onaylanmış muhasebe kararı değildir.
Onay bekleyen analiz, tamamlanmış/verified rapor gibi gösterilmez; rapor tablosu
bu eksikliği ancak ilgili akışın gerçekten desteklediği yerde gösterir.

Account kolonunun olmaması file-total modunu otomatik seçtirmez. Bu mod yalnız
tek GL hesabına ait olduğu doğrulanan kapsam için kullanılır. Satır mapping'i
aynı tutarlara ayrıca uygulanmaz. Birden çok hesap içeren bordro veya vendor
dosyası sırf Account kolonu yok diye tek hesaba toplanmaz.

İlk yaklaşım kullanıcı onaylı run-scoped taslaktır; yeni SQL veya kalıcı
dosya-kuralı tablosu değildir. Karar mevcut run/veri yapıları üzerinden
sonuçla ilişkilendirilebilmeli; yeniden okuma ve Excel'de kapsam kaybolmamalıdır.
Bu imkân teknik tasarımda doğrulanmadan “SQL'siz çözüldü” denmez.

Aynı tutar farklı kaynaklarda tekrar bulunuyorsa toplamlar körlemesine
toplanmaz. Kapsam çakışması ve farklı kontrollerin aynı GL hedefini kullanması
çözülmeden bağımsız bir başarılı kontrol sonucu verilmez. Mevcut motorun bu
durumlarda destek kaynaklarını topladığı dikkate alınmalıdır.

### 11.6. Redhawk ile doğrulanacak kapsam

17 Eylül 2026 salt okunur dosya incelemesinde mevcut dört dosya: GL, payroll,
vendor invoices ve contracts. Üç destek dosyasında da Account kolonu yoktur.

| Kontrol | Dosyada bulunan yapı | Uygulamadan önce netleştirilecek kapsam |
|---|---|---|
| Bordro | Base Compensation, Bonus, Benefits Cost, Role, Pay Period | Tutarların dönemi ve ücret hesaplarına dağılımı; Technician Wages, Admin Wages, Owner Salary ve varsa Installation Labor ilişkisi |
| Tedarikçiler | Vendor, Product Line, Description, Amount, Invoice Date | Satırların ilgili gider/COGS hesaplarına eşlemesi; bütün dosyanın tek hesaba ait olduğu varsayılmaz |
| Sözleşmeler | Monthly Fee, Status, Start Date, Last Billed | Service Revenue hedefi; mevcut roster kurallarıyla dönem/aktiflik kapsamı; hazır Monthly Fee tekrar çarpılmaz |

Bu tablo onaylı finansal hesaplama formülü değildir. Kolon adları tek başına
bordro tutarının aylık mı yıllık mı olduğunu veya hangi yan hakların hangi GL
hesabına girdiğini kanıtlamaz. Her kontrol için deterministik beklenen sonuç
uygulamadan önce yazılmalıdır. Mevcut roster davranışı farkı yok etmek amacıyla
değiştirilmez. Yanlış GL hedefini mevcut sayısal guardrail kendiliğinden bulamaz.

Kurulum/yakıtın sonraki tesliminde Installation Revenue ve Vehicle & Fuel
hesaplarının kapsamı doğrulanır. Depozito/tahsilat toplamının gelirle veya
sadece yakıtın birleşik araç/yakıt gideriyle aynı olduğu varsayılmaz.
Yeni dosya adı, şema ve detector birlikte kilitlenmeden bu kontroller açılmaz.

### 11.7. Excel ve paylaşım

Mevcut Reconciliations sayfasının başına aynı kontrol özeti ve kapsam bilgisi
yerleştirilir; altında mevcut recon ayrıntıları korunur. Consolidated P&L ve
Source Breakdown korunur. Yeni bir checklist sayfası bu ilk teslim için şart
değildir. Ekran ve Excel aynı deterministik kontrol sonucundan beslenir.

Temiz kontrolde de kaynak/hedef ve karşılaştırma kanıtı bulunmalıdır. Eksik
kaynaklar ve değerlendirilmemiş alanlar export'ta kaybolmamalıdır. Banka için
mevcut dışarıda-mutabakat cümlesi kalır; oturumluk kutu kalıcı sign-off veya
Excel onayı gibi sunulmaz. Açıklar varken indirilen paket bunları açıkça taşır;
“dönem kapandı” etiketi almaz. Eski raporun yeniden indirilmesi güncel dosyalarla
yapılmış yeni bir karşılaştırma gibi gösterilmez.

### 11.8. Kabul: kullanıcı gerçekten sonuç alıyor mu?

Aşağıdakiler yapılmış testler değil, uygulama öncesi kabul şartlarıdır:

- Redhawk'ın mevcut dosyalarıyla her kontrolün kapsamı, hedefi ve beklenen
  sonucu deterministik olarak tanımlıdır. Salt dosya varlığı başarı değildir.
- Temiz eşleşmede recon kartı çıkmasa da kontrolün yapıldığı kanıtlanır.
- Account'suz tek hedefli kaynak doğru karşılaştırılır; çok hedefli kaynak
  yanlışlıkla file-total moduna sokulmaz.
- Yanlış hedef, GL yokluğu, kaynak yokluğu, boş kaynak, kısmi mapping ve
  dosyalar arası kapsam çakışması sahte Tied out üretmez.
- Kullanıcı her açık için “hangi hesabı/kaynağı inceleyeceğim?” sorusunu
  cevaplayabilir; desteklenmeyen satır-seviyesi teşhis uydurulmaz.
- Mevcut guardrail, materiality, coverage ve altı sınıf davranışı korunur;
  kasıtlı sayısal uyuşmazlık doğrulanmış sonuç gibi sunulmaz.
- UI ve Excel sayıları/durumları aynıdır; bankanın dışarıda olduğu ve
  kurulum/yakıtın değerlendirilmediği ikisinde de görünür.
- Hedef kullanıcıyla 60 saniyelik okuma yürüyüşünde açık iş, eksik kapsam,
  kaynak kanıtı ve sonraki adım bulunabilir. Kullanıcı doğrulaması henüz yapılmadı.

### 11.9. Sınırlar ve uygulama öncesi açıklar

Dil 1 iskeleti korunur. Yeni ajan, recon sınıfı, banka matching, ERP JE,
closed/sign-off, run kilidi, SQL, Cloudflare/deploy, Gün 0 manifesti ve açık
madde yaşlandırması bu kaydın dışındadır. Takılı-run / yeniden üretme işi
yeniden açılmaz. Sentinel binary restore bir kabul kapısı değildir.

Ürün yönü belirlenmiştir; teknik uygulama kilidi için hâlâ üç somut çıktı
gereklidir: Redhawk kontrol bazlı tutar/dönem/GL kapsamı ve beklenen sonuçları;
eksik/kısmi/çakışan kapsamın karşılaştırma kanıtı; run-scoped mapping ile rapor
ve Excel arasındaki izlenebilirliğin mevcut şemayla nasıl korunacağı.
Bu açıklar çözülmeden uygulama hazır veya finansal sonuç doğrulanmış sayılmaz.

### 11.10. Kararın araştırma dayanağı

17 Eylül 2026 tarihli web incelemesi. Kaynaklar ürün/uygulama rehberleridir;
Month Proof kullanıcı araştırması ya da talep doğrulaması değildir.

- [ServiceTitan — Closing Timeline](https://www.servicetitan.com/guides/contractor-playbook/closing-timeline):
  Örnek kapanışta kayıt ve mutabakat işleri finansal inceleme, yönetimle paylaşım
  ve dönem kilidinden önce gelir. Kapsam bu üç/beş kontrolden daha geniştir.
- [ServiceTitan — Commercial Accounting](https://www.servicetitan.com/commercial-playbook/commercial-accounting):
  Bekleyen faturalar, aktarılmamış ödemeler ve operasyon/muhasebe tutarlılığı
  gibi somut kayıt eksiklerini görünür kılan kontroller sunar.
- [FloQast — Global Month-End Close](https://www.floqast.com/optimize-the-close/products/global-month-end-close):
  Durum görünürlüğü, iş sorumluluğu ve destekleyici belgeleri öne çıkarır.
- [BlackLine — Pluralsight örneği](https://www.blackline.com/blog/online-learning-company-learns-how-to-cut-close-cycle/):
  Hazırlama ve inceleme adımlarının belgelenmesi, inceleyenin tamamlanan
  mutabakatı erişilebilir kanıtlarla değerlendirebilmesini destekler.

Month Proof için çıkarımımız: önce açık iş ve kapsam, ardından erişilebilir
kanıt ve finansal anlatı. Bu çıkarım yeni görev atama, çok kullanıcılı onay veya
tam kapanış yönetimi özelliklerini bu dilime dahil etmez.

### 11.11. 17 Eylül 2026 — İlk teslim uygulandı

İnceleme sonrası not: Bu bölüm ilk uygulamanın kaydıdır; tamamlanma kabulü
değildir. Bulunan dört hata için güncel karar ve düzeltme kapsamı §11.12'dedir.

Uygulama yetkisi bu tarihte verildi. Dil 2 ilk teslimi kodda:

**Kontrol sözleşmesi (Redhawk, 2026-03, pandas ile doğrulandı)**

- Bordro: tutar = keşfedilen amount kolonu (fixture’da Base Compensation).
  Bonus ve Benefits Cost amount olarak map edilmedikçe kapsam dışıdır.
  Pay Period close ayına eşitse satır tutulur. Eşleme tanesi Role → GL;
  çalışan adları Haiku’ya veya rapor kanıtına gitmez. Installation Labor
  bordro hedefi değildir. Onaylı Role eşlemesinde Owner Salary 5,500,
  Technician Wages 6,200, Admin Wages 1,400 GL ile tutar.
- Tedarikçiler: Amount + Product Line tanesi. Dosya tek COGS hesabına
  toplanmaz. Yakıt faturası bu kontrolün gider satırıdır; ayrı Fuel
  kontrolü açılmaz.
- Sözleşmeler: Monthly Fee çarpılmaz. Mevcut roster (85 / 82 / 3) korunur.
  File-total hedefi yalnız **Service Revenue**. Monitoring Revenue icat
  edilmez. Fixture: 3,825.00 vs 3,540.00, fark 285.00 → has_exceptions.

**Davranış**

- Kontrol durumları Python’da üretilir: Tied out, Has exceptions, Mapping
  required, Source missing, Not compared. Kart çıkmaması Tied out değildir.
- Tied out için iki taraflı karşılaştırma, doğrulanmış hedef, tam kapsam ve
  mevcut `_is_material` gerekir. Kısmi kontrol Tied out olamaz.
- File-total, Account kolonunun yokluğundan otomatik seçilmez. Sözleşme
  roster’ı veya parse sonrası boş satır tanesi kullanıcı onaylı tek GL
  hedefine gider. Satır mapping’i aynı tutara ikinci kez uygulanmaz.
- Onay run-scoped `parse_preview.file_total_decisions` içindedir. Vendor
  satır hafızasına yazılmaz. Yeni SQL yoktur.
- Rapor `reconciliations` JSONB’si `close_controls_v1` zarfına konur.
  Eski liste şekli Tied out uydurmaz. GET /report ve Excel aynı özeti okur.
- Kurulum/yakıt yalnız kapsam notudur. `3/5` veya kapanış yüzdesi yoktur.
- Banka cümlesi ve oturumluk kutu aynıdır; Excel’e sign-off yazılmaz.

**Açık kalan**

- Kurulum ve yakıt named kontrolleri (fixture + detector + kapsam).
- Bordro Bonus / Benefits’in ücret hesaplarına dağıtımı — kullanıcı onayı
  veya ayrı GL olmadan tahmin edilmez.
- 60 saniyelik kullanıcı yürüyüşü henüz yapılmadı.
- Dil 3: `closed` / sign-off / dönem kilidi.

SQL, `supabase db push`, Cloudflare, banka satır eşleme ve period lock
yapılmadı.

### 11.12. 17 Eylül 2026 — İnceleme sonrası dört düzeltme kararı

Kullanıcı, aşağıdaki sadeleştirilmiş yaklaşımı onayladı; önce bu kayıt,
ardından uygulama ve regresyon testleri yapılacak. Yeni ekran, ajan veya
veritabanı tablosu gerekmiyor. Önceki 571 testin geçmesi bu dört durumu
doğrulamadığı için ilk teslimin kabulü henüz tamamlanmış sayılmaz.

1. **Kontrol başına tek destek dosyası:** Aynı kontrol için birden fazla
   dosya varsa otomatik başarılı karşılaştırma yapılmaz. Kullanıcıdan
   dosyaları birleştirip yeniden yüklemesi istenir; durum Not compared olur.
   Tek dosyanın birden fazla GL hesabına dağılması desteklenir. Boş dosya
   Tied out olamaz. Dosyaların birbirini tamamlayıp tamamlamadığını tahmin
   eden yeni bir motor yapılmaz.
2. **Dar file-total kapsamı:** Gerçek Account/GL kolonu varsa satır eşlemesi
   korunur. Sözleşmelerde file-total yalnız desteklenen müşteri roster'ı +
   aylık ücret şeması doğrulandığında ve kullanıcı hedefi onayladığında
   kullanılır. Dosya türü veya Account yokluğu tek başına yeterli değildir.
   Belirsiz yapıda sessiz tek-hesap toplaması yapılmaz.
3. **Sunucuda tam onay kontrolü:** Gerekli tüm mapping kararları dolu ve
   geçerli olmalıdır. Boş, eksik veya taslak dışı karar kabul edilmez;
   kayıt yazma ve arka plan işi başlamadan mevcut eşleme ekranına anlaşılır
   hata döner. Şirket ve run yetki kontrolleri korunur.
4. **Excel açıklama eşitliği:** Kontrol seviyesindeki eksiklik nedeni ve
   sonraki adım mevcut Reconciliations sayfasında korunur. Yeni sayfa veya
   ayrı hesaplama eklenmez; aynı control summary kullanılır.

Doğrulama: Her hata için regresyon testi; gerçek Account içeren çok hedefli
sözleşme ile Redhawk roster yolunun ayrılması; eksik/boş onayda hiçbir yan
etki olmaması; UI/Excel eksiklik açıklaması eşitliği. İlgili backend suite,
guardrail kontrolleri ve frontend doğrulaması tekrar çalıştırılacak.
Tarayıcı yürüyüşü yapılmadıysa açıkça açık iş olarak kalacak. Commit, SQL,
deploy, banka matching ve Dil 3 bu onayın dışındadır.

**Uygulama sonucu — 17 Eylül 2026:** Dört düzeltme working tree'de uygulandı.
Çoklu destek dosyası kontrolü Not compared üretir; gerçek GL kolonu bulunan
sözleşmeler satır eşlemesinde kalır. File-total ilk teslimde yalnız doğrulanmış
aylık ücret roster şemasına açıktır; boş parse sonucu uygunluk kanıtı değildir.
Belirsiz sözleşme şemasında mevcut hata akışı desteklenen export'u ister.
Onaysız roster taslağı yalnız toplu tutarı taşır; müşteri kimlikleri hesap
eşleme LLM'ine gönderilmez. Eksik/boş/taslak dışı mapping onayı yan etki
başlamadan reddedilir. Excel'in mevcut sayfasında Why not compared ve Next
action birlikte korunur.

**Doğrulama:** `pytest -q tests/tools tests/agents tests/api tests/domain`:
588 passed (17 yeni regresyon testi; guardrail testleri dahil). Gerçek Redhawk
roster'ının parser yolunda 3,825 toplamını koruması, çok hesaplı sözleşmenin
satır mapping'inde kalması, sanitizasyon ve reddedilen onayların yan etkisizliği
yerel fixture/mock testleriyle doğrulandı. Frontend typecheck ve production
build geçti; build mevcut büyük chunk uyarısını verdi. Değiştirilen Python
dosyalarında Black geçti; Flake8 `--ignore E501,W503` ile geçti. Genel
`black --check backend tests` kapsam dışında kalan beş dosyada, genel Flake8
ise mevcut repo biçim/unused-import sorunlarında başarısız; tüm repo lint'i
yeşil denmiyor. Code-auditor kontrolünde mevcut guardrail toleransları ve
yetkilendirme korunmuştur; skill'in eski tolerans notu uygulanmamıştır.

Tarayıcıda 60 saniyelik kullanıcı yürüyüşü ve Excel'in görsel incelemesi henüz
yapılmadı; otomatik testler bunların yerine geçmiş sayılmaz. Canlı servis,
ücretli LLM, SQL, deploy veya commit yapılmadı.
