# Dil 2 kenarları ve Dil 3 kilidi — canlı doğrulama, 1 Ekim 2026

Demo şirket (Redhawk), Mart ve Nisan 2026. Nisan için tarihleri kaydırılmış sentetik kopyalar kullanıldı
(`docs/demo_data` değişmedi). Dosya: `monthproof_2026-03-01_close_package.xlsx` (düzeltme öncesi, Mart),
`workbook.pdf` + `screenshots/workbook_page*.png` (Numbers'tan PDF), `after_layout_fix.pdf` +
`screenshots/after_page*.png` (düzeltme sonrası örnek).

| Madde | Sonuç | Not |
|---|---|---|
| Excel kâr tablosu (Mart) | PASS | Revenue 38.090, COGS 14.705, OPEX 10.990, G&A 8.760, net +3.635; ekranla aynı; Missing JE ve rol adı yok |
| Excel sunum | Düzeltildi | "Sources" sütunu GL ve destek dosyasını yan yana yazıyordu ve kesiliyordu. Başlık "GL amount wins; other files are evidence", sütun genişletildi ve sarıldı, Source Breakdown başlığına not eklendi |
| Excel görsel (L15) | PASS (düzeltmeyle) | Reconciliations ve Source Breakdown okunaklı; P&L "Sources" kesiliyordu, düzeltildi |
| L5 eksik kaynak | PASS | Sözleşme "Source missing", Tied out değil |
| L7 boş kaynak | **FAIL** | Boş bordro dosyası `KeyError: 'amount'` ile çöküyor, kullanıcı "Something went wrong" görüyor. Nedeni açık, düzeltilmedi |
| L8 bir kontrol için iki dosya | PASS (kısmi) | Kart "Not compared", iki dosya adı, birleştir talimatı. Ama altındaki istisna listesi ve anlatı iki dosyayı yine toplayıp "$1.400 fark" diyor |
| L10 iki GL hedefli sözleşme | PASS | Satır eşlemesi korunuyor, dosya toplamı önerilmiyor |
| L11 belirsiz sözleşme | PASS | Net hata, rapor ve arka plan işlemi yok (mesaj genel: "couldn't read this file") |
| L12 geçersiz mapping onayı | PASS | Boş, eksik, fazla, geçersiz hesap: hepsi 400, run durumu değişmedi |
| L6 GL'de olmayan hedef | Kapalı | Hedef listesi yalnız GL hesapları; geçersiz hesap sunucuda 400 (L12) |
| Kapalı ayda Replace | PASS | Nisan kapalıyken Replace onayı 409, `monthly_entries`'e istek gitmedi. Ekranda kullanıcı düz mesaj yerine ham "API 409" görüyor |
| L16 stale-export | PASS | Replace sonrası yeni rapor yazılana kadar 6 export isteği 409, sonra 200 |
| Retry (kapalı ay) | Birim test | Canlıda üretilemedi (`guardrail_failed` run gerekir) |

Ek gözlem: Opus yükseltmesi Nisan'da guardrail'de düştü; asıl rapor değişmeden kaldı (bilinen davranış).
