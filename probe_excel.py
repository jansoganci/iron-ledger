import openpyxl
from pathlib import Path

# Dosya yolunu kendi yoluna göre güncelle
file_path = Path("docs/demo_data/Drone Inc - Mar 26.xlsx")
wb = openpyxl.load_workbook(file_path, data_only=True)
ws = wb.active

print(f"{'Row':<5} | {'Value':<30} | {'Bold':<6} | {'Indent'}")
print("-" * 60)

for i, row in enumerate(ws.iter_rows(min_row=1, max_row=20), 1):
    cell = row[1] # B sütununa (Account) bakıyoruz genelde
    print(f"{i:<5} | {str(cell.value):<30} | {str(cell.font.bold):<6} | {cell.alignment.indent}")