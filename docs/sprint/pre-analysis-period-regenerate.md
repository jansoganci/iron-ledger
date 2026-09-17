# Aynı dönemi yeniden üretme — pre-analysis

**Durum:** onaylandı ve kodlandı. Onay kutusu uygulandı.

**Aile:** takılı run / aynı `(şirket, ay)` ikinci kez kapanış. Dil 2 (checklist) ve Dil 3 (`closed`) değil.

**Kaynak:** `backend/domain/run_state_machine.py`, `backend/agents/interpreter.py`, `backend/adapters/supabase_repos.py` (`ReportsRepo.write`, `EntriesRepo.replace_period`), `backend/api/routers/uploads.py` (`POST /confirm`, `POST /retry`), `backend/messages.py`, `tests/agents/test_report_write_conflict.py`.

---

## Kullanıcı cümlesi (kilit)

Herhangi bir ayın verisi değişince, o ay **bir / iki / beş kez** daha yüklenirse sistem her seferinde “emin misin?” diye sorar. “Eminim” denirse **o seferki yeni dosyalarla** baştan hesaplar.

Bu belge o cümleyi koda çevrilecek kurallara çevirir.

---

## Bugün (kod)

1. İlk Mart yüklemesi: önizleme onayı → `replace_period` → karşılaştırma → anlatı → guardrail → `reports` INSERT → `complete`.
2. Mart silinmeden ikinci yükleme: önizleme onayı yine `monthly_entries`’i değiştirir. `reports` insert-only + `reports_monthly_unique` ikinci satırı reddeder. Run `report_failed`. Mesaj “önce sil” der. Aylık silme API’si yok. `POST /retry` yalnız `guardrail_failed`.
3. Eski “GENERATING’de %98 sonsuza” takılması **düzeltildi** (`REPORT_FAILED` + poller). Kalan boşluk: açık regenerate yok.

Claude matematik yapmaz. Bu dilim de yaptırmaz.

---

## Onaylanan davranış (Mart örneği)

| Sefer | Soru | Eminim | Vazgeç |
|---|---|---|---|
| 1. yükleme (bu ayda henüz doğrulanmış rapor yok) | Ekstra soru yok. Bugünkü “Confirm & Analyze” durur. | Yeni rapor yazılır. | Önizlemede durursan eski bir rapor yoktur; Mart satırı yazılmaz. |
| 2. / 3. / 5. yükleme (doğrulanmış rapor var) | Analyze’a basınca blocking “emin misin?” | Yeni dosyalarla tam pipeline. Guardrail geçerse **tek** güncel Mart raporu o olur. | Hiçbir şey değişmez. Eski rapor + eski satırlar durur. |

Beş kez “eminim” = beş kez pandas + beş kez anlatı + beş kez guardrail. Ekranda Mart için **tek** doğrulanmış rapor kalır: son geçen.

---

## Kilit kararlar

Tartışmalıysa kod yazma.

| # | Karar | Değer |
|---|---|---|
| 1 | Sessiz UPSERT | Yasak. |
| 2 | Yeni SQL | Yok. Çeyreklik gibi: açık sil → INSERT. Unique index durur. |
| 3 | Blocking soru | Analyze tıklanınca, **yalnız** o dönemde doğrulanmış aylık rapor varsa. |
| 4 | Sunucu kilidi | `POST /runs/{id}/confirm`: rapor varsa ve run’da `regenerate=true` yoksa **409**, `replace_period` çalışmaz. |
| 5 | Rapor ne zaman değişir | Guardrail **geçtikten sonra**. Interpreter, flag varsa eski aylık raporu siler, sonra insert eder. Flag yoksa bugünkü gibi `REPORT_FAILED`. |
| 6 | Eski run | Terminal audit. Güncellenmez. |
| 7 | Public aylık DELETE | Bu dilimde yok. Silme yalnız interpreter içinde, flag + geçen guardrail ile. |
| 8 | `POST /retry` | Değişmez. Hâlâ yalnız `guardrail_failed`. |
| 9 | `closed` / Dil 2 | Yok. |
| 10 | Anomaliler | Aynı dönem yeniden hesaplanınca eski anomaly satırları silinir, yenileri yazılır. Beş sefer üst üste yığılmaz. |

---

## Akış

```
Dosya + dönem seç
        │
        ▼
Bu dönemde doğrulanmış aylık rapor var mı?
        │
   hayır ──► bugünkü upload (flag yok)
        │
      evet
        │
        ▼
Modal: “Bu ayın doğrulanmış raporu var. Devam edersen
önizlemeden sonra sayılar değişir; doğrulama geçerse
rapor da yenilenir. Emin misin?”
        │
   Vazgeç ──► modal kapanır, istek yok
        │
   Eminim
        │
        ▼
POST /upload  (run extras: regenerate=true)
discovery / mapping / preview  — monthly_entries henüz dokunulmaz
        │
        ▼
Confirm & Analyze  (gövde veya run flag: regenerate=true)
        │
        ▼
replace_period + anomalileri dönem için değiştir
karşılaştırma + anlatı + guardrail
        │
   geçti ──► eski aylık raporu sil, yenisini yaz, complete
        │
   kaldı ──► eski rapor durur, run guardrail_failed,
             satırlar yenidir, rapor bayat; Retry Analysis
             bu yeni run için çalışır
```

Önizleme adımı kalkmaz. İlk yüklemede tek onay odur. Yeniden yüklemede Analyze modalı **asıl** “emin misin”; önizlemede kısa hatırlatma (“Onay, doğrulama geçince bu ayın mevcut raporunun yerini alır”).

---

## Guardrail düşerse (dürüst kenar)

“Eminim” satırları değiştirir (karşılaştırma DB’deki `monthly_entries`’e bakmak zorunda). Yeni rapor **yazılmaz**, çünkü guardrail geçmedi. Eski doğrulanmış rapor durur; `is_stale` true olur.

Bu bilinçli: doğrulanmış raporu, henüz doğrulanmamış bir anlatı için silmeyiz.

Retry Analysis (`guardrail_failed`) aynı yeni dosyayla taze run açar. O run da `regenerate=true` taşımalı ki ikinci deneme raporu yazabilsin. Bu dilimde: retry, kaynak run’daki `regenerate` bayrağını kopyalar.

---

## API / kod (onay sonrası, şimdi değil)

- `ConfirmRequest.regenerate: bool = False` — `backend/api/routers/uploads.py`
- `POST /upload` form: `regenerate` (opsiyonel). Rapor yoksa yok sayılır.
- Run extras: `regenerate: true` (retry bunu kopyalar)
- `ReportsRepo.delete_monthly(company_id, period)` — `delete_quarterly` gibi, idempotent, `company_id` JWT’den
- Interpreter: guardrail geçti + flag → `delete_monthly` sonra `write`
- `AnomaliesRepo.replace_period` (veya delete-then-`write_many`) — `company_id` + `period`
- Mesajlar yalnız `backend/messages.py`:
  - onay yokken 409: dönem zaten doğrulanmış, yeniden üretmek için onay gerekir
  - `REPORT_ALREADY_EXISTS` interpreter savunması olarak kalır (flag yok)
- Frontend: `UploadPage` Analyze öncesi modal; `ParsePreviewPanel` hatırlatma; `ReportSummary` Regenerate aynı upload’a gider (dönem dolu, modal çıkar)
- Yeni sayfa yok. Token’lar `frontend/src/index.css`. `company_id` istemciden yazılmaz.

---

## Testler (onay sonrası)

- İlk confirm, flag yok: rapor yazılır, 409 yok.
- Rapor varken confirm flagsız: 409, `monthly_entries` değişmez, rapor aynı kalır.
- Rapor varken flag: satırlar yeni dosya, tek güncel rapor yeni, eski run `complete` durur.
- Beş döngü: `reports`’ta o dönem için tek aylık satır; anomaly yığını yok.
- Flag + guardrail fail: eski rapor durur, run `guardrail_failed`, satırlar yeni.
- Interpreter flagsız ikinci yazı: hâlâ `REPORT_FAILED`, sessiz silme yok.
- `delete_monthly` başka şirketin satırına dokunmaz.
- Frontend `typecheck`.

Canlı LLM / `supabase db push` yok.

---

## Dışarıda

- Dil 2 isimli beş kontrol, Dil 3 `closed`
- Rapor sürüm geçmişi UI
- Public `DELETE /report/{period}`
- `POST /retry`’yi `report_failed` yapmak
- Guardrail toleransı, mapping, token, checklist Dil 1
- Migrasyon / unique index değişikliği

`closed` gelince kilitli dönem bu modalı göstermez ve 409 döner. O kural bu dilimde kodlanmaz.

---

## Onay kutusu

- [x] Kilit tablo kabul
- [x] Guardrail-fail kenarı kabul (satır yeni, rapor eski, bayat)
- [x] Anomali replace bu dilimde
- [x] SQL yok kabul
- [x] Kod, bu kutu işaretlendikten sonra
